def test_pay_survives_short_rate_limit(api, backend):
    order = api.post("/orders", json={"items": [{"sku": "tea", "unit_price": "10.00"}]}).json()
    backend.fail_next_with_rate_limit(2)
    assert api.post(f"/orders/{order['id']}/pay").status_code == 200
