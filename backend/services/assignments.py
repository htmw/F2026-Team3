"""Assignments (spec 15): coursework of the student's current sections plus advising items (forms) for their program,
with the student's progress in assignment_submissions. Also the source of the dashboard deadlines and on-time tile
(spec 10), the schedule's deadlines and study suggestion (spec 14) and the student's assignments badge."""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session

from core.errors import ApiError, conflict, not_found
from core.time import iso_z, local_zone, now, short_date, today
from models import ApprovalRequest, Assignment, AssignmentSubmission, Student, User
from services import approvals, audit
from services.catalog import current_term
from services.courses import current_enrollments

DUE_SOON_DAYS = 3
NEXT_DAYS = 10
BADGE_DAYS = 7
ADVISING = "Advising"
STATUS_LABELS = {"todo": "To do", "in_progress": "In progress", "submitted": "Submitted", "graded": "Graded"}
TABS = ("To do", "In progress", "Submitted", "Graded")
CLOSED = ("submitted", "graded")
FORM_FIELDS = {"Proposed topic": 200, "Project summary": 4000}  # field -> max length
SHORT_SUMMARY_WORDS = 50


@dataclass
class Entry:
    assignment: Assignment
    submission: AssignmentSubmission
    course: str  # course code, or "Advising"

    @property
    def due(self) -> date:
        return due_date(self.assignment)

    @property
    def closed(self) -> bool:
        return self.submission.status in CLOSED

    @property
    def status(self) -> str:
        return STATUS_LABELS[self.submission.status]

    @property
    def short(self) -> str:
        return short_title(self.assignment)


def due_date(assignment: Assignment) -> date:
    """The local (institution time zone) calendar day an assignment is due."""
    return assignment.due_at.astimezone(local_zone()).date()


def short_title(assignment: Assignment) -> str:
    return assignment.short_title or assignment.title.split(":")[0].strip()


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def _visible(db: Session, student: Student) -> tuple[list[Assignment], dict[int, str]]:
    """Assignments of the student's current sections plus the advising items of their program; section id -> course code."""
    sections = {entry.section.id: entry.course.course_code for entry in current_enrollments(db, student) if entry.section}
    query = db.query(Assignment).filter(or_(
        Assignment.section_id.in_(sections) if sections else false(),
        and_(Assignment.section_id.is_(None), Assignment.program_id == student.program_id),
    ))
    return query.all(), sections


def _submission(db: Session, student: Student, assignment: Assignment, existing: dict | None = None) -> AssignmentSubmission:
    submission = (existing.get(assignment.id) if existing is not None else
                  db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment.id,
                                                        AssignmentSubmission.student_id == student.student_id).one_or_none())
    if submission is None:
        submission = AssignmentSubmission(assignment_id=assignment.id, student_id=student.student_id, status="todo", steps_done=[])
        db.add(submission)
        db.flush()
    return submission


def list_for_student(db: Session, student: Student) -> list[Entry]:
    """Open items by due date first, then closed items newest first. Missing submissions are created (the caller commits)."""
    assignments, sections = _visible(db, student)
    existing = {row.assignment_id: row for row in db.query(AssignmentSubmission)
                .filter(AssignmentSubmission.student_id == student.student_id)}
    entries = [Entry(a, _submission(db, student, a, existing), sections.get(a.section_id, ADVISING)) for a in assignments]
    open_rows = sorted((e for e in entries if not e.closed), key=lambda e: (e.assignment.due_at, e.assignment.title))
    closed_rows = sorted((e for e in entries if e.closed), key=lambda e: e.assignment.title)
    closed_rows.sort(key=lambda e: e.assignment.due_at, reverse=True)  # stable: titles stay A→Z on the same due time
    return open_rows + closed_rows


def deadline_label(entry: Entry, day: date) -> str:
    if entry.closed:
        return "Done"
    if entry.due < day:
        return "Overdue"
    if (entry.due - day).days <= DUE_SOON_DAYS:
        return "Due soon"
    return "In progress" if entry.submission.status == "in_progress" else "Not started"


def score_text(submission: AssignmentSubmission) -> str:
    if submission.score is not None:
        return f"{float(submission.score):g}%"
    return submission.score_text or "—"


