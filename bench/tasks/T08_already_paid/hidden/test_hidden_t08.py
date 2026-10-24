def test_code_and_no_provider_call(api, backend, paid_order):
    calls = backend.calls
    resp = api.post(f"/orders/{paid_order['id']}/pay")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "already_paid"
    assert backend.calls == calls


def test_first_pay_still_200(api):
    oid = api.post("/orders", json={"items": [{"sku": "x", "unit_price": "5.00"}]}).json()["id"]
    assert api.post(f"/orders/{oid}/pay").status_code == 200
    assert api.get(f"/orders/{oid}").json()["status"] == "paid"
