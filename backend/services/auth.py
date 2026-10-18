"""Sign-in, cookie sessions, sign-up and password reset / invite links (spec 02 Phase A).
Phase B (TOTP two-step, Google sign-in) is not built yet: needs_mfa() is always False."""
import re
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings as env
from core.errors import ApiError
from core.security import hash_password, new_token, sha256_hex, verify_password
from core.time import now
from models import AuthToken, LoginAttempt, Student, User, UserSession
from services import audit, mailer, settings

HOMES = {"student": "/student", "advisor": "/advisor", "admin": "/admin"}
RATE_LIMIT = 5
RATE_WINDOW = timedelta(minutes=15)
RESET_LINK_LIFETIME = timedelta(minutes=30)
INVITE_LIFETIME = timedelta(days=7)
SLIDE_GRANULARITY = timedelta(minutes=1)
DEFAULT_PROGRAM_ID = 1

# Compared against when the email is unknown, so a miss costs the same time as a wrong password.
DUMMY_HASH = hash_password("not-a-real-password")



def normalize_email(email: str) -> str:
    return email.strip().lower()


def home_for(role: str) -> str:
    return HOMES[role]


def google_enabled(db: Session) -> bool:
    """Google sign-in is offered when the OAuth client is configured and the admin turned it on (spec 02 Phase B)."""
    return bool(env.GOOGLE_CLIENT_ID and env.GOOGLE_CLIENT_SECRET) and settings.get(db, "security")["google"]


def name_from_email(email: str) -> str:
    """Display name for an invited user: "priya.natarajan@pac.edu" → "Priya Natarajan"."""
    local = email.split("@", 1)[0]
    parts = [part for part in re.split(r"[._+-]+", local) if part]
    return " ".join(part.capitalize() for part in parts) or local


def split_name(name: str) -> tuple[str, str, str]:
    """(full name with spaces collapsed, first, last): the last word is the last name."""
    name = " ".join(name.split())
    first, _, last = name.rpartition(" ") if " " in name else (name, "", "")
    return name, first, last


def user_payload(user: User) -> dict:
    first = user.first_name or user.name.split()[0]
    last = user.last_name or (user.name.split()[-1] if len(user.name.split()) > 1 else "")
    return {
        "id": user.user_id,
        "role": user.role,
        "email": user.email,
        "full_name": user.name,
        "first_name": user.preferred_name or first,  # greetings use the preferred name (spec 17)
        "preferred_name": user.preferred_name,
        "initials": (first[:1] + last[:1]).upper(),
        "mfa_enabled": user.mfa_enabled,
        "google_linked": user.google_sub is not None,
    }


def _rate_limited(db: Session, email: str, kind: str) -> bool:
    query = db.query(func.count(LoginAttempt.id)).filter(
        LoginAttempt.email == email, LoginAttempt.kind == kind, LoginAttempt.at > now() - RATE_WINDOW)
    if kind == "login":
        query = query.filter(LoginAttempt.success.is_(False))
    return query.scalar() >= RATE_LIMIT


def _invalid_credentials() -> ApiError:
    return ApiError(401, "INVALID_CREDENTIALS", "That email and password don't match.")


def _too_many() -> ApiError:
    return ApiError(429, "RATE_LIMITED", "Too many attempts. Wait 15 minutes and try again.")


def authenticate(db: Session, email: str, password: str, ip: str | None) -> User:
    email = normalize_email(email)
    if _rate_limited(db, email, "login"):
        raise _too_many()
    user = db.query(User).filter(func.lower(User.email) == email).one_or_none()
    if user is None:
        verify_password(password, DUMMY_HASH)
    if user is None or not verify_password(password, user.password_hash):
        db.add(LoginAttempt(email=email, ip=ip, kind="login", success=False))
        audit.record(db, user, "auth.login_failed", f"Failed sign-in for {email}", target=("user", user.user_id) if user else None,
                     ip=ip, result="failed", error="Wrong email or password")
        db.commit()
        raise _invalid_credentials()
    if not user.is_active:
        raise ApiError(403, "DEACTIVATED", "This account is deactivated. Contact your administrator.")
    db.add(LoginAttempt(email=email, ip=ip, kind="login", success=True))
    return user


def needs_mfa(db: Session, user: User) -> bool:
    # Phase B: role in (advisor, admin) and settings.get(db, "security")["mfa"].
    return False


def create_session(db: Session, user: User, remember: bool, ip: str | None, user_agent: str | None) -> tuple[str, UserSession]:
    raw, token_hash = new_token()
    lifetime = timedelta(days=env.SESSION_DAYS_REMEMBER) if remember else settings.session_timeout(db)
    session = UserSession(user_id=user.user_id, token_hash=token_hash, expires_at=now() + lifetime, remember=remember,
                          ip=ip, user_agent=(user_agent or "")[:255] or None)
    db.add(session)
    user.last_login_at = now()
    audit.record(db, user, "auth.login", f"{user.name} signed in", target=("user", user.user_id), ip=ip)
    db.commit()
    return raw, session


