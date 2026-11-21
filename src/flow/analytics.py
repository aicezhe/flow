"""Чистые функции: данные на входе, словари на выходе. Без SQL и HTTP.

Вход везде: rows = [(user, artist, track, ts), ...], ts в секундах UNIX.
"""
from collections import Counter, defaultdict
from datetime import datetime, tzinfo

TOP_ARTISTS = 10      # столбиков на человека
MATRIX_ARTISTS = 25   # артистов в матрице


def plays_by_user(rows) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for user, artist, _track, _ts in rows:
        out[user][artist] += 1
    return dict(out)


def jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def hours_histogram(timestamps, tz: tzinfo | None = None) -> list[int]:
    """24 числа: сколько прослушиваний в каждый час суток. tz=None значит локальное время."""
    hours = [0] * 24
    for ts in timestamps:
        hours[datetime.fromtimestamp(ts, tz).hour] += 1
    return hours


def summary(rows) -> dict:
    plays = plays_by_user(rows)
    artists = {a for c in plays.values() for a in c}
    nnz = sum(len(c) for c in plays.values())
    cells = len(plays) * len(artists)
    ts = [r[3] for r in rows]
    return {
        "people": len(plays),
        "plays": len(rows),
        "artists": len(artists),
        # доля непустых ячеек в матрице «человек x артист»
        "density_percent": round(100 * nnz / cells, 1) if cells else 0.0,
        "first_ts": min(ts) if ts else None,
        "last_ts": max(ts) if ts else None,
    }


def user_stats(user: str, rows, top_n: int = TOP_ARTISTS, tz: tzinfo | None = None) -> dict:
    mine = [r for r in rows if r[0] == user]
    counts = Counter(r[1] for r in mine)
    ts = [r[3] for r in mine]
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    return {
        "name": user,
        "plays": len(mine),
        "artists": len(counts),
        "heard_once": sum(1 for v in counts.values() if v == 1),
        "first_ts": min(ts) if ts else None,
        "last_ts": max(ts) if ts else None,
        "top_artists": [{"artist": a, "plays": n} for a, n in top],
        "hours": hours_histogram(ts, tz),
    }


def similarity(plays: dict[str, Counter]) -> dict:
    users = sorted(plays)
    sets = {u: set(plays[u]) for u in users}
    return {"users": users,
            "matrix": [[jaccard(sets[a], sets[b]) for b in users] for a in users]}


def shared_artists(plays: dict[str, Counter], a: str, b: str, limit: int = 8) -> list[str]:
    common = set(plays[a]) & set(plays[b])
    return sorted(common, key=lambda x: (-(plays[a][x] + plays[b][x]), x))[:limit]


def matrix(plays: dict[str, Counter], top_n: int = MATRIX_ARTISTS) -> dict:
    """plays[i][j] = прослушиваний у человека i артиста j; артисты по убыванию суммы."""
    users = sorted(plays)
    totals: Counter = Counter()
    for c in plays.values():
        totals.update(c)
    artists = [a for a, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]]
    return {"users": users, "artists": artists,
            "plays": [[plays[u].get(a, 0) for a in artists] for u in users]}


def build_report(rows, generated_at: int, tz: tzinfo | None = None) -> dict:
    plays = plays_by_user(rows)
    return {
        "generated_at": generated_at,
        "summary": summary(rows),
        "users": [user_stats(u, rows, tz=tz) for u in sorted(plays)],
        "similarity": similarity(plays),
        "matrix": matrix(plays),
    }
