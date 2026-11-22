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
    monkeypatch.setenv("SIGNUP_ENABLED", "1")

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
        if not path.startswith("/api") or path in ("/api/health", "/api/auth", "/api/signup"):
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
    assert r.status_code == 404 and "not found" in r.json()["detail"].lower()


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


# ---------- публичные заявки ----------

OK_INFO = FakeResponse({"user": {"name": "Friend_FM"}})
OK_RECENT = FakeResponse({"recenttracks": {"track": [], "@attr": {"totalPages": "0"}}})
GOOD = {"username": "friend_fm", "consent": True}


def signups_in_db():
    return storage.connect().execute("SELECT username, contact, status, consent_at FROM signup_requests").fetchall()


def test_signup_ok_saves_pending_with_consent_time(client, monkeypatch):
    fake_lastfm(monkeypatch, OK_INFO, OK_RECENT)
    r = client.post("/api/signup", json={**GOOD, "contact": " @friend "})
    assert r.status_code == 200 and r.json() == {"status": "received"}
    (row,) = signups_in_db()
    assert row["username"] == "Friend_FM" and row["status"] == "pending"
    assert row["contact"] == "@friend" and row["consent_at"] > 0


def test_signup_unknown_user_404(client, monkeypatch):
    fake_lastfm(monkeypatch, FakeResponse({"error": 6, "message": "User not found"}, 404))
    r = client.post("/api/signup", json=GOOD)
    assert r.status_code == 404 and "not found" in r.json()["detail"].lower()
    assert signups_in_db() == []


def test_signup_private_profile_403(client, monkeypatch):
    fake_lastfm(monkeypatch, OK_INFO, FakeResponse({"error": 17, "message": "login"}, 403))
    r = client.post("/api/signup", json=GOOD)
    assert r.status_code == 403 and "private" in r.json()["detail"].lower()
    assert signups_in_db() == []


def test_signup_without_consent_400_and_no_lastfm_call(client):
    # сеть в этом файле запрещена: любой вызов Last.fm уронил бы тест
    for body in ({"username": "friend_fm"}, {"username": "friend_fm", "consent": False}):
        r = client.post("/api/signup", json=body)
        assert r.status_code == 400 and "consent" in r.json()["detail"].lower()
    assert signups_in_db() == []


def test_signup_duplicate_same_answer_one_row(client, monkeypatch):
    fake_lastfm(monkeypatch, OK_INFO, OK_RECENT, OK_INFO, OK_RECENT)
    first = client.post("/api/signup", json=GOOD)
    second = client.post("/api/signup", json=GOOD)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    assert len(signups_in_db()) == 1


def test_signup_existing_person_same_answer_nothing_created(client, monkeypatch):
    storage.add_person(storage.connect(), "Friend_FM", "Friend_FM")
    fake_lastfm(monkeypatch, OK_INFO, OK_RECENT)
    r = client.post("/api/signup", json=GOOD)
    assert r.status_code == 200 and r.json() == {"status": "received"}
    assert signups_in_db() == []


def test_signup_honeypot_silent_success(client):
    r = client.post("/api/signup", json={**GOOD, "website": "http://spam.example"})
    assert r.status_code == 200 and r.json() == {"status": "received"}
    assert signups_in_db() == []


def test_signup_length_limits(client):
    assert client.post("/api/signup", json={**GOOD, "contact": "x" * 101}).status_code == 422
    assert client.post("/api/signup", json={**GOOD, "username": "a" * 65}).status_code == 422
    assert client.post("/api/signup", json={**GOOD, "contact": "x" * 5000}).status_code in (413, 422)


def test_signup_rate_limit_429(client, monkeypatch):
    fake_lastfm(monkeypatch, *[OK_INFO, OK_RECENT] * 5)
    assert [client.post("/api/signup", json=GOOD).status_code for _ in range(5)] == [200] * 5
    assert client.post("/api/signup", json=GOOD).status_code == 429


def test_signup_disabled_404(client, monkeypatch):
    monkeypatch.delenv("SIGNUP_ENABLED")
    assert client.post("/api/signup", json=GOOD).status_code == 404


def test_signup_pending_cap_503(client, monkeypatch):
    conn = storage.connect()
    for i in range(50):
        storage.create_signup(conn, f"user{i}", None, 1)
    assert client.post("/api/signup", json=GOOD).status_code == 503


def test_public_endpoints_leak_nothing(client, monkeypatch):
    storage.add_person(storage.connect(), "secret_person", "Secret")
    storage.insert_scrobbles(storage.connect(), "secret_person", [("secret artist", "t", 1)])
    fake_lastfm(monkeypatch, OK_INFO, OK_RECENT)
    bodies = [client.get("/api/health").text, client.post("/api/signup", json=GOOD).text]
    assert client.get("/api/health").json() == {"status": "ok"}
    for text in bodies:
        assert "secret" not in text.lower()
    for path in ("/api/people", "/api/signups", "/api/report"):
        assert client.get(path).status_code == 401


