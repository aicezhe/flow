"""Клиент Last.fm и синхронизация. HTTP только здесь."""
import requests

from . import config, storage

API_URL = "https://ws.audioscrobbler.com/2.0/"
PAGE_LIMIT = 200   # максимум для user.getRecentTracks по документации
TIMEOUT = 30       # секунд на один запрос

MESSAGES = {
    "private": "This profile is private. Ask your friend to allow showing recent listening "
               "in their Last.fm privacy settings.",
    "not_found": "Last.fm user not found.",
    "error": "Could not reach Last.fm. Please try again later.",
}


class LastfmError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _error_from_code(code: int, message: str) -> LastfmError:
    # В документации Last.fm 6 = «неверные параметры», 17 = «нужен логин». Но на практике
    # 6 приходит для несуществующего ника, а 17 для закрытого профиля. Это поведение
    # не задокументировано, поэтому оно изолировано здесь.
    if code == 6:
        return LastfmError("not_found", MESSAGES["not_found"])
    if code == 17:
        return LastfmError("private", MESSAGES["private"])
    if code == 29:
        return LastfmError("error", "Last.fm asks you to wait (rate limit). Try again in a minute.")
    if code == 10:
        return LastfmError("error", "Last.fm rejected the API key. Check LASTFM_KEY.")
    return LastfmError("error", f"Last.fm returned error {code}: {message}")


def _call(method: str, api_key: str, timeout: float = TIMEOUT, **params) -> dict:
    r = requests.get(API_URL, params={"method": method, "api_key": api_key,
                                      "format": "json", **params}, timeout=timeout)
    try:
        data = r.json()
    except ValueError:
        data = None
    # Ошибки Last.fm приходят с HTTP 4xx и JSON-телом, поэтому тело читаем до raise_for_status.
    if isinstance(data, dict) and "error" in data:
        raise _error_from_code(int(data["error"]), str(data.get("message", "")))
    r.raise_for_status()
    if not isinstance(data, dict):
        raise LastfmError("error", "Last.fm returned a response that is not JSON.")
    return data


def fetch_recent_tracks(username: str, api_key: str, since_ts: int = 0):
    """Генерирует (artist, track, ts). Идёт по страницам до totalPages."""
    page = 1
    while True:
        params = {"user": username, "limit": PAGE_LIMIT, "page": page}
        if since_ts:
            # Включительность from в документации не указана; дубли отсекает UNIQUE.
            params["from"] = since_ts
        block = _call("user.getRecentTracks", api_key, **params)["recenttracks"]
        tracks = block.get("track", [])
        if isinstance(tracks, dict):   # на всякий случай: один трек вместо списка
            tracks = [tracks]
        for t in tracks:
            if "date" not in t:        # «играет сейчас», в историю ещё не попало
                continue
            yield t["artist"]["#text"].lower(), t["name"], int(t["date"]["uts"])
        if page >= int(block["@attr"]["totalPages"]):
            break
        page += 1


def verify_user(username: str, api_key: str | None = None) -> str:
    """Проверяет, что ник существует; возвращает его написание из Last.fm."""
    data = _call("user.getInfo", api_key or config.lastfm_key(), user=username)
    return data["user"]["name"]


def verify_public_user(username: str, api_key: str | None = None) -> str:
    """Для публичной заявки: ник существует И недавние прослушивания открыты.
    user.getInfo приватность не показывает, поэтому дополнительно просим один трек.
    Возвращает написание ника из Last.fm. Короткий таймаут: этот путь открыт всем."""
    key = api_key or config.lastfm_key()
    canonical = _call("user.getInfo", key, timeout=10, user=username)["user"]["name"]
    _call("user.getRecentTracks", key, timeout=10, user=canonical, limit=1)
    return canonical


def sync_user(conn, username: str, api_key: str | None = None) -> dict:
    api_key = api_key or config.lastfm_key()
    try:
        since = storage.last_ts(conn, username)
        # Сначала скачиваем всё, потом пишем: страницы идут от новых к старым, и при обрыве
        # посередине сохранённый MAX(ts) «перепрыгнул» бы недогруженные старые прослушивания.
        rows = list(fetch_recent_tracks(username, api_key, since))
        added = storage.insert_scrobbles(conn, username, rows)
    except LastfmError as e:
        storage.set_status(conn, username, e.status, e.message)
        return {"username": username, "added": 0, "status": e.status, "error": e.message}
    except (requests.RequestException, KeyError, ValueError, TypeError):
        storage.set_status(conn, username, "error", MESSAGES["error"])
        return {"username": username, "added": 0, "status": "error", "error": MESSAGES["error"]}
    storage.set_status(conn, username, "ok")
    return {"username": username, "added": added, "status": "ok"}


def sync_all(conn, usernames: list[str] | None = None, api_key: str | None = None) -> list[dict]:
    api_key = api_key or config.lastfm_key()
    if usernames is None:
        usernames = [p["username"] for p in storage.list_people(conn)]
    return [sync_user(conn, u, api_key) for u in usernames]
