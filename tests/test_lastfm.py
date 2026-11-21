"""Разбор ответов Last.fm с замоканным HTTP: сеть не нужна."""
import pytest
import requests

from flow import lastfm, storage


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def track(artist, name, uts=None):
    t = {"artist": {"#text": artist}, "name": name}
    if uts is not None:
        t["date"] = {"uts": str(uts)}
    return t


def page(tracks, total_pages, number=1):
    return FakeResponse({"recenttracks": {"track": tracks,
                         "@attr": {"page": str(number), "totalPages": str(total_pages)}}})


@pytest.fixture
def conn(tmp_path):
    c = storage.connect(tmp_path / "t.db")
    storage.add_person(c, "anna", "Anna")
    return c


def mock_get(monkeypatch, responses):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        r = responses[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(lastfm.requests, "get", fake_get)
    return calls


def test_skips_now_playing_and_paginates(monkeypatch, conn):
    calls = mock_get(monkeypatch, [
        page([track("Radiohead", "Now Playing"), track("Radiohead", "Karma Police", 200)], 2, 1),
        page([track("Björk", "Hyperballad", 100)], 2, 2),
    ])
    res = lastfm.sync_user(conn, "anna", "KEY")
    assert res == {"username": "anna", "added": 2, "status": "ok"}
    assert [c["page"] for c in calls] == [1, 2]            # по totalPages
    assert storage.all_scrobbles(conn) == [("anna", "radiohead", "Karma Police", 200),
                                           ("anna", "björk", "Hyperballad", 100)]


def test_incremental_from_and_dedup(monkeypatch, conn):
    storage.insert_scrobbles(conn, "anna", [("radiohead", "Karma Police", 200)])
    calls = mock_get(monkeypatch, [page([track("Radiohead", "Karma Police", 200),
                                         track("Radiohead", "Creep", 300)], 1)])
    res = lastfm.sync_user(conn, "anna", "KEY")
    assert calls[0]["from"] == 200
    assert res["added"] == 1                                # дубль отброшен UNIQUE


def test_first_sync_has_no_from(monkeypatch, conn):
    calls = mock_get(monkeypatch, [page([], 0)])
    lastfm.sync_user(conn, "anna", "KEY")
    assert "from" not in calls[0]


def test_private_profile(monkeypatch, conn):
    mock_get(monkeypatch, [FakeResponse({"error": 17, "message": "Login: User required to be logged in"}, 403)])
    res = lastfm.sync_user(conn, "anna", "KEY")
    assert res["status"] == "private" and res["added"] == 0 and res["error"]
    p = storage.get_person(conn, "anna")
    assert p["status"] == "private" and p["error"] and p["last_synced_at"] is None


def test_not_found(monkeypatch, conn):
    mock_get(monkeypatch, [FakeResponse({"error": 6, "message": "User not found"}, 404)])
    assert lastfm.sync_user(conn, "anna", "KEY")["status"] == "not_found"


def test_one_failure_does_not_stop_others(monkeypatch, conn):
    storage.add_person(conn, "bob", "Bob")
    mock_get(monkeypatch, [requests.ConnectionError("down"),
                           page([track("Radiohead", "Creep", 5)], 1)])
    results = lastfm.sync_all(conn, ["anna", "bob"], "KEY")
    assert [r["status"] for r in results] == ["error", "ok"]
    assert results[1]["added"] == 1


def test_verify_user(monkeypatch):
    mock_get(monkeypatch, [FakeResponse({"user": {"name": "Anna_FM"}})])
    assert lastfm.verify_user("anna_fm", "KEY") == "Anna_FM"
