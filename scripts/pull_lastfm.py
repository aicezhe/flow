# scripts/pull_lastfm.py: тонкая обёртка над flow.lastfm
# Запуск из папки проекта:  LASTFM_KEY=... python scripts/pull_lastfm.py [ник ...]
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flow import lastfm, storage  # noqa: E402

SEED_USERS = ["aicezhe"]   # как раньше; друзей лучше добавлять через веб-приложение

if __name__ == "__main__":
    conn = storage.connect()
    names = sys.argv[1:] or SEED_USERS
    for name in names:
        if not storage.get_person(conn, name):
            storage.add_person(conn, name, name)
    # без аргументов синхронизируем всех, кто есть в базе
    try:
        results = lastfm.sync_all(conn, names if sys.argv[1:] else None)
    except RuntimeError as e:   # нет LASTFM_KEY
        sys.exit(str(e))
    for r in results:
        print(r["username"], r["status"], f"+{r['added']}", r.get("error", ""))
