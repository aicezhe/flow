# scripts/migrate_sqlite_to_pg.py: разовый перенос data/flow.db (SQLite) в PostgreSQL.
#
#   DATABASE_URL=postgresql://localhost/flow python scripts/migrate_sqlite_to_pg.py            # пробный прогон
#   DATABASE_URL=postgresql://localhost/flow python scripts/migrate_sqlite_to_pg.py --apply    # записать
#
# Безопасно по умолчанию: без --apply всё выполняется и проверяется в транзакции, которая
# откатывается. Удалённая база (не localhost) требует ещё и --allow-remote. Строка подключения
# содержит пароль, поэтому скрипт её никогда не печатает. Схему (db/schema.sql) нужно применить заранее.
import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import psycopg  # noqa: E402
from psycopg.conninfo import conninfo_to_dict  # noqa: E402

from flow import analytics, config  # noqa: E402

BATCH = 5000
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def is_local(url: str) -> bool:
    host = (conninfo_to_dict(url).get("host") or "").split(",")[0]
    return host in LOCAL_HOSTS or host.startswith("/")


def has_table(src: sqlite3.Connection, name: str) -> bool:
    return src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def read_source(path: Path):
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)  # только чтение
    scrobbles = src.execute("SELECT user, artist, track, ts FROM scrobbles ORDER BY ts").fetchall()
    people = []
    if has_table(src, "people"):
        people = src.execute("SELECT username, display_name, added_at, last_synced_at, status, error "
                             "FROM people ORDER BY added_at, username").fetchall()
    signups = []
    if has_table(src, "signup_requests"):
        signups = src.execute("SELECT username, contact, consent_at, created_at, status, decided_at "
                              "FROM signup_requests ORDER BY id").fetchall()
    src.close()
    # Как раньше делал connect(): каждый, у кого есть прослушивания, должен быть в people.
    known = {p[0] for p in people}
    now = int(datetime.now(timezone.utc).timestamp())
    orphans = sorted({r[0] for r in scrobbles} - known)
    people += [(u, u, now, None, "ok", None) for u in orphans]
    return people, scrobbles, signups, orphans


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sqlite", type=Path, default=None, help="путь к flow.db (по умолчанию из настроек)")
    ap.add_argument("--apply", action="store_true", help="записать (иначе пробный прогон с откатом)")
    ap.add_argument("--allow-remote", action="store_true", help="разрешить не-локальную базу (Supabase и т.п.)")
    args = ap.parse_args()

    try:
        url = config.database_url()
    except RuntimeError as e:
        return print(e) or 2
    local = is_local(url)
    if not local and not args.allow_remote:
        print("Целевая база не локальная. Если это намеренно, добавьте --allow-remote.")
        return 2
    path = args.sqlite or config.db_path()
    if not path.exists():
        print(f"Нет файла SQLite: {path}")
        return 2

    people, scrobbles, signups, orphans = read_source(path)
    migrated_at = datetime.now(timezone.utc)  # consent_at всех перенесённых людей
    print(f"Источник: {path.name}: людей {len(people)} (из прослушиваний добавлено {len(orphans)}), "
          f"прослушиваний {len(scrobbles)}, заявок {len(signups)}")
    print(f"Приёмник: {'локальная база' if local else 'УДАЛЁННАЯ база (адрес скрыт)'}; "
          f"режим: {'ЗАПИСЬ' if args.apply else 'пробный прогон (откат)'}")

    usernames = [p[0] for p in people]
    with psycopg.connect(url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO people(username, display_name, consent_at, created_at, last_synced_at, status, error) "
                "VALUES (%s, %s, %s, to_timestamp(%s), to_timestamp(%s), %s, %s) ON CONFLICT (username) DO NOTHING",
                [(u, d, migrated_at, added, synced, st, err) for u, d, added, synced, st, err in people])
            for i in range(0, len(scrobbles), BATCH):
                cur.executemany(
                    "INSERT INTO scrobbles(username, artist, track, ts) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING", scrobbles[i:i + BATCH])
            cur.execute("SELECT count(*) FROM signup_requests")
            if cur.fetchone()[0] == 0:  # у заявок нет естественного ключа: грузим только в пустую таблицу
                cur.executemany(
                    "INSERT INTO signup_requests(username, contact, consent_at, created_at, status, decided_at) "
                    "VALUES (%s, %s, to_timestamp(%s), to_timestamp(%s), %s, to_timestamp(%s))", signups)
            else:
                print("signup_requests в приёмнике не пуста: заявки не переносились")

            # ---------- сверка ----------
            problems = []
            cur.execute("SELECT username, count(*), max(ts) FROM scrobbles WHERE username = ANY(%s) GROUP BY 1",
                        (usernames,))
            dst = {u: (n, m) for u, n, m in cur.fetchall()}
            src: dict[str, list] = {}
            for u, _a, _t, ts in scrobbles:
                s = src.setdefault(u, [0, 0])
                s[0] += 1
                s[1] = max(s[1], ts)
            for u, (n, m) in src.items():
                if dst.get(u) != (n, m):
                    problems.append(f"{u}: в SQLite {(n, m)}, в Postgres {dst.get(u)}")
            cur.execute("SELECT count(*) FROM people WHERE username = ANY(%s)", (usernames,))
            if cur.fetchone()[0] != len(usernames):
                problems.append("не все люди перенесены")
            # Главная проверка: отчёт, посчитанный по обеим базам, должен совпасть целиком.
            cur.execute("SELECT username, artist, track, ts FROM scrobbles WHERE username = ANY(%s)", (usernames,))
            rep_src = analytics.build_report(scrobbles, 0, tz=timezone.utc)
            rep_dst = analytics.build_report(cur.fetchall(), 0, tz=timezone.utc)
            if rep_src != rep_dst:
                problems.append("отчёты analytics.build_report по двум базам различаются")

        if problems:
            conn.rollback()
            print("СВЕРКА НЕ ПРОШЛА, откат:\n  " + "\n  ".join(problems))
            return 1
        print(f"Сверка пройдена: счётчики, MAX(ts) по каждому человеку и весь отчёт совпали "
              f"({len(src)} чел., {len(scrobbles)} прослушиваний).")
        if args.apply:
            conn.commit()
            print(f"Записано. consent_at у перенесённых людей: {migrated_at:%Y-%m-%d %H:%M} UTC (время миграции).")
        else:
            conn.rollback()
            print("Пробный прогон: ничего не записано. Для записи добавьте --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
