"""PaymentsClient over an in-memory fake backend (stands in for the internal payments API)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from .errors import CardDeclined, IdempotencyConflict, InvalidRequest, NotFound, RateLimited, RefundTooLarge
from .money import Money
from .result import Result

MAX_PAGE = 100


@dataclass(frozen=True)
class Charge:
    id: str
    amount: Money
    description: str
    idempotency_key: str


@dataclass(frozen=True)
class Refund:
    id: str
    charge_id: str
    amount: Money


@dataclass(frozen=True)
class Page:
    items: list
    next_cursor: str | None  # None means this was the last page


@dataclass
class FakeBackend:
    """State of the fake payments service. Tests use the helpers to script failures."""

    charges: dict[str, Charge] = field(default_factory=dict)
    refunds: dict[str, Refund] = field(default_factory=dict)
    by_key: dict[str, str] = field(default_factory=dict)
    decline_over_paise: int = 10_000_000
    rate_limit_next: int = 0
    rate_limit_retry_after: float = 0.0
    lose_next_responses: int = 0
    calls: int = 0

    def fail_next_with_rate_limit(self, times: int, retry_after: float = 0.0) -> None:
        self.rate_limit_next = times
        self.rate_limit_retry_after = retry_after

    def fail_next_after_commit(self, times: int, retry_after: float = 0.0) -> None:
        """The next `times` new charges are saved, then RateLimited is raised (the response was lost)."""
        self.lose_next_responses = times
        self.rate_limit_retry_after = retry_after

    def _maybe_rate_limit(self) -> None:
        self.calls += 1
        if self.rate_limit_next > 0:
            self.rate_limit_next -= 1
            raise RateLimited(self.rate_limit_retry_after)


class Charges:
    def __init__(self, backend: FakeBackend) -> None:
        self._b = backend

    def create(self, amount: Money, *, idempotency_key: str, description: str = "") -> Result[Charge]:
        """Charge `amount`. Calls with the same idempotency key and amount return the same charge.

        Raises RateLimited (retry with the same key) and InvalidRequest (bad arguments).
        """
        if not isinstance(amount, Money):
            raise InvalidRequest("amount must be Money")
        if not idempotency_key:
            raise InvalidRequest("idempotency_key is required")
        if amount.paise <= 0:
            raise InvalidRequest("amount must be positive")
        self._b._maybe_rate_limit()
        if idempotency_key in self._b.by_key:
            existing = self._b.charges[self._b.by_key[idempotency_key]]
            if existing.amount != amount:
                return Result.failure(IdempotencyConflict("same key used with a different amount"))
            return Result.success(existing)
        if amount.paise > self._b.decline_over_paise:
            return Result.failure(CardDeclined("amount over limit"))
        charge = Charge(f"ch_{len(self._b.charges) + 1:04d}", amount, description, idempotency_key)
        self._b.charges[charge.id] = charge
        self._b.by_key[idempotency_key] = charge.id
        if self._b.lose_next_responses > 0:
            self._b.lose_next_responses -= 1
            raise RateLimited(self._b.rate_limit_retry_after)
        return Result.success(charge)

    def get(self, charge_id: str) -> Result[Charge]:
        charge = self._b.charges.get(charge_id)
        return Result.success(charge) if charge else Result.failure(NotFound(charge_id))

    def list(self, *, cursor: str | None = None, limit: int = 20) -> Page:
        """One page of charges, oldest first. Follow `next_cursor` until it is None."""
        if not 1 <= limit <= MAX_PAGE:
            raise InvalidRequest(f"limit must be 1..{MAX_PAGE}")
        start = int(cursor) if cursor else 0
        items = list(self._b.charges.values())[start : start + limit]
        end = start + len(items)
        return Page(items, str(end) if end < len(self._b.charges) else None)

    def get_all(self) -> list[Charge]:
        """DEPRECATED: returns at most 100 charges. Use list() with cursors."""
        warnings.warn("Charges.get_all is deprecated; use list() and follow next_cursor", DeprecationWarning, stacklevel=2)
        return list(self._b.charges.values())[:MAX_PAGE]


class Refunds:
    def __init__(self, backend: FakeBackend) -> None:
        self._b = backend

    def create(self, charge_id: str, amount: Money) -> Result[Refund]:
        """Refund part or all of a charge. Over-refunding returns a RefundTooLarge failure."""
        if not isinstance(amount, Money) or amount.paise <= 0:
            raise InvalidRequest("amount must be positive Money")
        charge = self._b.charges.get(charge_id)
        if charge is None:
            return Result.failure(NotFound(charge_id))
        already = sum(r.amount.paise for r in self._b.refunds.values() if r.charge_id == charge_id)
        if already + amount.paise > charge.amount.paise:
            return Result.failure(RefundTooLarge(f"only {charge.amount.paise - already} paise refundable"))
        refund = Refund(f"re_{len(self._b.refunds) + 1:04d}", charge_id, amount)
        self._b.refunds[refund.id] = refund
        return Result.success(refund)

    def list_for_charge(self, charge_id: str) -> list[Refund]:
        return [r for r in self._b.refunds.values() if r.charge_id == charge_id]


class PaymentsClient:
    def __init__(self, backend: FakeBackend | None = None) -> None:
        self.backend = backend or FakeBackend()
        self.charges = Charges(self.backend)
        self.refunds = Refunds(self.backend)
