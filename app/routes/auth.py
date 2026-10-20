from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import LoginSession, User
from app.schemas import Credentials, PreferenceInput, Register
from app.security import COOKIE, DB, CurrentUser, hash_password, issue_session, token_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["账号"])


def public_user(user):
    return {"id": user.id, "email": user.email, "name": user.name, "preference": user.preference}


@router.post("/register", status_code=201)
def register(body: Register, response: Response, db: DB):
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "该邮箱已注册") from None
    issue_session(db, user, response)
    return public_user(user)


@router.post("/login")
def login(body: Credentials, response: Response, db: DB):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    issue_session(db, user, response)
    return public_user(user)


@router.get("/me")
def me(user: CurrentUser):
    return public_user(user)


@router.patch("/me")
def preferences(body: PreferenceInput, user: CurrentUser, db: DB):
    user.preference = body.preference
    db.commit()
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    session = db.get(LoginSession, token_hash(request.cookies.get(COOKIE, "")))
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(COOKIE)
