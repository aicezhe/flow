"""Мини-пример, посчитанный руками: 3 человека, 4 артиста, 14 прослушиваний.

          a  b  c  d  | всего
  alice   3  1  0  0  |  4
  bob     1  0  2  1  |  4
  carol   0  2  0  4  |  6
  всего   4  3  2  5  | 14

Непустых ячеек 2+3+2 = 7 из 3*4 = 12, плотность 58.3%.
Jaccard: alice-bob {a}/{a,b,c,d} = 1/4; alice-carol {b}/{a,b,d} = 1/3; bob-carol {d}/{a,b,c,d} = 1/4.
Матрица: артисты по сумме: d(5), a(4), b(3), c(2).
"""
from datetime import timezone

import pytest

from flow import analytics

BASE = 1704067200  # 2024-01-01 00:00:00 UTC


def t(day, hour):
    return BASE + day * 86400 + hour * 3600


ROWS = [
    ("alice", "a", "t1", t(0, 9)), ("alice", "a", "t2", t(0, 9)),
    ("alice", "a", "t1", t(1, 21)), ("alice", "b", "t3", t(2, 10)),
    ("bob", "a", "t1", t(1, 9)), ("bob", "c", "t4", t(1, 9)),
    ("bob", "c", "t4", t(3, 8)), ("bob", "d", "t5", t(3, 8)),
    ("carol", "b", "t3", t(2, 0)), ("carol", "b", "t3", t(4, 23)),
    ("carol", "d", "t5", t(2, 1)), ("carol", "d", "t5", t(3, 2)),
    ("carol", "d", "t5", t(3, 3)), ("carol", "d", "t5", t(4, 4)),
]


def test_jaccard():
    assert analytics.jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert analytics.jaccard({"a"}, {"a"}) == 1.0
    assert analytics.jaccard({"a"}, {"b"}) == 0.0
    assert analytics.jaccard(set(), set()) == 0.0


def test_hours_histogram():
    h = analytics.hours_histogram([t(0, 9), t(0, 9), t(1, 21), t(2, 10)], timezone.utc)
    assert len(h) == 24
    assert h[9] == 2 and h[10] == 1 and h[21] == 1
    assert sum(h) == 4


def test_summary():
    s = analytics.summary(ROWS)
    assert s == {"people": 3, "plays": 14, "artists": 4, "density_percent": 58.3,
                 "first_ts": t(0, 9), "last_ts": t(4, 23)}


def test_summary_empty():
    s = analytics.summary([])
    assert s["plays"] == 0 and s["density_percent"] == 0.0 and s["first_ts"] is None


def test_user_stats():
    alice = analytics.user_stats("alice", ROWS, tz=timezone.utc)
    assert alice["plays"] == 4 and alice["artists"] == 2 and alice["heard_once"] == 1
    assert alice["top_artists"] == [{"artist": "a", "plays": 3}, {"artist": "b", "plays": 1}]
    assert alice["first_ts"] == t(0, 9) and alice["last_ts"] == t(2, 10)
    assert alice["hours"][9] == 2
    assert analytics.user_stats("bob", ROWS)["heard_once"] == 2
    assert analytics.user_stats("carol", ROWS)["heard_once"] == 0


def test_similarity():
    sim = analytics.similarity(analytics.plays_by_user(ROWS))
    assert sim["users"] == ["alice", "bob", "carol"]
    m = sim["matrix"]
    assert m[0][0] == 1.0
    assert m[0][1] == pytest.approx(1 / 4)
    assert m[0][2] == pytest.approx(1 / 3)
    assert m[1][2] == pytest.approx(1 / 4)
    assert m[1][0] == m[0][1]


def test_matrix():
    m = analytics.matrix(analytics.plays_by_user(ROWS))
    assert m["users"] == ["alice", "bob", "carol"]
    assert m["artists"] == ["d", "a", "b", "c"]
    assert m["plays"] == [[0, 3, 1, 0], [1, 1, 0, 2], [4, 0, 2, 0]]


def test_matrix_top_n():
    m = analytics.matrix(analytics.plays_by_user(ROWS), top_n=2)
    assert m["artists"] == ["d", "a"]
    assert m["plays"] == [[0, 3], [1, 1], [4, 0]]


def test_shared_artists():
    plays = analytics.plays_by_user(ROWS)
    assert analytics.shared_artists(plays, "alice", "bob") == ["a"]
    assert analytics.shared_artists(plays, "alice", "carol") == ["b"]


def test_build_report_shape():
    r = analytics.build_report(ROWS, generated_at=123, tz=timezone.utc)
    assert set(r) == {"generated_at", "summary", "users", "similarity", "matrix"}
    assert r["generated_at"] == 123
    assert [u["name"] for u in r["users"]] == ["alice", "bob", "carol"]
