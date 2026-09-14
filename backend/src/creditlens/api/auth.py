from __future__ import annotations

import hmac
import time
from hashlib import sha256

from fastapi import Cookie, HTTPException, Request, Response

from creditlens.config import get_settings

COOKIE = "creditlens_session"


def _sign(payload: str) -> str:
    settings = get_settings()
    digest = hmac.new(settings.secret_key.encode(), payload.encode(), sha256).hexdigest()
    return f"{payload}.{digest}"


def issue_session(password: str) -> str:
    settings = get_settings()
    if not hmac.compare_digest(password, settings.demo_password):
        raise HTTPException(status_code=401, detail="Неверный demo-пароль")
    return _sign(f"demo:{int(time.time())}")


def require_session(creditlens_session: str | None = Cookie(default=None, alias=COOKIE)) -> str:
    if not creditlens_session or "." not in creditlens_session:
        raise HTTPException(status_code=401, detail="Требуется вход")
    payload, signature = creditlens_session.rsplit(".", 1)
    expected = hmac.new(get_settings().secret_key.encode(), payload.encode(), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    return payload


def set_cookie(response: Response, token: str, *, secure: bool = False) -> None:
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=60 * 60 * 12,
    )
