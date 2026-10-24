"""Result: a value or a PayError. Check `.ok` (or call `.unwrap()`) before using `.value`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .errors import PayError

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: PayError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def unwrap(self) -> T:
        """Return the value, or raise the error."""
        if self.error is not None:
            raise self.error
        return self.value  # type: ignore[return-value]

    @classmethod
    def success(cls, value: T) -> Result[T]:
        return cls(value=value)

    @classmethod
    def failure(cls, error: PayError) -> Result[T]:
        return cls(error=error)
