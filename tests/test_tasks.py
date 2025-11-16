from types import SimpleNamespace

from app.tasks import needs_title_refresh


def test_needs_title_refresh_when_title_matches_url():
    link = SimpleNamespace(url="https://example.com", title="https://example.com")
    assert needs_title_refresh(link) is True


def test_needs_title_refresh_when_title_missing():
    link = SimpleNamespace(url="https://example.com", title=None)
    assert needs_title_refresh(link) is True


def test_needs_title_refresh_when_title_differs():
    link = SimpleNamespace(url="https://example.com", title="Custom Title")
    assert needs_title_refresh(link) is False
