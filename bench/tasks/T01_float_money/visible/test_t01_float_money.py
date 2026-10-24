def test_total_is_exact(api):
    resp = api.post("/orders", json={"items": [{"sku": "pen", "unit_price": "0.29", "qty": 3}]})
    assert resp.status_code == 201
    assert resp.json()["total"] == "0.87"
