"""Весь SQL проекта. Остальные модули SQL не пишут."""
import sqlite3
import time
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS scrobbles(
  user TEXT, artist TEXT, track TEXT, ts INTEGER,
  UNIQUE(user, ts, artist, track));
CREATE TABLE IF NOT EXISTS people(
  username TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  added_at INTEGER NOT NULL,
  last_synced_at INTEGER,
  status TEXT NOT NULL DEFAULT 'ok',
  error TEXT);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path) if path else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Люди, чьи прослушивания уже лежат в базе от старого скрипта, появляются в списке.
    conn.execute(
        "INSERT OR IGNORE INTO people(username, display_name, added_at) "
        "SELECT DISTINCT user, user, ? FROM scrobbles", (int(time.time()),))
    conn.commit()
    return conn


# ---------- people ----------

def add_person(conn, username: str, display_name: str) -> None:
    conn.execute(
        "INSERT INTO people(username, display_name, added_at) VALUES (?,?,?) "
        "ON CONFLICT(username) DO UPDATE SET display_name=excluded.display_name",
        (username, display_name, int(time.time())))
    conn.commit()


def get_person(conn, username: str) -> dict | None:
    row = conn.execute("SELECT * FROM people WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def list_people(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT p.username, p.display_name, COUNT(s.ts) AS plays, "
        "       p.last_synced_at, p.status, p.error "
        "FROM people p LEFT JOIN scrobbles s ON s.user = p.username "
        "GROUP BY p.username ORDER BY p.added_at, p.username").fetchall()
    return [dict(r) for r in rows]


def set_status(conn, username: str, status: str, error: str | None = None) -> None:
    """last_synced_at обновляется только после успешной загрузки."""
    if status == "ok":
        conn.execute("UPDATE people SET status='ok', error=NULL, last_synced_at=? WHERE username=?",
                     (int(time.time()), username))
    else:
        conn.execute("UPDATE people SET status=?, error=? WHERE username=?",
                     (status, error, username))
    conn.commit()


def delete_person(conn, username: str) -> bool:
    """Удаляет человека и все его прослушивания в одной транзакции."""
    with conn:
        conn.execute("DELETE FROM scrobbles WHERE user=?", (username,))
        cur = conn.execute("DELETE FROM people WHERE username=?", (username,))
    return cur.rowcount > 0


# ---------- scrobbles ----------

def last_ts(conn, username: str) -> int:
    return conn.execute("SELECT COALESCE(MAX(ts),0) FROM scrobbles WHERE user=?",
                        (username,)).fetchone()[0]


def insert_scrobbles(conn, username: str, rows: list[tuple[str, str, int]]) -> int:
    """rows: (artist, track, ts). Возвращает, сколько строк реально добавлено."""
    before = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO scrobbles(user, artist, track, ts) VALUES (?,?,?,?)",
                     [(username, a, t, ts) for a, t, ts in rows])
    conn.commit()
    return conn.total_changes - before


def all_scrobbles(conn) -> list[tuple[str, str, str, int]]:
    return [tuple(r) for r in conn.execute("SELECT user, artist, track, ts FROM scrobbles")]
