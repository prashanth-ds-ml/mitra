def test_create_and_pay_order(api):
    order = api.post("/orders", json={"items": [{"sku": "tea", "unit_price": "12.50", "qty": 2}]})
    assert order.status_code == 201
    assert order.json()["total"] == "25.00"

    paid = api.post(f"/orders/{order.json()['id']}/pay")
    assert paid.status_code == 200
    assert paid.json()["amount"] == "25.00"


def test_partial_refund(api, paid_order):
    resp = api.post(f"/orders/{paid_order['id']}/refunds", json={"amount": "50.00"})
    assert resp.status_code == 201
    assert resp.json()["amount"] == "50.00"


def test_unknown_order_is_404(api):
    assert api.get("/orders/ord_9999").status_code == 404
