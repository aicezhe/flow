"""FastAPI: тонкий слой над storage, lastfm, analytics, auth.

Запуск (только локально):
    uvicorn flow.api:app --reload --host 127.0.0.1 --port 8000 --app-dir src
"""
import hmac
import time

import requests
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import analytics, config, lastfm, storage
from .auth import Auth, RateLimiter

# CORS: только адрес dev-сервера Vite.
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


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
        raise HTTPException(401, "Нужен вход.", headers={"WWW-Authenticate": "Bearer"})


def lastfm_key() -> str:
    try:
        return config.lastfm_key()
    except RuntimeError:
        raise HTTPException(503, "На сервере не задан LASTFM_KEY.")


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
        raise HTTPException(503, "Админ-режим выключен: на сервере не задан ADMIN_PIN.")
    auth: Auth = request.app.state.auth
    if not auth.allow_attempt(request.client.host if request.client else "?"):
        raise HTTPException(429, "Слишком много попыток. Подождите минуту.",
                            headers={"Retry-After": "60"})
    if not hmac.compare_digest(body.pin.encode(), pin.encode()):
        raise HTTPException(401, "Неверный PIN.")
    return {"token": auth.issue_token()}


@public.post("/signup")
def signup(body: SignupIn, request: Request, conn=Depends(get_conn)):
    """Заявка друга. Ничего не сообщает о других людях: новая заявка, повторная и ник,
    который уже в списке, получают одинаковый ответ."""
    if not config.signup_enabled():
        raise HTTPException(404, "Not Found")
    if int(request.headers.get("content-length") or 0) > SIGNUP_MAX_BODY:
        raise HTTPException(413, "Слишком большой запрос.")
    if body.website:                      # бот заполнил скрытое поле: молча «успех»
        return SIGNUP_OK
    if body.consent is not True:
        raise HTTPException(400, "Нужно согласие: отметьте галочку, что вы согласны на использование данных.")
    client = request.client.host if request.client else "?"
    if not request.app.state.signup_limiter.allow(client):
        raise HTTPException(429, "Слишком много заявок. Попробуйте позже.", headers={"Retry-After": "600"})
    if storage.count_pending_signups(conn) >= SIGNUP_MAX_PENDING:
        raise HTTPException(503, "Приём заявок временно закрыт. Отправьте ник Анне напрямую.")
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
        raise HTTPException(409, "Этот человек уже в списке.")
    storage.add_person(conn, canonical, body.display_name.strip() or canonical)
    return next(p for p in storage.list_people(conn) if p["username"] == canonical)


@protected.delete("/people/{username}", status_code=204)
def delete_person(username: str, conn=Depends(get_conn)):
    if not storage.delete_person(conn, username):
        raise HTTPException(404, "Такого человека нет в списке.")
    return Response(status_code=204)


@protected.post("/sync")
def sync(body: SyncIn | None = None, conn=Depends(get_conn)):
    key = lastfm_key()
    names = None
    if body and body.username:
        if not storage.get_person(conn, body.username):
            raise HTTPException(404, "Такого человека нет в списке.")
        names = [body.username]
    return {"results": lastfm.sync_all(conn, names, key)}


@protected.get("/signups")
def signups(conn=Depends(get_conn)):
    return storage.list_signups(conn, "pending")


def _decide(signup_id: int, approve: bool, conn):
    s = storage.get_signup(conn, signup_id)
    if not s:
        raise HTTPException(404, "Заявка не найдена.")
    if s["status"] != "pending":
        raise HTTPException(409, "Заявка уже обработана.")
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


def create_app() -> FastAPI:
    app = FastAPI(title="Flow API")
    app.state.auth = Auth()
    app.state.signup_limiter = RateLimiter(SIGNUP_LIMIT, SIGNUP_WINDOW)
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                       allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
    app.include_router(public)
    app.include_router(protected)
    return app


app = create_app()
