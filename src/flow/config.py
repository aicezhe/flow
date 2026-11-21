"""Настройки из окружения. Файл .env подхватывается python-dotenv и не перетирает
переменные, уже заданные в окружении (так в тестах побеждает monkeypatch)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def db_path() -> Path:
    return Path(os.environ.get("DB_PATH") or ROOT / "data" / "flow.db")


def lastfm_key() -> str:
    key = os.environ.get("LASTFM_KEY")
    if not key:
        raise RuntimeError("Не задана переменная окружения LASTFM_KEY")
    return key


def admin_pin() -> str | None:
    """None значит, что админ-режим выключен (API отвечает 503). Значения по умолчанию нет."""
    return os.environ.get("ADMIN_PIN") or None
