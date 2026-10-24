"""Shop API (FastAPI). Amounts in requests and responses are rupee strings like "12.50"."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from paysdk import CurrencyMismatch, Money, PaymentsClient, RateLimited

from . import payments
from .store import LineItem, OrderStore

MAX_ORDER_PAISE = 10_000_000  # ₹1,00,000


class ItemIn(BaseModel):
    sku: str
    unit_price: str
    qty: int = 1
    currency: str | None = None  # defaults to the order currency


class OrderIn(BaseModel):
    items: list[ItemIn]
    currency: str = "INR"


class RefundIn(BaseModel):
    amount: str | None = None  # None refunds everything not yet refunded


def _parse_rupees(value: str, currency: str) -> Money:
    try:
        return Money.from_rupees(value, currency)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, {"code": "bad_amount", "message": str(exc)}) from exc


def _order_json(order, client) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "currency": order.currency,
        "total": payments.order_total(order).rupees(),
        "charge_id": order.charge_id,
    }


def create_app(client: PaymentsClient | None = None, sleep: Callable[[float], None] = time.sleep) -> FastAPI:
    app = FastAPI(title="shop")
    app.state.client = client or PaymentsClient()
    app.state.store = OrderStore()

    def get_order(order_id: str):
        order = app.state.store.get(order_id)
        if order is None:
            raise HTTPException(404, {"code": "order_not_found"})
        return order

    @app.exception_handler(RateLimited)
    async def rate_limited(_request, err: RateLimited):
        return JSONResponse(
            {"detail": {"code": "rate_limited"}}, status_code=503, headers={"Retry-After": str(err.retry_after)}
        )

    @app.post("/orders", status_code=201)
    def create_order(body: OrderIn):
        items = [
            LineItem(i.sku, _parse_rupees(i.unit_price, i.currency or body.currency), i.qty) for i in body.items
        ]
        if not items or any(i.qty < 1 for i in items):
            raise HTTPException(422, {"code": "bad_items"})
        order = app.state.store.add(items, body.currency)
        try:
            total = payments.order_total(order)
        except CurrencyMismatch as exc:
            del app.state.store.orders[order.id]
            raise HTTPException(422, {"code": "currency_mismatch", "message": str(exc)}) from exc
        if total.paise > MAX_ORDER_PAISE:
            del app.state.store.orders[order.id]
            raise HTTPException(422, {"code": "order_too_large"})
        return _order_json(order, app.state.client)

    @app.get("/orders/{order_id}")
    def read_order(order_id: str):
        return _order_json(get_order(order_id), app.state.client)

    @app.post("/orders/{order_id}/pay")
    def pay(order_id: str):
        order = get_order(order_id)
        try:
            charge = payments.charge_order(app.state.client, order, sleep=sleep)
        except payments.AlreadyPaid as exc:
            raise HTTPException(409, {"code": "already_paid"}) from exc
        except payments.PaymentFailed as exc:
            raise HTTPException(402, {"code": exc.error.code}) from exc
        return {"charge_id": charge.id, "amount": charge.amount.rupees()}

    @app.post("/orders/{order_id}/refunds", status_code=201)
    def refund(order_id: str, body: RefundIn):
        order = get_order(order_id)
        if order.status != "paid":
            raise HTTPException(409, {"code": "not_paid"})
        amount = _parse_rupees(body.amount, order.currency) if body.amount is not None else None
        try:
            refund = payments.refund_order(app.state.client, order, amount)
        except payments.RefundRejected as exc:
            raise HTTPException(409, {"code": exc.error.code}) from exc
        return {"refund_id": refund.id, "amount": refund.amount.rupees()}

    @app.get("/orders/{order_id}/refunds")
    def list_refunds(order_id: str):
        order = get_order(order_id)
        refunds = app.state.client.refunds.list_for_charge(order.charge_id) if order.charge_id else []
        return {
            "total_refunded": payments.refunded_total(app.state.client, order).rupees(),
            "refunds": [{"refund_id": r.id, "amount": r.amount.rupees()} for r in refunds],
        }

    @app.get("/charges")
    def list_charges():
        charges = payments.all_charges(app.state.client)
        return {"count": len(charges), "charges": [{"id": c.id, "amount": c.amount.rupees()} for c in charges]}

    return app


app = create_app()
