def test_over_refund_code(api, paid_order):
    resp = api.post(f"/orders/{paid_order['id']}/refunds", json={"amount": "300.00"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "refund_exceeds_charge"


def test_second_refund_over_remaining(api, paid_order):
    oid = paid_order["id"]
    assert api.post(f"/orders/{oid}/refunds", json={"amount": "150.00"}).status_code == 201
    resp = api.post(f"/orders/{oid}/refunds", json={"amount": "60.00"})
    assert resp.status_code == 409
    assert api.post(f"/orders/{oid}/refunds", json={"amount": "50.00"}).status_code == 201


def test_valid_refund_still_works(api, paid_order):
    resp = api.post(f"/orders/{paid_order['id']}/refunds", json={"amount": "200.00"})
    assert resp.status_code == 201
    assert resp.json()["amount"] == "200.00"
