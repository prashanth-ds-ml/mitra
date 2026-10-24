def test_two_refunds(api, paid_order):
    oid = paid_order["id"]
    api.post(f"/orders/{oid}/refunds", json={"amount": "50.00"})
    api.post(f"/orders/{oid}/refunds", json={"amount": "25.50"})
    resp = api.get(f"/orders/{oid}/refunds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_refunded"] == "75.50"
    assert [r["amount"] for r in body["refunds"]] == ["50.00", "25.50"]
    assert all(r["refund_id"].startswith("re_") for r in body["refunds"])


def test_unpaid_order(api):
    oid = api.post("/orders", json={"items": [{"sku": "x", "unit_price": "1.00"}]}).json()["id"]
    assert api.get(f"/orders/{oid}/refunds").json() == {"total_refunded": "0.00", "refunds": []}


def test_unknown_order(api):
    assert api.get("/orders/ord_9999/refunds").status_code == 404
