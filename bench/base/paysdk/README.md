# paysdk

Internal payments SDK. Five rules:

1. **Money is integer paise.** `Money(1250)` is ₹12.50. Parse user input with `Money.from_rupees("12.50")`;
   floats are refused. Format with `money.rupees()`. Adding different currencies raises `CurrencyMismatch`.
2. **Business outcomes come back in a `Result`.** `client.charges.create(...)` and `client.refunds.create(...)` return
   `Result`; check `result.ok` (or call `result.unwrap()`) before using `result.value`. Errors carry a `code`
   (`card_declined`, `refund_exceeds_charge`, `not_found`, `idempotency_conflict`).
3. **Every charge needs an idempotency key.** Use a key that is stable for the thing being paid (for example the order
   id). Retrying with the same key never charges twice.
4. **`RateLimited` is raised, not returned.** Wait `err.retry_after` seconds and retry with the same key.
5. **Lists are paginated.** `charges.list(cursor=..., limit=...)` returns a `Page`; follow `page.next_cursor` until it
   is `None`. `limit` is 1-100. `charges.get_all()` is deprecated and returns at most 100 charges.
