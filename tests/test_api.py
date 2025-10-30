import os
import tempfile

from fastapi.testclient import TestClient

tmp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tmp_db.name}")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.database import Base, engine  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()
client = TestClient(app)


def setup_module(module):  # noqa: D401
    """Initialise database tables for API tests."""

    Base.metadata.create_all(bind=engine)


def teardown_module(module):  # noqa: D401
    """Drop tables and cleanup temp database."""

    Base.metadata.drop_all(bind=engine)
    try:
        tmp_db.close()
        os.unlink(tmp_db.name)
    except OSError:
        pass


def test_create_and_list_link():
    payload = {
        "url": "https://example.com",
        "title": "Example",
        "notes": "Testing",
        "tags": ["test", "example"],
        "collection": "Reading",
        "is_done": False,
    }

    create_response = client.post(
        "/api/links",
        json=payload,
    )

    assert create_response.status_code == 201, create_response.text
    data = create_response.json()
    assert data["url"].rstrip("/") == payload["url"].rstrip("/")
    assert data["collection"]["name"] == "Reading"

    list_response = client.get("/api/links")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["url"].rstrip("/") == payload["url"].rstrip("/") for item in items)
