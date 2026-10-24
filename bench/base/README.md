# shop

Small order and payment API built on the internal `paysdk` (see `paysdk/README.md`).

- `shop/app.py`: FastAPI routes (amounts are rupee strings like "12.50")
- `shop/payments.py`: charging, refunds, listing charges
- `shop/store.py`: in-memory orders
- Tests: `python -m pytest -q`
