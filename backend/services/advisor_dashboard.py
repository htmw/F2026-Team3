"""The advisor dashboard (spec 20): summary tiles, approval queue, today's meetings, students needing attention,
caseload and expected graduation. Risk levels come from services/advisees (spec 21), the queue from
services/approvals (spec 23)."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from core.time import day_label, local_zone, now, short_date, today
from models import Advisor, AdvisorAvailability, ApprovalRequest, Meeting, Program, Student, User
from services import approvals
from services.advisees import grad_label, initials, levels, last_contact, short_name
from services.catalog import current_term, next_term
from services.preferences import GRADUATION_MONTHS

QUEUE_LIMIT = 5
ATTENTION_LIMIT = 3
BUSY_WEEK = 8
JOIN_MINUTES = 10
PROGRAM_SHORT = {"Computer Science": "CS", "Information Systems": "IS"}
CASELOAD = (("Low", "On track", "accent"), ("Medium", "Needs attention", "amber"), ("High", "At risk", "pink"))


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(0), local_zone()).astimezone(timezone.utc)
    return start, datetime.combine(day + timedelta(days=1), time(0), local_zone()).astimezone(timezone.utc)


def display_name(user: User) -> str:
    """"Dr. Sarah Smith" -> "Dr. Smith"; names without an honorific stay whole."""
    first = user.name.split()[0]
    return f"{first} {user.last_name}" if first in ("Dr.", "Prof.") and user.last_name else user.name


def _short_program(name: str) -> str:
    for long, short in PROGRAM_SHORT.items():
        name = name.replace(long, short)
    return name


def header(db: Session, advisor: Advisor, user: User) -> dict:
    term = current_term(db)
    title = user.title or "Faculty advisor"
    department = advisor.department if advisor.department and advisor.department not in title else None
    parts = [title, department, term.name if term else None]
    return {"displayName": display_name(user), "subtitle": " · ".join(p for p in parts if p),
            "initials": initials(user.name)}


def _week_meetings(db: Session, advisor: Advisor, day: date) -> list[Meeting]:
    monday = day - timedelta(days=day.weekday())
    start, _ = _day_bounds(monday)
    _, end = _day_bounds(monday + timedelta(days=6))
    return (db.query(Meeting)
            .filter(Meeting.staff_user_id == advisor.user_id, Meeting.status.in_(("requested", "confirmed")),
                    Meeting.starts_at >= start, Meeting.starts_at < end)
            .order_by(Meeting.starts_at).all())


def stats(db: Session, students: list[Student], waiting: int, week: list[Meeting], attention: int, day: date) -> list[dict]:
    term = current_term(db)
    program_ids = {s.program_id for s in students}
    names = [_short_program(p.program_name) for p in
             db.query(Program).filter(Program.program_id.in_(program_ids)).order_by(Program.program_name)] if program_ids else []
    todays = sum(1 for m in week if m.starts_at.astimezone(local_zone()).date() == day)
    busy = len(week) >= BUSY_WEEK
    return [
        {"key": "advisees", "label": "Advisees", "value": str(len(students)), "tag": term.name if term else None,
         "tone": "gray", "note": " and ".join(names) or "No advisees yet"},
        {"key": "waiting", "label": "Waiting for you", "value": str(waiting), "tag": "Action" if waiting else "Clear",
         "tone": "amber" if waiting else "teal", "note": "Plans, forms and requests"},
        {"key": "meetings", "label": "Meetings this week", "value": str(len(week)),
         "tag": "Busy" if busy else "This week", "tone": "indigo" if busy else "gray", "note": f"{todays} today"},
        {"key": "attention", "label": "Need attention", "value": str(attention), "tag": "Review", "tone": "pink",
         "note": "Flagged by Acadmate"},
    ]


def _check(request: ApprovalRequest) -> tuple[bool, str]:
    """(ok, check line): the first failing blocking check (lower-cased first letter), else the all-clear."""
    for check in (request.precheck or {}).get("checks", []):
        if not check.get("ok") and check.get("blocking"):
            text = check.get("text") or "a pre-check failed"
            return False, text[0].lower() + text[1:]
    return True, "meets all remaining requirements"


def queue(db: Session, advisor: Advisor, limit: int = QUEUE_LIMIT) -> tuple[list[dict], int]:
    query = approvals.pending_query(db, advisor)
    total = query.count()
    rows = []
    for request in query.limit(limit):
        student = db.get(Student, request.student_id)
        ok, check = _check(request)
        rows.append({"id": request.id, "studentId": student.student_id, "name": short_name(student.name),
                     "initials": initials(student.name), "type": approvals.type_label(request), "item": request.title,
                     "when": short_date(request.created_at.astimezone(local_zone()).date()), "check": check, "ok": ok})
    return rows, total


def today_meetings(db: Session, advisor: Advisor, day: date) -> dict:
    start, end = _day_bounds(day)
    current = now()
    rows = []
    meetings = (db.query(Meeting, Student)
                .join(Student, Student.student_id == Meeting.student_id)
                .filter(Meeting.staff_user_id == advisor.user_id, Meeting.status.in_(("requested", "confirmed")),
                        Meeting.starts_at >= start, Meeting.starts_at < end))
    for meeting, student in meetings:
        record = f"/advisor/advisees/{student.student_id}"
        if meeting.ends_at <= current:
            action, href = "Notes", record
        elif meeting.format == "online" and meeting.video_url and current >= meeting.starts_at - timedelta(minutes=JOIN_MINUTES):
            action, href = "Join", meeting.video_url
        else:
            action, href = "Open", record
        mode = "Online" if meeting.format == "online" else "In person"
        rows.append({"id": f"mtg-{meeting.id}", "time": meeting.starts_at.astimezone(local_zone()).strftime("%H:%M"),
                     "who": short_name(student.name), "studentId": student.student_id,
                     "topic": f"{meeting.topic} · {mode}", "action": action, "href": href})
    hours = (db.query(AdvisorAvailability)
             .filter(AdvisorAvailability.staff_user_id == advisor.user_id, AdvisorAvailability.kind == "office_hours",
                     AdvisorAvailability.weekday == day.weekday()))
    for window in hours:
        rows.append({"id": f"off-{window.id}", "time": window.start_time.strftime("%H:%M"), "who": "Drop-in office hours",
                     "studentId": None, "topic": window.location or "Office hours", "action": "Details",
                     "href": "/advisor/meetings"})
    rows.sort(key=lambda row: row["time"])
    return {"label": day_label(day), "meetings": rows}


def graduation_buckets(db: Session, students: list[Student]) -> list[dict]:
    labels = [f"{GRADUATION_MONTHS[t.season][:3]} {t.year}" for t in (current_term(db), next_term(db)) if t is not None]
    counts = {label: 0 for label in labels}
    later = 0
    for student in students:
        label = grad_label(student.expected_graduation)
        if label in counts:
            counts[label] += 1
        else:
            later += 1
    return [{"n": n, "label": label} for label, n in counts.items()] + [{"n": later, "label": "Later"}]


def build(db: Session, advisor: Advisor, day: date | None = None) -> dict:
    day = day or today()
    user = db.get(User, advisor.user_id)
    ctx, rated = levels(db, advisor)
    students = [s for s, _, _ in rated]
    flagged = [(s, level, flag) for s, level, flag in rated if level != "Low"]
    contact = last_contact(db, advisor, [s for s, _, _ in flagged])

    flagged.sort(key=lambda row: (row[1] != "High", contact.get(row[0].student_id, date.min)))
    attention = []
    for student, level, flag in flagged[:ATTENTION_LIMIT]:
        cumulative = ctx.cumulative.get(student.student_id)
        last = contact.get(student.student_id)
        attention.append({"studentId": student.student_id, "userId": student.user_id, "name": short_name(student.name),
                          "initials": initials(student.name), "flag": flag,
                          "gpa": f"{cumulative:.2f}".rstrip("0").rstrip(".") if cumulative is not None else "—",
                          "last": short_date(last) if last else "—", "level": level})

    counts = {level: 0 for level, _, _ in CASELOAD}
    for _, level, _ in rated:
        counts[level] += 1
    rows, total = queue(db, advisor)
    return {
        "advisor": header(db, advisor, user),
        "stats": stats(db, students, total, _week_meetings(db, advisor, day), len(flagged), day),
        "queue": rows,
        "queueTotal": total,
        "today": today_meetings(db, advisor, day),
        "attention": attention,
        "caseload": [{"label": label, "n": counts[level], "tone": tone} for level, label, tone in CASELOAD],
        "graduation": graduation_buckets(db, students),
        "prechecks": approvals.prechecks_on(db, advisor),
    }
