"""Flagged AI answers for the admin screens (specs 30 and 34): list, resolve (fixed or dismissed) and reopen.
Students create flags from the AI advisor (threads.flag); advisors and automatic checks come with specs 22 and 34."""
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import conflict, not_found
from core.time import local_zone, now, short_date, today
from models import AiFlag, Student, User
from services import audit

STATUSES = ("Open", "Resolved", "Dismissed")
SOURCE_LABELS = {"student": "Reported by student", "advisor": "Reported by an advisor", "auto": "Auto-check"}


def _when(flag: AiFlag) -> str:
    """"Today", "Yesterday", else "Sep 29" (school time zone)."""
    day = flag.created_at.astimezone(local_zone()).date()
    if day == today():
        return "Today"
    if day == today() - timedelta(days=1):
        return "Yesterday"
    return short_date(day)


def _student_label(db: Session, flag: AiFlag) -> str | None:
    """"Amara O." for the student the answer was given to."""
    if flag.student_id is None:
        return None
    user = db.query(User).join(Student, Student.user_id == User.user_id).filter(
        Student.student_id == flag.student_id).one_or_none()
    if user is None:
        return None
    first = user.preferred_name or user.first_name
    return f"{first} {user.last_name[:1]}." if user.last_name else first


def flag_out(db: Session, flag: AiFlag) -> dict:
    return {
        "id": flag.id,
        "q": flag.question,
        "why": flag.issue,
        "answer": flag.answer,
        "when": _when(flag),
        "student": _student_label(db, flag),
        "source": SOURCE_LABELS[flag.source],
        "status": flag.status,
    }


def counts(db: Session) -> dict:
    rows = dict(db.query(AiFlag.status, func.count(AiFlag.id)).group_by(AiFlag.status).all())
    return {status.lower(): rows.get(status, 0) for status in STATUSES}


def list_flags(db: Session, status: str = "Open") -> dict:
    """Flags with `status` ("All" for every status), newest first, plus the count per status."""
    query = db.query(AiFlag)
    if status != "All":
        query = query.filter(AiFlag.status == status)
    flags = query.order_by(AiFlag.created_at.desc(), AiFlag.id.desc()).all()
    return {"flags": [flag_out(db, flag) for flag in flags], "counts": counts(db)}


def _get(db: Session, flag_id: int) -> AiFlag:
    flag = db.get(AiFlag, flag_id)
    if flag is None:
        raise not_found("Flag")
    return flag


def resolve(db: Session, admin: User, flag_id: int, resolution: str, note: str | None = None,
            ip: str | None = None) -> dict:
    flag = _get(db, flag_id)
    if flag.status != "Open":
        raise conflict(f"This flag is already {flag.status.lower()}.")
    flag.status = resolution
    flag.resolved_by = admin.user_id
    flag.resolved_at = now()
    verb = "Marked as fixed" if resolution == "Resolved" else "Dismissed"
    changes = {"status": ["Open", resolution]}
    if note:
        changes["note"] = note
    audit.record(db, admin, "ai.flag.resolve", f"{verb} a flagged AI answer", ("ai_flag", flag.id), changes, ip=ip)
    db.commit()
    return flag_out(db, flag)


def reopen(db: Session, admin: User, flag_id: int, ip: str | None = None) -> dict:
    flag = _get(db, flag_id)
    if flag.status == "Open":
        raise conflict("This flag is already open.")
    previous = flag.status
    flag.status = "Open"
    flag.resolved_by = None
    flag.resolved_at = None
    audit.record(db, admin, "ai.flag.reopen", "Reopened a flagged AI answer", ("ai_flag", flag.id),
                 {"status": [previous, "Open"]}, ip=ip)
    db.commit()
    return flag_out(db, flag)