def row_out(entry: Entry, day: date) -> dict:
    a, s = entry.assignment, entry.submission
    desc = a.description
    if s.feedback:
        desc = f"{desc}\n\nAdvisor: {s.feedback}" if desc else f"Advisor: {s.feedback}"
    done = set(s.steps_done or [])
    return {
        "id": a.id,
        "title": a.title,
        "course": entry.course,
        "due": short_date(entry.due),
        "due_date": entry.due.isoformat(),
        "status": entry.status,
        "deadline": deadline_label(entry, day),
        "score": score_text(s),
        "weight": a.weight_text,
        "type": a.type,
        "desc": desc,
        "submission_url": a.submission_url,
        "steps": [{"text": text, "done": index in done} for index, text in enumerate(a.default_steps or [])],
    }


def _and(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _unique(values) -> list:
    return list(dict.fromkeys(values))


def stats(entries: list[Entry], day: date) -> list[dict]:
    upcoming = [e for e in entries if not e.closed and e.due <= day + timedelta(days=NEXT_DAYS)]
    soonest = min(upcoming, key=lambda e: e.assignment.due_at, default=None)
    doing = [e for e in entries if e.submission.status == "in_progress"]
    waiting = [e for e in entries if e.submission.status == "submitted"]
    scores = [float(e.submission.score) for e in entries if e.submission.status == "graded" and e.submission.score is not None]
    return [
        {"label": "Due in next 10 days", "value": str(len(upcoming)),
         "note": f"Next: {soonest.short} on {short_date(soonest.due)}" if soonest else "Nothing due soon"},
        {"label": "In progress", "value": str(len(doing)),
         "note": _and(_unique(e.course for e in doing)) if doing else "Nothing started yet"},
        {"label": "Awaiting grade", "value": str(len(waiting)),
         "note": f"{waiting[0].short} · {waiting[0].course}" if waiting else "Nothing waiting"},
        {"label": "Graded average", "value": f"{round(sum(scores) / len(scores))}%" if scores else "—",
         "note": f"Across {len(scores)} graded item{'' if len(scores) == 1 else 's'}" if scores else "No grades yet"},
    ]


def subtitle(db: Session, entries: list[Entry]) -> str:
    term = current_term(db)
    courses = _unique(e.course for e in entries if e.course != ADVISING)
    advising = any(e.course == ADVISING for e in entries)
    scope = f"{len(courses)} course{'' if len(courses) == 1 else 's'}" + (" and advising" if advising else "")
    if not courses:
        scope = "advising" if advising else "no courses"
    items = f"{len(entries)} item{'' if len(entries) == 1 else 's'}"
    return f"{term.name if term else 'This term'} · {items} across {scope}"


def payload(db: Session, student: Student) -> dict:
    day = today()
    entries = list_for_student(db, student)
    db.commit()  # keep the lazily created submissions
    return {
        "subtitle": subtitle(db, entries),
        "stats": stats(entries, day),
        "tabs": [{"label": "All", "count": len(entries)}] +
                [{"label": label, "count": sum(1 for e in entries if e.status == label)} for label in TABS],
        "courses": [{"value": course, "label": course} for course in _unique(e.course for e in entries)],
        "rows": [row_out(e, day) for e in entries],
    }


def _own(db: Session, student: Student, assignment_id: int) -> tuple[Assignment, AssignmentSubmission]:
    assignments, _ = _visible(db, student)
    assignment = next((a for a in assignments if a.id == assignment_id), None)
    if assignment is None:
        raise not_found("Assignment")
    return assignment, _submission(db, student, assignment)


def update_progress(db: Session, student: Student, assignment_id: int, steps_done: list[int] | None,
                    status: str | None) -> dict:
    assignment, submission = _own(db, student, assignment_id)
    if submission.status in CLOSED:
        raise conflict("This assignment is already submitted.")
    if steps_done is not None:
        count = len(assignment.default_steps or [])
        if any(index < 0 or index >= count for index in steps_done):
            raise _validation("stepsDone", f"Choose steps between 0 and {count - 1}." if count else "This assignment has no steps.")
        submission.steps_done = sorted(set(steps_done))
    if submission.status == "todo" and (status == "In progress" or submission.steps_done):
        submission.status = "in_progress"
    db.commit()
    return {"status": STATUS_LABELS[submission.status], "steps_done": list(submission.steps_done or [])}


def _form_fields(fields: dict | None) -> dict:
    fields = fields or {}
    clean = {}
    for name, limit in FORM_FIELDS.items():
        value = str(fields.get(name) or "").strip()
        if not value:
            raise _validation(name, "This field is required.")
        if len(value) > limit:
            raise _validation(name, f"Must be at most {limit} characters.")
        clean[name] = value
    return clean


def form_precheck(fields: dict) -> dict:
    checks = [{"ok": True, "blocking": False, "text": "Proposed topic filled in"}]
    if len(fields["Project summary"].split()) < SHORT_SUMMARY_WORDS:
        checks.append({"ok": False, "blocking": False, "text": "Project summary looks short."})
    else:
        checks.append({"ok": True, "blocking": False, "text": "Project summary is complete"})
    return approvals.precheck_summary(checks)


def submit(db: Session, student: Student, actor: User, assignment_id: int, fields: dict | None) -> dict:
    assignment, submission = _own(db, student, assignment_id)
    if submission.status in CLOSED:
        raise conflict("This assignment is already submitted.")
    precheck = None
    request = None
    if assignment.type == "Form":
        clean = _form_fields(fields)
        precheck = form_precheck(clean)
        submission.form_fields = clean
        request = approvals.create_form_request(db, student, assignment, clean, precheck)
    submission.status = "submitted"
    submission.submitted_at = now()
    submission.feedback = None
    audit.record(db, actor, "assignment.submit", f"Submitted {assignment.title}", target=("assignment", assignment.id),
                 changes={"approvalRequestId": request.id} if request else None)
    db.commit()
    return {"status": "Submitted", "submitted_at": iso_z(submission.submitted_at), "precheck": precheck}


def apply_form_decision(db: Session, request: ApprovalRequest) -> None:
    """Spec 23 calls this after deciding a `form` request: approved -> Graded "Approved"; changes requested ->
    back to In progress with the advisor's comment. The caller commits."""
    assignment_id = (request.payload or {}).get("assignmentId")
    submission = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment_id,
                                                       AssignmentSubmission.student_id == request.student_id).one_or_none()
    if submission is None:
        return
    if request.status == "approved":
        submission.status, submission.score_text, submission.feedback = "graded", "Approved", None
    elif request.status == "changes_requested":
        submission.status, submission.feedback = "in_progress", request.comment


