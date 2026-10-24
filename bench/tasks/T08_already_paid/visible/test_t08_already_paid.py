def test_second_pay_is_409(api, paid_order):
    assert api.post(f"/orders/{paid_order['id']}/pay").status_code == 409
