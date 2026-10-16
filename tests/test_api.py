import json


def test_pages_render(client):
    for url in ("/", "/guide", "/login", "/register"):
        r = client.get(url)
        assert r.status_code == 200, url
        assert "IBM Plex" in r.get_data(as_text=True) or "ibm-plex" in r.get_data(as_text=True)


def test_requires_login(client):
    assert client.get("/api/projects").status_code == 401
    assert client.get("/app").status_code == 302


def test_register_login_logout(client):
    r = client.post("/api/auth/register", json={"email": "bad", "password": "password123"})
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={"email": "x@y.dz", "password": "short"})
    assert r.status_code == 400
    assert client.post("/api/auth/register", json={"email": "x@y.dz", "password": "password123"}).status_code == 201
    assert client.post("/api/auth/register", json={"email": "x@y.dz", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/auth/login", json={"email": "x@y.dz", "password": "wrongpass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "x@y.dz", "password": "password123"}).status_code == 200
    assert client.get("/api/projects").status_code == 200


def test_login_is_throttled(client):
    for _ in range(8):
        client.post("/api/auth/login", json={"email": "z@z.dz", "password": "nope-nope"})
    assert client.post("/api/auth/login", json={"email": "z@z.dz", "password": "nope-nope"}).status_code == 429


def test_csrf_enforced(app):
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "a@b.dz", "password": "x"})
    assert r.status_code == 403


def test_project_lifecycle(user):
    r = user.post("/api/projects", json={"template": "workshop"})
    assert r.status_code == 201
    pid = r.json["project"]["id"]
    assert r.json["project"]["snapshot"]["level"] in ("safe", "warn", "crit")
    got = user.get(f"/api/projects/{pid}").json["project"]
    got["data"]["start_cash"] = 123456
    upd = user.put(f"/api/projects/{pid}", json={"data": got["data"]})
    assert upd.json["project"]["data"]["start_cash"] == 123456
    dup = user.post(f"/api/projects/{pid}/duplicate")
    assert dup.status_code == 201 and dup.json["project"]["name"].endswith("(نسخة)")
    assert len(user.get("/api/projects").json["projects"]) == 2
    assert user.delete(f"/api/projects/{pid}").status_code == 200
    assert user.get(f"/api/projects/{pid}").status_code == 404


def test_users_cannot_see_each_others_projects(app):
    from conftest import Client
    a, b = Client(app), Client(app)
    a.post("/api/auth/register", json={"email": "a@a.dz", "password": "password123"})
    b.post("/api/auth/register", json={"email": "b@b.dz", "password": "password123"})
    pid = a.post("/api/projects", json={"template": "blank"}).json["project"]["id"]
    assert b.get(f"/api/projects/{pid}").status_code == 404
    assert b.put(f"/api/projects/{pid}", json={"data": {"name": "hack"}}).status_code == 404
    assert b.delete(f"/api/projects/{pid}").status_code == 404
    assert b.get(f"/api/projects/{pid}/analyze/summary").status_code == 404
    assert b.get(f"/api/projects/{pid}/export.xlsx").status_code == 404
    assert b.get("/api/projects").json["projects"] == []


def test_analyze_and_preview(user, sample_raw):
    pid = user.post("/api/projects", json={"data": sample_raw}).json["project"]["id"]
    s = user.get(f"/api/projects/{pid}/analyze/summary")
    assert s.status_code == 200 and s.json["overall"] in ("safe", "warn", "crit")
    mc = user.post(f"/api/projects/{pid}/analyze/montecarlo", json={"params": {"n": 500}})
    assert mc.json["n"] == 500
    pv = user.post("/api/preview/breakeven", json={"project": sample_raw})
    assert pv.status_code == 200 and pv.json["breakeven_total"] > 0
    assert user.get(f"/api/projects/{pid}/analyze/nope").status_code == 404
    assert user.post("/api/preview/summary", json={}).status_code == 400


def test_exports(user, sample_raw):
    pid = user.post("/api/projects", json={"data": sample_raw}).json["project"]["id"]
    assert user.get(f"/api/projects/{pid}/export.json").status_code == 200
    csv = user.get(f"/api/projects/{pid}/export/income.csv")
    assert csv.status_code == 200 and "الإيرادات" in csv.get_data(as_text=True)
    x = user.get(f"/api/projects/{pid}/export.xlsx")
    assert x.status_code == 200 and x.data[:2] == b"PK"


def test_export_blocks_formula_injection(user, sample_raw):
    from smartrisk.api.exports import _safe_cell
    assert _safe_cell("=HYPERLINK(1)").startswith("'") and _safe_cell("عادي") == "عادي"


def test_import_roundtrip(user, sample_raw):
    pid = user.post("/api/projects", json={"data": sample_raw}).json["project"]["id"]
    exported = json.loads(user.get(f"/api/projects/{pid}/export.json").get_data(as_text=True))
    r = user.post("/api/projects/import", json={"data": exported})
    assert r.status_code == 201
    assert user.post("/api/projects/import", json={"data": {"junk": 1}}).status_code == 400


def test_meta_endpoints(client):
    assert len(client.get("/api/meta/glossary").json["terms"]) > 30
    assert len(client.get("/api/meta/templates").json["templates"]) >= 4
    assert "tax" in client.get("/api/meta/rules").json
    assert len(client.get("/api/analyzers").json["analyzers"]) >= 12


def test_local_mode_needs_no_login(tmp_path):
    from smartrisk import create_app
    from conftest import Client
    app = create_app({"DATABASE": str(tmp_path / "l.db"), "AUTH_REQUIRED": False, "TESTING": True})
    c = Client(app)
    assert c.post("/api/projects", json={"template": "blank"}).status_code == 201
    assert c.get("/app").status_code == 200 or c.get("/app").status_code == 302


def test_security_headers(client):
    r = client.get("/")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"] and r.headers["X-Frame-Options"] == "DENY"
