"""Approval requests shared by the features that create them: term plans (spec 12) and advising forms (spec 15).
Spec 23 adds the advisor queue and decisions here."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import AdvisorStudentAssignment, ApprovalRequest, Assignment, Student
from services.catalog import current_term


def avg_decision_days(db: Session, since: datetime) -> dict[int, float]:
    """Average time from request to decision, in days, per advisor, over requests decided since `since`
    (the overview's workload and the admin advisors list, specs 30 and 32)."""
    seconds = func.avg(func.extract("epoch", ApprovalRequest.decided_at - ApprovalRequest.created_at))
    rows = (db.query(ApprovalRequest.advisor_id, seconds)
            .filter(ApprovalRequest.decided_at >= since, ApprovalRequest.advisor_id.isnot(None))
            .group_by(ApprovalRequest.advisor_id))
    return {advisor_id: float(value) / 86400 for advisor_id, value in rows}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def precheck_summary(checks: list[dict]) -> dict:
    """{ok, text, checks}: only blocking checks stop one-click approval; warnings are listed for the advisor."""
    blocking = sum(1 for check in checks if not check["ok"] and check["blocking"])
    warnings = sum(1 for check in checks if not check["ok"] and not check["blocking"])
    if blocking:
        text = f"{_plural(blocking, 'thing')} to fix before your advisor can approve."
    elif warnings:
        text = f"Ready for your advisor. {_plural(warnings, 'thing')} to finish soon."
    else:
        text = "Ready for your advisor."
    return {"ok": blocking == 0, "text": text, "checks": checks}


def advisor_for(db: Session, student: Student) -> int | None:
    link = db.get(AdvisorStudentAssignment, student.student_id)
    return link.advisor_id if link else None


def create_form_request(db: Session, student: Student, assignment: Assignment, fields: dict, precheck: dict) -> ApprovalRequest:
    """A pending `form` request for the student's advisor. The caller commits."""
    term = current_term(db)
    request = ApprovalRequest(student_id=student.student_id, advisor_id=advisor_for(db, student), type="form",
                              title=assignment.title[:200], term_id=term.id if term else None,
                              payload={"assignmentId": assignment.id, "fields": fields}, precheck=precheck)
    db.add(request)
    db.flush()
    return request
