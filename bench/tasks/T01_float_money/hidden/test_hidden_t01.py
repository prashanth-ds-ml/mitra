import pytest


@pytest.mark.parametrize("price,qty,total", [("0.29", 3, "0.87"), ("1.15", 1, "1.15"), ("10.10", 7, "70.70"), ("4.35", 3, "13.05")])
def test_exact_totals(api, price, qty, total):
    resp = api.post("/orders", json={"items": [{"sku": "x", "unit_price": price, "qty": qty}]})
    assert resp.status_code == 201
    assert resp.json()["total"] == total


def test_more_than_two_decimals_rejected(api):
    resp = api.post("/orders", json={"items": [{"sku": "x", "unit_price": "1.234", "qty": 1}]})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "bad_amount"


def test_pay_charges_exact_amount(api, backend):
    order = api.post("/orders", json={"items": [{"sku": "x", "unit_price": "1.15", "qty": 1}]}).json()
    api.post(f"/orders/{order['id']}/pay")
    (charge,) = backend.charges.values()
    assert charge.amount.paise == 115
