def test_code_and_not_saved(api):
    resp = api.post("/orders", json={"items": [{"sku": "tv", "unit_price": "50000.01", "qty": 2}]})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "order_too_large"
    assert api.get("/orders/ord_0001").status_code == 404


def test_exact_limit_allowed(api):
    resp = api.post("/orders", json={"items": [{"sku": "tv", "unit_price": "50000.00", "qty": 2}]})
    assert resp.status_code == 201
    assert resp.json()["total"] == "100000.00"
