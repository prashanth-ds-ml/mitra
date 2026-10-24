from paysdk import Money, PaymentsClient


def test_lists_all_charges(api, backend):
    client = PaymentsClient(backend)
    for i in range(150):
        client.charges.create(Money(100), idempotency_key=f"k{i}")
    assert api.get("/charges").json()["count"] == 150
