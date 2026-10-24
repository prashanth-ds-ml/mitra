MIXED = [{"sku": "a", "unit_price": "1.00"}, {"sku": "b", "unit_price": "1.00", "currency": "USD"}]


def test_code(api):
    resp = api.post("/orders", json={"items": MIXED})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "currency_mismatch"


def test_not_saved(api):
    api.post("/orders", json={"items": MIXED})
    assert api.get("/orders/ord_0001").status_code == 404
    ok = api.post("/orders", json={"items": [{"sku": "a", "unit_price": "1.00"}]})
    assert ok.status_code == 201


def test_same_foreign_currency_ok(api):
    items = [{"sku": "a", "unit_price": "2.00"}, {"sku": "b", "unit_price": "3.00"}]
    resp = api.post("/orders", json={"items": items, "currency": "USD"})
    assert resp.status_code == 201
    assert resp.json()["total"] == "5.00"
