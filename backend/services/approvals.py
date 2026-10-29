"""Approval requests shared by the features that create them: term plans (spec 12), advising forms (spec 15) and
drop requests, and the advisor's queue and decisions on them (spec 23: list, approve / request changes / reopen)."""
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import conflict, not_found
from core.time import iso_z, local_zone, now, short_date
from models import (Advisor, AdvisorStudentAssignment, ApprovalRequest, Assignment, AssignmentSubmission, Course,
                    CourseSection, Enrollment, PlanItem, Student, User)
from services import audit, messages, preferences
from services.catalog import current_term

TYPE_LABELS = {"plan": "Course plan", "form": "Form"}  # every other type is a "Request"
REOPEN_WINDOW = timedelta(hours=24)
DECIDED_DAYS = 60  # the Approved / Changes requested tabs look back this far
FULL_TIME_CREDITS = 9
STATUS_LABELS = {"pending": "Pending", "approved": "Approved", "changes_requested": "Changes requested"}
CANT_REOPEN = "This decision can't be reopened anymore."


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


def type_label(request: ApprovalRequest) -> str:
    return TYPE_LABELS.get(request.type, "Request")


def pending_query(db: Session, advisor: Advisor):
    """The advisor's pending requests, oldest first."""
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at, ApprovalRequest.id))


def pending_count(db: Session, advisor: Advisor) -> int:
    """The advisor's Approvals badge and the dashboard's "Waiting for you"."""
    return pending_query(db, advisor).count()


def _own(db: Session, advisor: Advisor, request_id: int) -> ApprovalRequest:
    """The advisor's request; another advisor's request is a 404 too, so ids don't reveal other queues."""
    request = db.get(ApprovalRequest, request_id)
    if request is None or request.advisor_id != advisor.advisor_id:
        raise not_found("Approval request")
    return request


def _plan_items(db: Session, request: ApprovalRequest) -> list[PlanItem]:
    ids = (request.payload or {}).get("planItemIds") or []
    return db.query(PlanItem).filter(PlanItem.id.in_(ids), PlanItem.student_id == request.student_id).all() if ids else []


def _submission(db: Session, request: ApprovalRequest) -> AssignmentSubmission | None:
    return (db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == (request.payload or {}).get("assignmentId"),
                    AssignmentSubmission.student_id == request.student_id).one_or_none())


def _is_drop(request: ApprovalRequest) -> bool:
    return request.type == "other" and (request.payload or {}).get("kind") == "drop"


def _drop_enrollment(db: Session, request: ApprovalRequest) -> Enrollment | None:
    """The current-term enrollment a drop request is about."""
    term = current_term(db)
    if term is None:
        return None
    return (db.query(Enrollment)
            .filter(Enrollment.student_id == request.student_id, Enrollment.course_id == (request.payload or {}).get("courseId"),
                    Enrollment.term == term.name)
            .order_by(Enrollment.enrollment_id).first())


def _credits(course: Course) -> str:
    return f"{float(course.credits):g} cr"


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _check_sentence(db: Session, request: ApprovalRequest, student: Student) -> str:
    """One line for the pre-check box: the first blocking problem, else what the request keeps on track."""
    checks = (request.precheck or {}).get("checks") or []
    if request.type == "form":
        empty = [name for name, value in ((request.payload or {}).get("fields") or {}).items() if not str(value).strip()]
        if empty:
            return f"The {empty[0].lower()} section is empty. Approving now would leave the form incomplete."
    if not (request.precheck or {}).get("ok", True):
        failed = next((c for c in checks if not c.get("ok") and c.get("blocking")), None) \
            or next((c for c in checks if not c.get("ok")), None)
        return _sentence(failed["text"]) if failed else "Needs a closer look before approving."
    if request.type == "plan":
        if any(c.get("ok") and str(c.get("text", "")).startswith("Covers all remaining requirements") for c in checks):
            graduation = f" Graduation stays on track for {student.expected_graduation}." if student.expected_graduation else ""
            return f"Meets every remaining requirement.{graduation}"
        credits = sum(float(db.get(Course, item.course_id).credits) for item in _plan_items(db, request))
        if credits >= FULL_TIME_CREDITS:
            return f"{credits:g} credits keeps full-time status."
        return f"{credits:g} credits, below full-time status."
    if request.type == "form":
        return "Every section is filled in."
    return "Nothing blocks approval."