def due_soon_count(db: Session, student: Student) -> int:
    """Open items due within a week, overdue included (the sidebar badge)."""
    limit = today() + timedelta(days=BADGE_DAYS)
    return sum(1 for e in list_for_student(db, student) if not e.closed and e.due <= limit)


def on_time_rate(db: Session, student: Student) -> tuple[int | None, int, int]:
    """(pct, on time, total) over items due up to today; late or missing submissions count against it."""
    due = [e for e in list_for_student(db, student) if e.due <= today()]
    on_time = sum(1 for e in due if e.submission.submitted_at is not None and e.submission.submitted_at <= e.assignment.due_at)
    return (round(on_time / len(due) * 100) if due else None), on_time, len(due)


def upcoming_tasks(db: Session, student: Student, limit: int = 4) -> list[dict]:
    """Dashboard deadlines: open items by due date, then done items newest first."""
    day = today()
    return [{"id": e.assignment.id, "title": e.assignment.title, "course": e.course, "due": short_date(e.due),
             "status": deadline_label(e, day)} for e in list_for_student(db, student)[:limit]]


def deadlines(db: Session, student: Student, start: date, end: date) -> list[dict]:
    """Open items due in [start, end] for the schedule (spec 14)."""
    rows = [{"id": f"as-{e.assignment.id}", "title": e.assignment.title, "course": e.course, "date": e.due.isoformat(),
             "label": short_date(e.due), "status": e.status}
            for e in list_for_student(db, student) if not e.closed and start <= e.due <= end]
    return sorted(rows, key=lambda row: (row["date"], row["course"], row["title"]))
