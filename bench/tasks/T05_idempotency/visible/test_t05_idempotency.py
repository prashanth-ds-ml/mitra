def test_lost_response_does_not_double_charge(api, backend):
    order = api.post("/orders", json={"items": [{"sku": "tea", "unit_price": "10.00"}]}).json()
    backend.fail_next_after_commit(1)
    assert api.post(f"/orders/{order['id']}/pay").status_code == 200
    assert api.get("/charges").json()["count"] == 1