def _lines(db: Session, request: ApprovalRequest) -> list[dict]:
    """"What's being requested": plan courses with their section time, form fields, or the drop and its credit load."""
    payload = request.payload or {}
    if request.type == "plan":
        sections = ({s.course_id: s for s in db.query(CourseSection).filter(CourseSection.term_id == request.term_id)}
                    if request.term_id else {})
        lines = []
        for item in sorted(_plan_items(db, request), key=lambda i: i.id):
            course = db.get(Course, item.course_id)
            section = sections.get(course.course_id)
            when = (f"{section.meeting_days.split(',')[0]} {section.start_time.strftime('%H:%M')} · "
                    if section and section.meeting_days and section.start_time else "")
            lines.append({"a": f"{course.course_code} {course.course_name}", "b": f"{when}{_credits(course)}"})
        return lines
    if request.type == "form":
        return [{"a": name, "b": str(value).strip() or "Missing"} for name, value in (payload.get("fields") or {}).items()]
    if _is_drop(request):
        course = db.get(Course, payload.get("courseId")) if payload.get("courseId") else None
        lines = [{"a": "Drop", "b": f"{course.course_code} · {_credits(course)}" if course else "A course"}]
        if payload.get("creditsAfter") is not None:
            lines.append({"a": "Credits after drop", "b": f"{float(payload['creditsAfter']):g}"})
        return lines
    return []


def row(db: Session, advisor: Advisor, request: ApprovalRequest) -> dict:
    """One request as the queue and the detail pane show it (spec 23)."""
    from services.advisees import short_name  # advisees reaches this module through degree_audit

    student = db.get(Student, request.student_id)
    user = db.get(User, student.user_id)
    ok = bool((request.precheck or {}).get("ok", True))
    can_undo = (request.status in ("approved", "changes_requested") and request.decided_by == advisor.user_id
                and request.decided_at is not None and now() - request.decided_at <= REOPEN_WINDOW)
    return {
        "id": request.id,
        "studentId": student.student_id,
        "name": short_name(student.name),
        "firstName": (user.preferred_name or user.first_name) if user and (user.preferred_name or user.first_name)
        else student.name.split()[0],
        "type": type_label(request),
        "item": request.title,
        "when": short_date(request.created_at.astimezone(local_zone()).date()),
        "status": STATUS_LABELS.get(request.status, request.status.replace("_", " ").capitalize()),
        "ok": ok,
        "checkShort": "Pre-check passed" if ok else "Needs a look",
        "check": _check_sentence(db, request, student),
        "lines": _lines(db, request),
        "comment": request.comment,
        "decidedAt": request.decided_at,
        "canUndo": can_undo,
    }


def _decided_query(db: Session, advisor: Advisor, status: str):
    since = now() - timedelta(days=DECIDED_DAYS)
    return (db.query(ApprovalRequest)
            .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.status == status,
                    ApprovalRequest.decided_at >= since)
            .order_by(ApprovalRequest.decided_at.desc(), ApprovalRequest.id.desc()))


def list_for(db: Session, advisor: Advisor, label: str = "Pending") -> dict:
    """The queue tab `label` (Pending oldest first; decided tabs newest first over the last 60 days) with all three counts."""
    queries = {"Pending": pending_query(db, advisor),
               "Approved": _decided_query(db, advisor, "approved"),
               "Changes requested": _decided_query(db, advisor, "changes_requested")}
    return {"tabs": [{"label": name, "count": query.count()} for name, query in queries.items()],
            "rows": [row(db, advisor, request) for request in queries[label]],
            "prechecks": prechecks_on(db, advisor)}


def get(db: Session, advisor: Advisor, request_id: int) -> dict:
    return row(db, advisor, _own(db, advisor, request_id))


def _decide(db: Session, advisor: Advisor, request_id: int, status: str, comment: str | None) -> ApprovalRequest:
    """Decides a pending request and applies its effect (plan items take the new status; forms go through
    assignments.apply_form_decision; an approved drop withdraws the enrollment, registrar sync is out of scope).
    The pre-decision state goes to payload["before"] so reopen() can restore it."""
    from services.assignments import apply_form_decision  # assignments imports this module

    request = _own(db, advisor, request_id)
    if request.status != "pending":
        raise conflict("This request has already been decided.")

    before: dict = {}
    if request.type == "plan":
        items = _plan_items(db, request)
        before["planItems"] = {str(item.id): item.status for item in items}
        for item in items:
            item.status = status
    request.status, request.comment, request.decided_at, request.decided_by = status, comment, now(), advisor.user_id
    if request.type == "form":
        submission = _submission(db, request)
        if submission is not None:
            before["submission"] = {"status": submission.status, "scoreText": submission.score_text,
                                    "feedback": submission.feedback}
        apply_form_decision(db, request)
        if submission is not None:
            before["submissionAfter"] = submission.status
    if _is_drop(request) and status == "approved":
        enrollment = _drop_enrollment(db, request)
        if enrollment is not None and enrollment.status == "in_progress":
            before["enrollment"] = {"id": enrollment.enrollment_id, "status": enrollment.status}
            enrollment.status = "withdrawn"
    request.payload = {**(request.payload or {}), "before": before}  # reassign: JSON columns don't track in-place edits
    return request


