"""Money in integer paise. Floats are refused on purpose: they lose paise."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class CurrencyMismatch(ValueError):
    """Two amounts in different currencies were combined."""


@dataclass(frozen=True)
class Money:
    paise: int
    currency: str = "INR"

    def __post_init__(self) -> None:
        if isinstance(self.paise, bool) or not isinstance(self.paise, int):
            raise TypeError("Money takes integer paise; use Money.from_rupees('12.50') for decimal amounts")

    @classmethod
    def from_rupees(cls, amount: str | Decimal, currency: str = "INR") -> Money:
        """Parse a rupee amount given as a string or Decimal, e.g. '12.50'."""
        if isinstance(amount, float):
            raise TypeError("pass rupees as a string or Decimal, never a float")
        try:
            value = Decimal(str(amount)) * 100
        except InvalidOperation as exc:
            raise ValueError(f"not a rupee amount: {amount!r}") from exc
        if value != value.to_integral_value():
            raise ValueError(f"more than 2 decimal places: {amount!r}")
        return cls(int(value), currency)

    @classmethod
    def zero(cls, currency: str = "INR") -> Money:
        return cls(0, currency)

    def _check(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError(f"cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.paise + other.paise, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.paise - other.paise, self.currency)

    def __mul__(self, times: int) -> Money:
        if isinstance(times, bool) or not isinstance(times, int):
            raise TypeError("Money can only be multiplied by an int")
        return Money(self.paise * times, self.currency)

    def rupees(self) -> str:
        """'12.50' style string, the format the API returns."""
        sign = "-" if self.paise < 0 else ""
        whole, frac = divmod(abs(self.paise), 100)
        return f"{sign}{whole}.{frac:02d}"
