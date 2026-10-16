import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from smartrisk import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})


class Client:
    """غلاف حول test_client يدير رمز CSRF تلقائياً."""
    def __init__(self, app):
        self.c = app.test_client()
        self.refresh()

    def refresh(self):
        with self.c.session_transaction() as s:
            s.setdefault("csrf", "test-token")
            self.token = s["csrf"]

    def req(self, method, url, **kw):
        self.refresh()
        h = kw.pop("headers", {})
        h["X-CSRF-Token"] = self.token
        r = getattr(self.c, method)(url, headers=h, **kw)
        return r

    def get(self, url, **kw): return self.req("get", url, **kw)
    def post(self, url, **kw): return self.req("post", url, **kw)
    def put(self, url, **kw): return self.req("put", url, **kw)
    def delete(self, url, **kw): return self.req("delete", url, **kw)


@pytest.fixture()
def client(app):
    return Client(app)


@pytest.fixture()
def user(client):
    r = client.post("/api/auth/register", json={"email": "u1@test.dz", "name": "تجربة", "password": "password123"})
    assert r.status_code == 201
    return client


@pytest.fixture()
def sample_raw():
    return json.loads((ROOT / "smartrisk" / "data" / "templates" / "workshop.json").read_text(encoding="utf-8"))
