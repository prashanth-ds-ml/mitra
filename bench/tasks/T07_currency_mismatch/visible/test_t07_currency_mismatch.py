def test_mixed_currency_rejected(api):
    items = [{"sku": "a", "unit_price": "1.00"}, {"sku": "b", "unit_price": "1.00", "currency": "USD"}]
    assert api.post("/orders", json={"items": items}).status_code == 422
