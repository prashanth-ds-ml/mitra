"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_harness(tmp_path, monkeypatch):
    """Tests never read the user's ~/.mitra/harness.toml (the self-improve loop writes it): default settings only."""
    monkeypatch.setenv("MITRA_HARNESS", str(tmp_path / "no-harness.toml"))