def user_from_token(db: Session, raw: str) -> User | None:
    """The signed-in user for a session cookie, or None. Non-remembered sessions slide on use."""
    session = db.query(UserSession).filter(UserSession.token_hash == sha256_hex(raw)).one_or_none()
    current = now()
    if session is None or session.revoked_at is not None or session.expires_at <= current:
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    if not session.remember:
        slid = current + settings.session_timeout(db)
        if slid - session.expires_at > SLIDE_GRANULARITY:
            session.expires_at = slid
            db.commit()
    return user


def revoke_session(db: Session, raw: str, ip: str | None) -> None:
    session = db.query(UserSession).filter(UserSession.token_hash == sha256_hex(raw)).one_or_none()
    if session is None or session.revoked_at is not None:
        return
    session.revoked_at = now()
    user = db.get(User, session.user_id)
    audit.record(db, user, "auth.logout", f"{user.name} signed out", target=("user", user.user_id), ip=ip)
    db.commit()


def signup_student(db: Session, name: str, email: str, password: str) -> User:
    institution = settings.get(db, "institution")
    if not institution["selfSignup"]:
        raise ApiError(403, "SIGNUP_CLOSED", "Self sign-up is turned off. Ask your administrator for an invite.")
    email = normalize_email(email)
    domain = institution["domain"]
    if not email.endswith(f"@{domain}"):
        raise ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.",
                       [{"field": "email", "message": f"Use your school email ({domain})."}])
    if db.query(User).filter(func.lower(User.email) == email).first() is not None:
        raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists. Sign in instead.")
    name, first, last = split_name(name)
    user = User(name=name, first_name=first, last_name=last, email=email, password_hash=hash_password(password), role="student")
    db.add(user)
    db.flush()
    # spec 33 adds start_term (the current term) once terms exist.
    db.add(Student(user_id=user.user_id, name=name, email=email, program_id=DEFAULT_PROGRAM_ID))
    db.flush()
    return user


def request_password_reset(db: Session, email: str, ip: str | None) -> None:
    """Always looks successful to the caller, so it can't be used to find out which emails have accounts."""
    email = normalize_email(email)
    if _rate_limited(db, email, "reset"):
        raise _too_many()
    db.add(LoginAttempt(email=email, ip=ip, kind="reset", success=True))
    user = db.query(User).filter(func.lower(User.email) == email).one_or_none()
    if user is None or not user.is_active:
        db.commit()
        return
    mail = issue_reset_link(db, user)
    db.commit()
    mailer.send_all([mail])


def _issue_token(db: Session, user: User, purpose: str, lifetime: timedelta) -> str:
    """A fresh single-use link token; earlier unused links of the same purpose stop working. Doesn't commit."""
    db.query(AuthToken).filter(AuthToken.user_id == user.user_id, AuthToken.purpose == purpose,
                               AuthToken.used_at.is_(None)).update({AuthToken.used_at: now()})
    raw, token_hash = new_token()
    db.add(AuthToken(user_id=user.user_id, token_hash=token_hash, purpose=purpose, expires_at=now() + lifetime))
    return raw


def issue_reset_link(db: Session, user: User) -> mailer.Mail:
    """Adds a 30-minute reset link to the session and returns the email; send it after the caller commits."""
    raw = _issue_token(db, user, "reset", RESET_LINK_LIFETIME)
    return mailer.Mail(user.email, "Reset your Acadmate password",
                       f"Choose a new password here (the link expires in 30 minutes):\n"
                       f"{env.FRONTEND_ORIGIN}/reset-password?token={raw}")


def issue_invite(db: Session, user: User, inviter_name: str) -> mailer.Mail:
    """Adds a 7-day invite link (spec 31) and returns the email; send it after the caller commits. Opening the link
    shows "Set up your account" and confirm_reset activates the user."""
    raw = _issue_token(db, user, "invite", INVITE_LIFETIME)
    return mailer.Mail(user.email, "You're invited to Acadmate",
                       f"{inviter_name} invited you to Acadmate. Set up your account here (the link expires in 7 days):\n"
                       f"{env.FRONTEND_ORIGIN}/reset-password?token={raw}")


def _valid_token(db: Session, raw: str) -> AuthToken:
    token = db.query(AuthToken).filter(AuthToken.token_hash == sha256_hex(raw)).one_or_none()
    if token is None or token.used_at is not None or token.expires_at <= now():
        raise ApiError(410, "LINK_EXPIRED", "This link is invalid or has expired.")
    return token


def check_link(db: Session, raw: str) -> dict:
    token = _valid_token(db, raw)
    return {"email": db.get(User, token.user_id).email, "purpose": token.purpose}


def confirm_reset(db: Session, raw: str, password: str, ip: str | None) -> None:
    token = _valid_token(db, raw)
    user = db.get(User, token.user_id)
    user.password_hash = hash_password(password)
    token.used_at = now()
    if token.purpose == "invite":
        user.is_active = True
    db.query(UserSession).filter(UserSession.user_id == user.user_id, UserSession.revoked_at.is_(None)) \
        .update({UserSession.revoked_at: now()})
    summary = f"{user.name} activated their account" if token.purpose == "invite" else f"{user.name} reset their password"
    audit.record(db, user, "auth.password_reset", summary, target=("user", user.user_id), ip=ip)
    db.commit()
