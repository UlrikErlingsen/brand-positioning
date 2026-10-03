import pytest


@pytest.fixture(autouse=True)
def _local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests run as the downloaded app does (no demo limits) unless a test sets SIGNAL_PUBLIC=1 itself."""
    monkeypatch.delenv("SIGNAL_PUBLIC", raising=False)
