import pytest

from paysdk import Money, PaymentsClient


@pytest.mark.parametrize("n", [0, 1, 100, 101, 250])
def test_counts(api, backend, n):
    client = PaymentsClient(backend)
    for i in range(n):
        client.charges.create(Money(100 + i), idempotency_key=f"k{i}")
    body = api.get("/charges").json()
    assert body["count"] == n
    ids = [c["id"] for c in body["charges"]]
    assert ids == sorted(set(ids))
