def _order(api):
    return api.post("/orders", json={"items": [{"sku": "tea", "unit_price": "10.00"}]}).json()["id"]


def test_waits_retry_after(api, backend, sleeps):
    oid = _order(api)
    backend.fail_next_with_rate_limit(3, retry_after=1.5)
    assert api.post(f"/orders/{oid}/pay").status_code == 200
    assert sleeps == [1.5, 1.5, 1.5]
    assert len(backend.charges) == 1


def test_gives_up_after_four_attempts(api, backend):
    oid = _order(api)
    backend.fail_next_with_rate_limit(10)
    resp = api.post(f"/orders/{oid}/pay")
    assert resp.status_code == 503
    assert backend.calls == 4
    assert api.get(f"/orders/{oid}").json()["status"] == "new"


def test_no_rate_limit_no_sleep(api, sleeps):
    assert api.post(f"/orders/{_order(api)}/pay").status_code == 200
    assert sleeps == []
