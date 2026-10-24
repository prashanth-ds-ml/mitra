def test_lists_refunds(api, paid_order):
    oid = paid_order["id"]
    api.post(f"/orders/{oid}/refunds", json={"amount": "50.00"})
    body = api.get(f"/orders/{oid}/refunds").json()
    assert body["total_refunded"] == "50.00"
    assert len(body["refunds"]) == 1
