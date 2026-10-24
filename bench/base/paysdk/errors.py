"""SDK errors.

Rule of this SDK: business outcomes (declined, not found, invalid refund) come back inside a Result;
transient problems (RateLimited) and programming errors (InvalidRequest) are raised.
"""

from __future__ import annotations


class PayError(Exception):
    code = "pay_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class CardDeclined(PayError):
    code = "card_declined"


class NotFound(PayError):
    code = "not_found"


class RefundTooLarge(PayError):
    code = "refund_exceeds_charge"


class IdempotencyConflict(PayError):
    code = "idempotency_conflict"


class InvalidRequest(PayError):
    """Raised (not returned): the caller used the SDK wrongly."""

    code = "invalid_request"


class RateLimited(PayError):
    """Raised (not returned): wait `retry_after` seconds and try again with the SAME idempotency key."""

    code = "rate_limited"

    def __init__(self, retry_after: float = 0.0) -> None:
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after