def approve(db: Session, advisor: Advisor, request_id: int, comment: str | None = None) -> ApprovalRequest:
    """Approves a pending request and applies its effect. The caller commits."""
    request = _decide(db, advisor, request_id, "approved", comment)
    actor = db.get(User, advisor.user_id)
    student = db.get(Student, request.student_id)
    text = f"{actor.name} approved your {request.title}."
    messages.notify(db, student.user_id, f"{text} “{comment}”" if comment else text)
    audit.record(db, actor, "approval.approve", f"Approved {student.name}'s {request.title}",
                 target=("approval_request", request.id), changes={"status": ["pending", "approved"]})
    db.flush()
    return request


def request_changes(db: Session, advisor: Advisor, request_id: int, comment: str) -> ApprovalRequest:
    """Sends a pending request back to the student with the advisor's comment. The caller commits."""
    request = _decide(db, advisor, request_id, "changes_requested", comment)
    actor = db.get(User, advisor.user_id)
    student = db.get(Student, request.student_id)
    messages.notify(db, student.user_id, f"{actor.name} asked for changes to your {request.title}: “{comment}”")
    audit.record(db, actor, "approval.request_changes", f"Asked {student.name} to change the {request.title}",
                 target=("approval_request", request.id), changes={"status": ["pending", "changes_requested"]})
    db.flush()
    return request


STALE_AFTER = timedelta(days=3)


def prechecks_on(db: Session, advisor: Advisor) -> bool:
    """Spec 27's "Run Acadmate pre-checks" switch. Off: checks are still stored, but the advisor screens hide them
    and never disable a quick Approve."""
    return bool(preferences.get(db, db.get(User, advisor.user_id))["approvals"].get("precheck", True))


def remind_stale(db: Session) -> int:
    """Daily (scripts/send_reminders.py): one notice per advisor with "Remind me about requests older than 3 days" on,
    listing the pending requests that crossed 3 days since the last run (each request is reminded once). Commits;
    returns the number of advisors told."""
    cutoff = now() - STALE_AFTER
    stale: dict[int, list[ApprovalRequest]] = {}
    for request in (db.query(ApprovalRequest)
                    .filter(ApprovalRequest.status == "pending", ApprovalRequest.advisor_id.isnot(None),
                            ApprovalRequest.created_at <= cutoff)
                    .order_by(ApprovalRequest.created_at)):
        if not (request.payload or {}).get("remindedAt"):
            stale.setdefault(request.advisor_id, []).append(request)
    told = 0
    for advisor_id, requests in stale.items():
        advisor = db.get(Advisor, advisor_id)
        user = db.get(User, advisor.user_id) if advisor else None
        if user is None or not user.is_active or not preferences.get(db, user)["approvals"].get("remindAfter3Days", True):
            continue
        titles = "; ".join(r.title for r in requests[:3]) + ("; …" if len(requests) > 3 else "")
        n = len(requests)
        messages.notify(db, user.user_id, f"{n} request{' has' if n == 1 else 's have'} waited more than 3 days: {titles}.")
        for request in requests:
            request.payload = {**(request.payload or {}), "remindedAt": iso_z(now())}
        told += 1
    db.commit()
    return told


def reopen(db: Session, advisor: Advisor, request_id: int) -> ApprovalRequest:
    """Puts a decision from the last 24 hours back to pending and restores what it changed. 409 when the decision is
    older or its effects changed since (the student edited the plan, resubmitted the form, re-enrolled). The caller
    commits."""
    request = _own(db, advisor, request_id)
    if request.status not in ("approved", "changes_requested") or request.decided_at is None \
            or now() - request.decided_at > REOPEN_WINDOW:
        raise conflict(CANT_REOPEN)
    payload = dict(request.payload or {})
    before = payload.pop("before", {}) or {}
    old_status = request.status

    statuses = before.get("planItems") or {}
    items = {str(item.id): item for item in _plan_items(db, request)}
    if any(key not in items or items[key].status != old_status for key in statuses):
        raise conflict(CANT_REOPEN)
    submission = _submission(db, request) if before.get("submission") is not None else None
    if submission is not None and before.get("submissionAfter") not in (None, submission.status):
        raise conflict(CANT_REOPEN)
    dropped = before.get("enrollment")
    enrollment = db.get(Enrollment, dropped["id"]) if dropped else None
    if dropped and (enrollment is None or enrollment.status != "withdrawn"):
        raise conflict(CANT_REOPEN)

    for key, status in statuses.items():
        items[key].status = status
    if submission is not None:
        saved = before["submission"]
        submission.status, submission.score_text, submission.feedback = saved["status"], saved["scoreText"], saved["feedback"]
    if enrollment is not None:
        enrollment.status = dropped["status"]

    request.payload = payload
    request.status, request.comment, request.decided_at, request.decided_by = "pending", None, None, None
    actor = db.get(User, advisor.user_id)
    student = db.get(Student, request.student_id)
    messages.notify(db, student.user_id, f"Your {request.title} is back under review.")
    audit.record(db, actor, "approval.reopen", f"Reopened {student.name}'s {request.title}",
                 target=("approval_request", request.id), changes={"status": [old_status, "pending"]})
    db.flush()
    return request
