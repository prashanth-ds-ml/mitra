def test_full_refund_then_nothing_left(api, paid_order):
    oid = paid_order["id"]
    first = api.post(f"/orders/{oid}/refunds", json={})
    assert first.status_code == 201
    assert first.json()["amount"] == "200.00"
    again = api.post(f"/orders/{oid}/refunds", json={})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "refund_exceeds_charge"


def test_amount_still_supported(api, paid_order):
    resp = api.post(f"/orders/{paid_order['id']}/refunds", json={"amount": "20.00"})
    assert resp.status_code == 201
    assert resp.json()["amount"] == "20.00"
