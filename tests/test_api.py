"""TestClient на временной базе. Сеть запрещена: любой реальный HTTP-вызов роняет тест."""
import pytest
import requests
from fastapi.testclient import TestClient

from flow import lastfm, storage
from flow.api import create_app
from flow.auth import Auth

PIN = "1234-test"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("ADMIN_PIN", PIN)
    monkeypatch.setenv("LASTFM_KEY", "test-key")

    def no_network(*a, **k):
        raise AssertionError("тест попытался сходить в сеть")
    monkeypatch.setattr(lastfm.requests, "get", no_network)


def fake_lastfm(monkeypatch, *responses):
    it = iter(responses)
    monkeypatch.setattr(lastfm.requests, "get", lambda *a, **k: next(it))


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def authed(client):
    token = client.post("/api/auth", json={"pin": PIN}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ---------- вход ----------

def test_health_is_open(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_wrong_pin_401(client):
    assert client.post("/api/auth", json={"pin": "nope"}).status_code == 401


def test_admin_disabled_without_pin_503(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PIN")
    assert client.post("/api/auth", json={"pin": ""}).status_code == 503
    assert client.post("/api/auth", json={"pin": "anything"}).status_code == 503


def test_report_without_token_401(client):
    assert client.get("/api/report").status_code == 401
    assert client.get("/api/report", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_good_pin_gives_token_and_report_200(authed):
    r = authed.get("/api/report")
    assert r.status_code == 200
    assert set(r.json()) == {"generated_at", "summary", "users", "similarity", "matrix"}


def test_sixth_attempt_in_a_minute_429(client):
    codes = [client.post("/api/auth", json={"pin": "bad"}).status_code for _ in range(5)]
    assert codes == [401] * 5
    assert client.post("/api/auth", json={"pin": "bad"}).status_code == 429
    assert client.post("/api/auth", json={"pin": PIN}).status_code == 429  # и верный PIN тоже


def test_every_api_route_except_health_and_auth_requires_token(client):
    """Страховка: новый адрес нельзя случайно оставить открытым."""
    checked = 0
    for path, methods in client.app.openapi()["paths"].items():
        if not path.startswith("/api") or path in ("/api/health", "/api/auth"):
            continue
        for method in methods:
            r = client.request(method.upper(), path.replace("{username}", "x"))
            assert r.status_code == 401, (method, path)
            checked += 1
    assert checked >= 5


def test_cors_only_for_vite_origin(client):
    ok = client.options("/api/people", headers={"Origin": "http://localhost:5173",
                                                "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/people", headers={"Origin": "http://evil.example",
                                                 "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_token_expires_after_12_hours():
    now = [0.0]
    a = Auth(clock=lambda: now[0])
    t = a.issue_token()
    assert a.is_valid(t)
    now[0] = 12 * 3600 - 1
    assert a.is_valid(t)
    now[0] = 12 * 3600 + 1
    assert not a.is_valid(t)


# ---------- люди ----------

def test_add_list_delete_person(authed, monkeypatch):
    fake_lastfm(monkeypatch, FakeResponse({"user": {"name": "Bob_FM"}}))
    r = authed.post("/api/people", json={"username": "bob_fm", "display_name": "Боб"})
    assert r.status_code == 201
    assert r.json()["username"] == "Bob_FM" and r.json()["display_name"] == "Боб"
    assert r.json()["plays"] == 0 and r.json()["status"] == "ok"

    conn = storage.connect()
    storage.insert_scrobbles(conn, "Bob_FM", [("a", "t", 1)])
    assert authed.get("/api/people").json()[0]["plays"] == 1

    assert authed.delete("/api/people/Bob_FM").status_code == 204
    assert authed.get("/api/people").json() == []
    assert storage.all_scrobbles(conn) == []          # прослушивания тоже удалены
    assert authed.delete("/api/people/Bob_FM").status_code == 404


def test_add_unknown_user_404(authed, monkeypatch):
    fake_lastfm(monkeypatch, FakeResponse({"error": 6, "message": "User not found"}, 404))
    r = authed.post("/api/people", json={"username": "ghost", "display_name": "X"})
    assert r.status_code == 404 and "не найден" in r.json()["detail"]


def test_add_duplicate_409(authed, monkeypatch):
    fake_lastfm(monkeypatch, FakeResponse({"user": {"name": "bob"}}),
                FakeResponse({"user": {"name": "bob"}}))
    assert authed.post("/api/people", json={"username": "bob"}).status_code == 201
    assert authed.post("/api/people", json={"username": "bob"}).status_code == 409


def test_add_rejects_weird_username_422(authed):
    assert authed.post("/api/people", json={"username": "a b/../c"}).status_code == 422


# ---------- sync и отчёт ----------

def test_sync_reports_per_person_status(authed, monkeypatch):
    storage.add_person(storage.connect(), "closed", "Closed")
    fake_lastfm(monkeypatch, FakeResponse({"error": 17, "message": "login"}, 403))
    r = authed.post("/api/sync", json={"username": "closed"})
    assert r.status_code == 200
    res = r.json()["results"]
    assert res[0]["username"] == "closed" and res[0]["status"] == "private" and res[0]["error"]
    assert authed.get("/api/people").json()[0]["status"] == "private"


def test_sync_unknown_person_404(authed):
    assert authed.post("/api/sync", json={"username": "nobody"}).status_code == 404


def test_sync_without_body_runs_for_everyone(authed, monkeypatch):
    conn = storage.connect()
    storage.add_person(conn, "a", "A")
    storage.add_person(conn, "b", "B")
    empty = {"recenttracks": {"track": [], "@attr": {"totalPages": "0"}}}
    fake_lastfm(monkeypatch, FakeResponse(empty), FakeResponse(empty))
    r = authed.post("/api/sync")
    assert [x["status"] for x in r.json()["results"]] == ["ok", "ok"]


def test_report_contract(authed):
    conn = storage.connect()
    storage.insert_scrobbles(conn, "anna", [("a", "t1", 1704067200), ("b", "t2", 1704070800)])
    storage.insert_scrobbles(conn, "bob", [("a", "t1", 1704067300)])
    rep = authed.get("/api/report").json()
    assert rep["summary"]["people"] == 2 and rep["summary"]["plays"] == 3
    u = rep["users"][0]
    assert set(u) == {"name", "plays", "artists", "heard_once", "first_ts", "last_ts",
                      "top_artists", "hours"}
    assert len(u["hours"]) == 24
    assert rep["similarity"]["users"] == ["anna", "bob"]
    assert rep["matrix"]["users"] == ["anna", "bob"] and rep["matrix"]["artists"][0] == "a"
