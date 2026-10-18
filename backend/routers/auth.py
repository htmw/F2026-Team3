from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from core.config import settings as env
from core.deps import get_current_user
from database import get_db
from models import User
from schemas.auth import AuthOut, ConfigOut, LinkOut, LoginIn, MeOut, OkOut, ResetConfirmIn, ResetRequestIn, SignupIn
from services import auth, settings
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _set_session_cookie(response: Response, raw: str, remember: bool) -> None:
    response.set_cookie(env.SESSION_COOKIE, raw, httponly=True, samesite="lax", secure=env.COOKIE_SECURE, path="/",
                        max_age=env.SESSION_DAYS_REMEMBER * 86400 if remember else None)


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(env.SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=env.COOKIE_SECURE)


def _signed_in(db: Session, request: Request, response: Response, user: User, remember: bool) -> dict:
    raw, _ = auth.create_session(db, user, remember, request_ip(request), request.headers.get("user-agent"))
    _set_session_cookie(response, raw, remember)
    return {"user": auth.user_payload(user), "home": auth.home_for(user.role)}


@router.get("/config", response_model=ConfigOut)
def config(db: Session = Depends(get_db)):
    institution = settings.get(db, "institution")
    return {
        "google_enabled": auth.google_enabled(db),
        "accent": settings.get(db, "branding")["accent"],
        "institution_name": institution["name"],
        "self_signup": institution["selfSignup"],
    }


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = auth.authenticate(db, body.email, body.password, request_ip(request))
    # Phase B: if auth.needs_mfa(db, user), answer {"mfaRequired": true, ...} instead of signing in.
    return _signed_in(db, request, response, user, body.remember)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(env.SESSION_COOKIE)
    if raw:
        auth.revoke_session(db, raw, request_ip(request))
    clear_session_cookie(response)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return {"user": auth.user_payload(user)}


@router.post("/signup", response_model=AuthOut, status_code=201)
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = auth.signup_student(db, body.name, body.email, body.password)
    return _signed_in(db, request, response, user, remember=False)


@router.post("/password-reset", response_model=OkOut, status_code=202)
def password_reset(body: ResetRequestIn, request: Request, db: Session = Depends(get_db)):
    auth.request_password_reset(db, body.email, request_ip(request))
    return {"ok": True}


@router.get("/password-reset/{token}", response_model=LinkOut)
def password_reset_link(token: str, db: Session = Depends(get_db)):
    return auth.check_link(db, token)


@router.post("/password-reset/confirm", status_code=204)
def password_reset_confirm(body: ResetConfirmIn, request: Request, db: Session = Depends(get_db)):
    auth.confirm_reset(db, body.token, body.password, request_ip(request))
