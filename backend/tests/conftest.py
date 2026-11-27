import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    """Ensure unit tests run deterministically offline even when .env defines cloud keys."""
    monkeypatch.setattr(settings, "MOCK_MODE", True)