# ---------- админка заявок ----------

def make_signup(contact="@f"):
    conn = storage.connect()
    storage.create_signup(conn, "Friend_FM", contact, 100)
    return conn.execute("SELECT id FROM signup_requests").fetchone()["id"]


def test_signups_list_requires_token_and_lists_pending(client, authed):
    make_signup()
    r = authed.get("/api/signups")
    assert r.status_code == 200 and r.json()[0]["username"] == "Friend_FM"


def test_approve_moves_to_people_and_clears_contact(authed):
    sid = make_signup()
    assert authed.post(f"/api/signups/{sid}/approve").json() == {"id": sid, "status": "approved"}
    assert [p["username"] for p in authed.get("/api/people").json()] == ["Friend_FM"]
    assert authed.get("/api/signups").json() == []
    assert signups_in_db()[0]["contact"] is None
    assert authed.post(f"/api/signups/{sid}/approve").status_code == 409


def test_reject_changes_status_not_people(authed):
    sid = make_signup()
    assert authed.post(f"/api/signups/{sid}/reject").json()["status"] == "rejected"
    assert authed.get("/api/people").json() == []
    row = signups_in_db()[0]
    assert row["status"] == "rejected" and row["contact"] is None


def test_decide_unknown_signup_404(authed):
    assert authed.post("/api/signups/999/approve").status_code == 404


def test_delete_person_removes_their_signups(authed):
    sid = make_signup()
    authed.post(f"/api/signups/{sid}/approve")
    assert authed.delete("/api/people/Friend_FM").status_code == 204
    assert signups_in_db() == []


# ---------- раздача собранного фронтенда ----------

def test_serves_built_frontend_without_shadowing_api(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Flow</title>")
    c = TestClient(create_app(static_dir=tmp_path))
    assert "<title>Flow</title>" in c.get("/").text
    assert c.get("/api/health").json() == {"status": "ok"}       # API не перекрыт
    assert c.get("/api/report").status_code == 401               # защита на месте
    assert c.get("/docs").status_code == 200


def test_no_frontend_when_dist_missing(tmp_path):
    c = TestClient(create_app(static_dir=tmp_path / "nope"))
    assert c.get("/").status_code == 404
    assert c.get("/api/health").status_code == 200


# ---------- клиентские маршруты (SPA fallback) ----------

INDEX = "<!doctype html><title>Flow</title>"


@pytest.fixture
def spa(tmp_path):
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    return TestClient(create_app(static_dir=tmp_path))


@pytest.mark.parametrize("path", ["/", "/guestform", "/guestform/", "/guestform?invite=abc123", "/some/client/route"])
def test_client_routes_serve_index(spa, path):
    """Прямая ссылка и обновление страницы на /guestform не должны давать 404."""
    r = spa.get(path)
    assert r.status_code == 200
    assert "<title>Flow</title>" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_existing_static_file_is_served_as_is(spa):
    r = spa.get("/assets/app.js")
    assert r.status_code == 200 and "console.log('app')" in r.text


def test_missing_asset_is_404_not_index(spa):
    """Пропавший скрипт должен быть 404, а не HTML вместо JavaScript."""
    r = spa.get("/assets/missing.js")
    assert r.status_code == 404 and "<title>" not in r.text


@pytest.mark.parametrize("path", ["/api/nope", "/api/people/x/y", "/api"])
def test_unknown_api_paths_are_404_not_index(spa, path):
    """API не перехватывается фолбэком: клиентам API нужен честный 404."""
    r = spa.get(path)
    assert r.status_code in (404, 401) and "<title>" not in r.text


def test_api_and_docs_not_shadowed_by_fallback(spa):
    assert spa.get("/api/health").json() == {"status": "ok"}
    assert spa.get("/api/report").status_code == 401          # закрыто токеном, а не HTML
    assert spa.get("/docs").status_code == 200 and "swagger" in spa.get("/docs").text.lower()


def test_guestform_is_404_without_a_build(tmp_path):
    c = TestClient(create_app(static_dir=tmp_path / "nope"))
    assert c.get("/guestform").status_code == 404
    assert c.get("/api/health").status_code == 200


def test_invite_param_is_ignored_by_server_routing(spa):
    """Код приглашения читает фронтенд; сервер просто отдаёт страницу, ничего о коде не зная."""
    assert spa.get("/guestform?invite=wrong").text == spa.get("/guestform").text
