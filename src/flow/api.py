"""FastAPI: тонкий слой над storage, lastfm, analytics, auth.

Запуск (только локально):
    uvicorn flow.api:app --reload --host 127.0.0.1 --port 8000 --app-dir src
"""
import hmac
import time
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from . import analytics, config, lastfm, storage
from .auth import Auth, RateLimiter

# CORS: только адрес dev-сервера Vite.
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class SPAStaticFiles(StaticFiles):
    """Собранный фронтенд с запасным ответом для клиентских маршрутов (/guestform и т.п.):
    если файла нет, отдаём index.html, иначе прямая ссылка и обновление страницы дали бы 404.
    Не подменяем: /api/* (клиенты API ждут 404, а не HTML) и пути с расширением (/assets/x.js:
    пропавший файл должен быть 404, а не HTML вместо скрипта)."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            is_api = path == "api" or path.startswith("api/")
            has_extension = "." in path.rsplit("/", 1)[-1]
            if e.status_code != 404 or is_api or has_extension:
                raise
            return await super().get_response("index.html", scope)


# ---------- зависимости ----------

def get_conn():
    conn = storage.connect()
    try:
        yield conn
    finally:
        conn.close()


def require_auth(request: Request, authorization: str | None = Header(default=None)):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not request.app.state.auth.is_valid(token):
        raise HTTPException(401, "Sign-in required.", headers={"WWW-Authenticate": "Bearer"})


def lastfm_key() -> str:
    try:
        return config.lastfm_key()
    except RuntimeError:
        raise HTTPException(503, "LASTFM_KEY is not set on the server.")


# ---------- модели запросов ----------

class AuthIn(BaseModel):
    pin: str = Field(max_length=200)


class PersonIn(BaseModel):
    username: str = Field(pattern=r"^[\w-]{1,64}$")
    display_name: str = Field(default="", max_length=60)


class SyncIn(BaseModel):
    username: str | None = None


class SignupIn(BaseModel):
    username: str = Field(pattern=r"^[\w-]{1,64}$")
    consent: bool = False
    contact: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=200)   # honeypot: человек его не видит


SIGNUP_MAX_BODY = 2048        # байт
SIGNUP_LIMIT = 5              # заявок
SIGNUP_WINDOW = 600           # за 10 минут с одного адреса
SIGNUP_MAX_PENDING = 50       # потолок ожидающих заявок
SIGNUP_OK = {"status": "received"}   # один и тот же ответ на любой «успех»


# ---------- открытые адреса ----------

public = APIRouter(prefix="/api")


@public.get("/health")
def health():
    return {"status": "ok"}


@public.post("/auth")
def login(body: AuthIn, request: Request):
    pin = config.admin_pin()
    if pin is None:
        raise HTTPException(503, "Admin mode is disabled: ADMIN_PIN is not set on the server.")
    auth: Auth = request.app.state.auth
    if not auth.allow_attempt(request.client.host if request.client else "?"):
        raise HTTPException(429, "Too many attempts. Please wait a minute.",
                            headers={"Retry-After": "60"})
    if not hmac.compare_digest(body.pin.encode(), pin.encode()):
        raise HTTPException(401, "Wrong PIN.")
    return {"token": auth.issue_token()}


@public.post("/signup")
def signup(body: SignupIn, request: Request, conn=Depends(get_conn)):
    """Заявка друга. Ничего не сообщает о других людях: новая заявка, повторная и ник,
    который уже в списке, получают одинаковый ответ."""
    if not config.signup_enabled():
        raise HTTPException(404, "Not Found")
    if int(request.headers.get("content-length") or 0) > SIGNUP_MAX_BODY:
        raise HTTPException(413, "Request too large.")
    if body.website:                      # бот заполнил скрытое поле: молча «успех»
        return SIGNUP_OK
    if body.consent is not True:
        raise HTTPException(400, "Consent is required: please tick the box to agree to the use of your data.")
    client = request.client.host if request.client else "?"
    if not request.app.state.signup_limiter.allow(client):
        raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": "600"})
    if storage.count_pending_signups(conn) >= SIGNUP_MAX_PENDING:
        raise HTTPException(503, "Requests are temporarily closed. Please send your username to Anna directly.")
    key = lastfm_key()
    try:
        canonical = lastfm.verify_public_user(body.username, key)
    except lastfm.LastfmError as e:
        code = {"not_found": 404, "private": 403}.get(e.status, 502)
        raise HTTPException(code, e.message)
    except (requests.RequestException, KeyError, ValueError, TypeError):
        raise HTTPException(502, lastfm.MESSAGES["error"])
    if not storage.get_person(conn, canonical):
        storage.create_signup(conn, canonical, body.contact.strip(), int(time.time()))
    return SIGNUP_OK


# ---------- закрытые адреса: зависимость стоит на всём роутере ----------

protected = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


@protected.get("/people")
def people(conn=Depends(get_conn)):
    return storage.list_people(conn)


@protected.post("/people", status_code=201)
def add_person(body: PersonIn, conn=Depends(get_conn)):
    key = lastfm_key()
    try:
        canonical = lastfm.verify_user(body.username, key)
    except lastfm.LastfmError as e:
        raise HTTPException(404 if e.status == "not_found" else 502, e.message)
    except (requests.RequestException, KeyError, ValueError, TypeError):
        raise HTTPException(502, lastfm.MESSAGES["error"])
    if storage.get_person(conn, canonical):
        raise HTTPException(409, "This person is already in the list.")
    storage.add_person(conn, canonical, body.display_name.strip() or canonical)
    return next(p for p in storage.list_people(conn) if p["username"] == canonical)


@protected.delete("/people/{username}", status_code=204)
def delete_person(username: str, conn=Depends(get_conn)):
    if not storage.delete_person(conn, username):
        raise HTTPException(404, "That person is not in the list.")
    return Response(status_code=204)


@protected.post("/sync")
def sync(body: SyncIn | None = None, conn=Depends(get_conn)):
    key = lastfm_key()
    names = None
    if body and body.username:
        if not storage.get_person(conn, body.username):
            raise HTTPException(404, "That person is not in the list.")
        names = [body.username]
    return {"results": lastfm.sync_all(conn, names, key)}


@protected.get("/signups")
def signups(conn=Depends(get_conn)):
    return storage.list_signups(conn, "pending")


def _decide(signup_id: int, approve: bool, conn):
    s = storage.get_signup(conn, signup_id)
    if not s:
        raise HTTPException(404, "Request not found.")
    if s["status"] != "pending":
        raise HTTPException(409, "This request was already handled.")
    storage.decide_signup(conn, signup_id, approve)
    return {"id": signup_id, "status": "approved" if approve else "rejected"}


@protected.post("/signups/{signup_id}/approve")
def approve_signup(signup_id: int, conn=Depends(get_conn)):
    return _decide(signup_id, True, conn)


@protected.post("/signups/{signup_id}/reject")
def reject_signup(signup_id: int, conn=Depends(get_conn)):
    return _decide(signup_id, False, conn)


@protected.get("/report")
def report(conn=Depends(get_conn)):
    return analytics.build_report(storage.all_scrobbles(conn), generated_at=int(time.time()))


def create_app(static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Flow API")
    app.state.auth = Auth()
    app.state.signup_limiter = RateLimiter(SIGNUP_LIMIT, SIGNUP_WINDOW)
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
    app.include_router(public)
    app.include_router(protected)
    # Собранный фронтенд (npm run build в web/) отдаётся с того же порта, Vite не нужен.
    # Монтируется последним: /api и /docs уже зарегистрированы и имеют приоритет.
    # Если web/dist нет (не собран), приложение работает как раньше, только API.
    static = static_dir if static_dir is not None else config.ROOT / "web" / "dist"
    if (static / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=static, html=True), name="web")
    return app


app = create_app()
