"""Payment logic for orders, on top of paysdk."""

from __future__ import annotations

import time
from collections.abc import Callable

from paysdk import Charge, Money, PayError, PaymentsClient, RateLimited, Refund, RefundTooLarge

from .store import Order

MAX_RETRIES = 3


class PaymentFailed(Exception):
    def __init__(self, error: PayError) -> None:
        super().__init__(error.message)
        self.error = error


class RefundRejected(Exception):
    def __init__(self, error: PayError) -> None:
        super().__init__(error.message)
        self.error = error


class AlreadyPaid(Exception):
    pass


def order_total(order: Order) -> Money:
    total = Money.zero(order.currency)
    for item in order.items:
        total = total + item.unit_price * item.qty
    return total


def charge_order(client: PaymentsClient, order: Order, sleep: Callable[[float], None] = time.sleep) -> Charge:
    """Charge an order once. Retries rate limits with the same idempotency key."""
    if order.status == "paid":
        raise AlreadyPaid(order.id)
    key = f"order-{order.id}"
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = client.charges.create(order_total(order), idempotency_key=key, description=f"order {order.id}")
        except RateLimited as err:
            if attempt == MAX_RETRIES:
                raise
            sleep(err.retry_after)
            continue
        if not result.ok:
            raise PaymentFailed(result.error)
        charge = result.value
        order.status = "paid"
        order.charge_id = charge.id
        return charge
    raise AssertionError("unreachable")


def refund_order(client: PaymentsClient, order: Order, amount: Money | None = None) -> Refund:
    """Refund `amount`, or everything not yet refunded when `amount` is None."""
    if amount is None:
        amount = order_total(order) - refunded_total(client, order)
        if amount.paise <= 0:
            raise RefundRejected(RefundTooLarge("nothing left to refund"))
    result = client.refunds.create(order.charge_id, amount)
    if not result.ok:
        raise RefundRejected(result.error)
    return result.value


def refunded_total(client: PaymentsClient, order: Order) -> Money:
    total = Money.zero(order.currency)
    if order.charge_id:
        for refund in client.refunds.list_for_charge(order.charge_id):
            total = total + refund.amount
    return total


def all_charges(client: PaymentsClient) -> list[Charge]:
    charges: list[Charge] = []
    cursor = None
    while True:
        page = client.charges.list(cursor=cursor, limit=100)
        charges.extend(page.items)
        if page.next_cursor is None:
            return charges
        cursor = page.next_cursor
