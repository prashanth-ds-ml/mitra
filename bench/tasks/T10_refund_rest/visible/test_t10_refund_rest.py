def test_refund_rest(api, paid_order):
    oid = paid_order["id"]
    api.post(f"/orders/{oid}/refunds", json={"amount": "50.00"})
    resp = api.post(f"/orders/{oid}/refunds", json={})
    assert resp.status_code == 201
    assert resp.json()["amount"] == "150.00"
