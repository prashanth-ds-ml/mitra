import pytest
from fastapi.testclient import TestClient

from paysdk import FakeBackend, PaymentsClient
from shop.app import create_app


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def api(backend, sleeps):
    return TestClient(create_app(PaymentsClient(backend), sleep=sleeps.append))


@pytest.fixture
def paid_order(api):
    order = api.post("/orders", json={"items": [{"sku": "tea", "unit_price": "100.00", "qty": 2}]}).json()
    api.post(f"/orders/{order['id']}/pay")
    return order
