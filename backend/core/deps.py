"""Auth dependencies for routers. Every /students/me/* route uses get_current_student, every /advisor/*
route get_current_advisor and every /admin/* route require_role("admin")."""
from typing import Callable, NamedTuple

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.config import settings
from core.errors import forbidden, not_found, unauthenticated
from database import get_db
from models import Advisor, AdvisorStudentAssignment, ApiKey, Student, User
from services import api_keys, auth


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get(settings.SESSION_COOKIE)
    user = auth.user_from_token(db, raw) if raw else None
    if user is None or not user.is_active:
        raise unauthenticated()
    return user


def require_role(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise forbidden()
        return user
    return dependency


def get_current_student(user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> Student:
    student = db.query(Student).filter(Student.user_id == user.user_id).one_or_none()
    if student is None:
        raise not_found("Student profile")
    return student


def get_current_advisor(user: User = Depends(require_role("advisor")), db: Session = Depends(get_db)) -> Advisor:
    advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one_or_none()
    if advisor is None:
        raise not_found("Advisor profile")
    return advisor


def advisor_can_see(db: Session, advisor_id: int, student_id: int) -> None:
    link = db.get(AdvisorStudentAssignment, student_id)
    if link is None or link.advisor_id != advisor_id:
        raise forbidden("This student isn't assigned to you.")


class ReportCaller(NamedTuple):
    """Who is reading a report: a signed-in admin, or an API key (spec 35)."""
    user: User | None
    key: ApiKey | None


def reports_access(request: Request, db: Session = Depends(get_db)) -> ReportCaller:
    """/admin/reports/*: an `Authorization: Bearer acm_…` key with scope reports:read, else an admin session.
    A bearer header must hold a valid key; it never falls back to the cookie."""
    header = request.headers.get("authorization")
    if header:
        key = api_keys.verify(db, header, "reports:read")
        if key is None:
            raise unauthenticated("Invalid or revoked API key.")
        return ReportCaller(None, key)
    user = get_current_user(request, db)
    if user.role != "admin":
        raise forbidden()
    return ReportCaller(user, None)
