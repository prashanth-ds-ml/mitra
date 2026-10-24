def _order(api, price="10.00"):
    return api.post("/orders", json={"items": [{"sku": "tea", "unit_price": price}]}).json()["id"]


def test_two_lost_responses_one_charge(api, backend):
    oid = _order(api)
    backend.fail_next_after_commit(2)
    resp = api.post(f"/orders/{oid}/pay")
    assert resp.status_code == 200
    assert len(backend.charges) == 1
    assert api.get(f"/orders/{oid}").json()["charge_id"] == resp.json()["charge_id"]


def test_different_orders_get_different_charges(api, backend):
    a, b = _order(api), _order(api)
    api.post(f"/orders/{a}/pay")
    api.post(f"/orders/{b}/pay")
    assert len(backend.charges) == 2


def test_plain_rate_limit_still_retried(api, backend):
    oid = _order(api)
    backend.fail_next_with_rate_limit(2)
    assert api.post(f"/orders/{oid}/pay").status_code == 200
    assert len(backend.charges) == 1
