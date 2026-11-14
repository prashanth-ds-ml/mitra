"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_harness(tmp_path, monkeypatch):
    """Tests never read the user's ~/.codemitra/harness.toml (the self-improve loop writes it): default settings only."""
    monkeypatch.setenv("CODEMITRA_HARNESS", str(tmp_path / "no-harness.toml"))
    # nor write to the user's ~/.codemitra (the central store, D-041, mirrors every record written in a test)
    monkeypatch.setenv("CODEMITRA_HOME", str(tmp_path / "codemitra-home"))
    monkeypatch.setenv("CODEMITRA_NO_MIGRATE", "1")  # D-080: tests never move real folders
    for old in ("MITRA_HOME", "MITRA_HARNESS"):
        monkeypatch.delenv(old, raising=False)
