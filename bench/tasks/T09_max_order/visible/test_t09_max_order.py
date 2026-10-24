def test_large_order_rejected(api):
    resp = api.post("/orders", json={"items": [{"sku": "tv", "unit_price": "150000.00"}]})
    assert resp.status_code == 422
