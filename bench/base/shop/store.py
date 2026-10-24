"""In-memory order store."""

from __future__ import annotations

from dataclasses import dataclass, field

from paysdk import Money


@dataclass
class LineItem:
    sku: str
    unit_price: Money
    qty: int


@dataclass
class Order:
    id: str
    items: list[LineItem]
    currency: str = "INR"
    status: str = "new"  # new -> paid
    charge_id: str | None = None


@dataclass
class OrderStore:
    orders: dict[str, Order] = field(default_factory=dict)

    def add(self, items: list[LineItem], currency: str) -> Order:
        order = Order(f"ord_{len(self.orders) + 1:04d}", items, currency)
        self.orders[order.id] = order
        return order

    def get(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)
