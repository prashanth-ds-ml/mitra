"""paysdk: internal payments SDK (fake). Read paysdk/README.md before using it."""

from .client import MAX_PAGE, Charge, FakeBackend, Page, PaymentsClient, Refund
from .errors import (
    CardDeclined,
    IdempotencyConflict,
    InvalidRequest,
    NotFound,
    PayError,
    RateLimited,
    RefundTooLarge,
)
from .money import CurrencyMismatch, Money
from .result import Result

__all__ = [
    "MAX_PAGE",
    "CardDeclined",
    "Charge",
    "CurrencyMismatch",
    "FakeBackend",
    "IdempotencyConflict",
    "InvalidRequest",
    "Money",
    "NotFound",
    "Page",
    "PayError",
    "PaymentsClient",
    "RateLimited",
    "Refund",
    "RefundTooLarge",
    "Result",
]
