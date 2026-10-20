import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import LoginSession, User, now

DB = Annotated[Session, Depends(get_db)]
COOKIE = "studyflow_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    salt, expected = encoded.split(":")
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)
    return hmac.compare_digest(digest.hex(), expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db: Session, user: User, response: Response):
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(token), user_id=user.id, expires_at=now() + timedelta(days=7)))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=604800)


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(COOKIE, "")
    session = db.get(LoginSession, token_hash(token))
    if not session or session.expires_at.replace(tzinfo=now().tzinfo) <= now():
        raise HTTPException(401, "请先登录")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
