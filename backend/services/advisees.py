"""An advisor's advisees: their risk level (shared with the advisor dashboard, spec 20) and the advisees list with
status, flag, credits and next meeting (spec 21)."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.time import local_zone, now, short_date, today
from models import (Advisor, AdvisorStudentAssignment, ApprovalRequest, Assignment, AssignmentSubmission, Conversation,
                    ConversationParticipant, Course, Enrollment, Meeting, PlanItem, Program, Student, User, UserSession)
from services.academics import gpa
from services.catalog import current_term, next_term, term_sort_key, terms_by_name
from services.degree_audit import GRADUATION_SEASON

GPA_DROP = 0.4
MISSED_DAYS = 14
MISSED_LIMIT = 3
INACTIVE_DAYS = 21
GPA_FLOOR = 3.0
FULL_TIME = 9
LEVELS = ("High", "Medium", "Low")
TABS = ("All", "Needs attention", "On track", "Graduating")
MEETING_STATUSES = ("requested", "confirmed")


def short_name(full: str) -> str:
    """"Amara Okafor" -> "Amara O."; a single name stays as it is."""
    parts = full.split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else full


def initials(name: str) -> str:
    """"Dr. Sarah Smith" -> "SS": first and last name, honorifics skipped."""
    parts = [p for p in name.replace(".", "").split() if p not in ("Dr", "Prof")]
    return "".join(p[0] for p in parts[:1] + parts[1:][-1:]).upper()


def grad_label(value: str | None) -> str | None:
    """"December 2026" / "Dec 2026" -> "Dec 2026"."""
    parts = (value or "").split()
    return f"{parts[0][:3]} {parts[-1]}" if len(parts) == 2 else None


def advisees(db: Session, advisor: Advisor) -> list[Student]:
    return (db.query(Student)
            .join(AdvisorStudentAssignment, AdvisorStudentAssignment.student_id == Student.student_id)
            .filter(AdvisorStudentAssignment.advisor_id == advisor.advisor_id)
            .order_by(Student.name).all())


@dataclass
class RiskContext:
    """Everything the risk rules read, loaded once for a group of students."""
    users: dict[int, User] = field(default_factory=dict)                 # student id -> user
    term_gpas: dict[int, list[float]] = field(default_factory=dict)      # student id -> term GPAs, oldest first
    cumulative: dict[int, float | None] = field(default_factory=dict)
    missed: dict[int, int] = field(default_factory=dict)                 # open items due in the last 14 days
    pending: dict[int, list[ApprovalRequest]] = field(default_factory=dict)
    last_sign_in: dict[int, datetime | None] = field(default_factory=dict)
    has_next_plan: set[int] = field(default_factory=set)


def risk_context(db: Session, students: list[Student]) -> RiskContext:
    ctx = RiskContext()
    ids = [s.student_id for s in students]
    if not ids:
        return ctx
    ctx.users = {s.student_id: db.get(User, s.user_id) for s in students}

    terms = terms_by_name(db)
    by_term: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    rows = (db.query(Enrollment.student_id, Enrollment.term, Course.credits, Enrollment.grade_points)
            .join(Course, Course.course_id == Enrollment.course_id)
            .filter(Enrollment.student_id.in_(ids), Enrollment.status == "completed", Enrollment.grade_points.isnot(None)))
    for student_id, term, credits, points in rows:
        by_term[student_id][term].append((credits, points))
    for student_id in ids:
        ordered = sorted(by_term[student_id], key=lambda name: term_sort_key(name, terms))
        ctx.term_gpas[student_id] = [gpa(by_term[student_id][name]) for name in ordered]
        ctx.cumulative[student_id] = gpa([row for name in ordered for row in by_term[student_id][name]])

    current = now()
    missed = (db.query(AssignmentSubmission.student_id, func.count())
              .join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
              .filter(AssignmentSubmission.student_id.in_(ids), AssignmentSubmission.status.in_(("todo", "in_progress")),
                      Assignment.due_at < current, Assignment.due_at >= current - timedelta(days=MISSED_DAYS))
              .group_by(AssignmentSubmission.student_id))
    ctx.missed = dict(missed.all())

    for request in (db.query(ApprovalRequest)
                    .filter(ApprovalRequest.student_id.in_(ids), ApprovalRequest.status == "pending")
                    .order_by(ApprovalRequest.created_at)):
        ctx.pending.setdefault(request.student_id, []).append(request)

    user_ids = [s.user_id for s in students]
    sessions = dict(db.query(UserSession.user_id, func.max(UserSession.created_at))
                    .filter(UserSession.user_id.in_(user_ids)).group_by(UserSession.user_id).all())
    for s in students:
        times = [t for t in (sessions.get(s.user_id), ctx.users[s.student_id].last_login_at) if t is not None]
        ctx.last_sign_in[s.student_id] = max(times) if times else None

    upcoming = next_term(db)
    if upcoming is not None:
        ctx.has_next_plan = {student_id for student_id, in db.query(PlanItem.student_id).distinct()
                             .filter(PlanItem.student_id.in_(ids), PlanItem.term_id == upcoming.id)}
    return ctx


def _failed_check(request: ApprovalRequest) -> str | None:
    """The first failing blocking check's text, else None."""
    for check in (request.precheck or {}).get("checks", []):
        if not check.get("ok") and check.get("blocking"):
            return check.get("text") or "a pre-check failed"
    return None


def _drops_below_full_time(request: ApprovalRequest) -> bool:
    return request.type in ("other", "swap") and (request.payload or {}).get("kind") == "drop" \
        and (request.payload or {}).get("creditsAfter", FULL_TIME) < FULL_TIME


failed_check = _failed_check  # shared with the advisor reports (spec 26)
drops_below_full_time = _drops_below_full_time


def risk_for(student: Student, ctx: RiskContext) -> tuple[str, str | None]:
    """(level, flag sentence). The first matching rule wins: High, then Medium, else Low."""
    user = ctx.users.get(student.student_id)
    first = (user.preferred_name or user.first_name) if user else student.name.split()[0]
    term_gpas = [g for g in ctx.term_gpas.get(student.student_id, []) if g is not None]
    pending = ctx.pending.get(student.student_id, [])
    drop = next((r for r in pending if _drops_below_full_time(r)), None)

    if len(term_gpas) >= 2 and term_gpas[-2] - term_gpas[-1] >= GPA_DROP - 1e-9:
        before, after = f"{term_gpas[-2]:.1f}", f"{term_gpas[-1]:.1f}"
        tail = f" and {first} asked to drop a course" if drop else ""
        return "High", f"Term GPA fell from {before} to {after}{tail}."
    missed = ctx.missed.get(student.student_id, 0)
    if missed >= MISSED_LIMIT:
        return "High", f"{first} missed {missed} deadlines in the last two weeks."
    if drop:
        return "High", f"{first} asked to drop a course, which leaves {drop.payload['creditsAfter']} credits."

    last = ctx.last_sign_in.get(student.student_id)
    if (last is None or last < now() - timedelta(days=INACTIVE_DAYS)) and student.student_id not in ctx.has_next_plan:
        return "Medium", f"{first} hasn't signed in for {INACTIVE_DAYS}+ days and has no plan for next term."
    for request in pending:
        failed = _failed_check(request)
        if failed:
            return "Medium", f"{request.title}: {failed[0].lower() + failed[1:]}"
    cumulative = ctx.cumulative.get(student.student_id)
    if cumulative is not None and cumulative < GPA_FLOOR:
        return "Medium", f"Cumulative GPA is {cumulative:.2f}, below {GPA_FLOOR:.1f}."
    return "Low", None


def levels(db: Session, advisor: Advisor) -> tuple[RiskContext, list[tuple[Student, str, str | None]]]:
    """The advisor's advisees with (level, flag), and the context the rules read."""
    students = advisees(db, advisor)
    ctx = risk_context(db, students)
    return ctx, [(s, *risk_for(s, ctx)) for s in students]


def attention_count(db: Session, advisor: Advisor) -> int:
    """Advisees with risk High or Medium (the advisor's Advisees badge)."""
    return sum(1 for _, level, _ in levels(db, advisor)[1] if level != "Low")


def last_contact(db: Session, advisor: Advisor, students: list[Student]) -> dict[int, date]:
    """Latest past meeting or direct message between the advisor and each student, as a school-time date."""
    if not students:
        return {}
    current = now()
    result: dict[int, datetime] = {}
    meetings = (db.query(Meeting.student_id, func.max(Meeting.starts_at))
                .filter(Meeting.staff_user_id == advisor.user_id, Meeting.starts_at <= current,
                        Meeting.student_id.in_([s.student_id for s in students]),
                        Meeting.status.in_(("confirmed", "completed")))
                .group_by(Meeting.student_id))
    for student_id, at in meetings:
        result[student_id] = at

    by_user = {s.user_id: s.student_id for s in students}
    mine = (db.query(ConversationParticipant.conversation_id)
            .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
            .filter(Conversation.kind == "direct", ConversationParticipant.user_id == advisor.user_id).subquery())
    direct = (db.query(ConversationParticipant.user_id, Conversation.last_message_at)
              .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
              .filter(ConversationParticipant.conversation_id.in_(mine.select()),
                      ConversationParticipant.user_id.in_(list(by_user))))
    for user_id, at in direct:
        student_id = by_user[user_id]
        at = min(at, current)
        if student_id not in result or at > result[student_id]:
            result[student_id] = at
    return {student_id: at.astimezone(local_zone()).date() for student_id, at in result.items()}


# --- advisees list (spec 21) --------------------------------------------------------------------------------------

def _credits(db: Session, ids: list[int]) -> dict[int, tuple[float, float]]:
    """Student id -> (earned, in-progress) credits. An F earns nothing (as in degree_audit)."""
    totals = {student_id: [0.0, 0.0] for student_id in ids}
    rows = (db.query(Enrollment.student_id, Enrollment.status, Enrollment.grade, Course.credits)
            .join(Course, Course.course_id == Enrollment.course_id).filter(Enrollment.student_id.in_(ids)))
    for student_id, status, grade, credits in rows:
        if status == "completed" and (grade or "").upper() != "F":
            totals[student_id][0] += float(credits)
        elif status == "in_progress":
            totals[student_id][1] += float(credits)
    return {student_id: (earned, doing) for student_id, (earned, doing) in totals.items()}


def _next_meetings(db: Session, advisor: Advisor, ids: list[int], day: date) -> dict[int, Meeting]:
    """Each student's earliest active meeting with the advisor from the start of today (school time)."""
    start = datetime.combine(day, time(0), local_zone()).astimezone(timezone.utc)
    result: dict[int, Meeting] = {}
    meetings = (db.query(Meeting)
                .filter(Meeting.staff_user_id == advisor.user_id, Meeting.student_id.in_(ids),
                        Meeting.status.in_(MEETING_STATUSES), Meeting.starts_at >= start)
                .order_by(Meeting.starts_at))
    for meeting in meetings:
        result.setdefault(meeting.student_id, meeting)
    return result


def next_meeting_label(meeting: Meeting | None, day: date) -> str:
    """"Today · 15:00", "Oct 5 · 11:00" or "Not booked"."""
    if meeting is None:
        return "Not booked"
    local = meeting.starts_at.astimezone(local_zone())
    when = "Today" if local.date() == day else short_date(local.date())
    return f"{when} · {local.strftime('%H:%M')}"


def _graduation_key(value: str | None) -> tuple[str, int] | None:
    """"December 2026" -> ("Fall", 2026)."""
    parts = (value or "").split()
    if len(parts) != 2 or parts[0][:3] not in GRADUATION_SEASON or not parts[1].isdigit():
        return None
    return GRADUATION_SEASON[parts[0][:3]], int(parts[1])


def is_graduating(expected: str | None, earned: float, doing: float, required: float,
                  terms: set[tuple[str, int]]) -> bool:
    """Graduates this or next term, and the courses in progress cover every remaining credit."""
    return _graduation_key(expected) in terms and required - earned <= doing


def status_for(level: str, graduating: bool) -> str:
    if graduating:
        return "Graduating"
    return "Needs attention" if level != "Low" else "On track"


def flag_for(level: str, risk_flag: str | None, pending: list[ApprovalRequest], graduating: bool) -> str | None:
    """A High risk first, then a request ready for approval, then any other risk, then the graduation step."""
    if level == "High":
        return risk_flag
    ready = next((r for r in pending if _failed_check(r) is None), None)
    if ready is not None:
        return f"{ready.title} waiting for your approval"
    if risk_flag:
        return risk_flag
    return "Final graduation audit due" if graduating else None


def _subtitle(n: int, department: str | None) -> str:
    count = f"{n} student{'' if n == 1 else 's'}"
    return f"{count} · {department} graduate programs" if department else count


def caseload(db: Session, advisor: Advisor, day: date | None = None) -> tuple[list[dict], RiskContext]:
    """Every advisee's row (status, risk, flag, credits, next meeting) plus the risk context, unsorted. Rows also
    carry the private keys `_student`, `_sort` and `_riskFlag`; list_for() and the reports (spec 26) drop them."""
    day = day or today()
    students = advisees(db, advisor)
    ids = [s.student_id for s in students]
    ctx = risk_context(db, students)
    credits = _credits(db, ids) if ids else {}
    meetings = _next_meetings(db, advisor, ids, day) if ids else {}
    programs = {p.program_id: p for p in
                db.query(Program).filter(Program.program_id.in_({s.program_id for s in students}))} if ids else {}
    terms = {(t.season, t.year) for t in (current_term(db), next_term(db)) if t is not None}

    rows = []
    for student in students:
        level, risk_flag = risk_for(student, ctx)
        program = programs.get(student.program_id)
        required = float(program.total_required_credits) if program else 0.0
        earned, doing = credits.get(student.student_id, (0.0, 0.0))
        graduating = is_graduating(student.expected_graduation, earned, doing, required, terms)
        cumulative = ctx.cumulative.get(student.student_id)
        user = ctx.users.get(student.student_id)
        rows.append({
            "studentId": student.student_id, "userId": student.user_id, "name": short_name(student.name),
            "fullName": student.name, "initials": initials(student.name),
            "program": program.program_name if program else None, "credits": earned, "requiredCredits": required,
            "gpa": f"{cumulative:.2f}" if cumulative is not None else "—",
            "status": status_for(level, graduating), "risk": level,
            "flag": flag_for(level, risk_flag, ctx.pending.get(student.student_id, []), graduating),
            "next": next_meeting_label(meetings.get(student.student_id), day),
            "graduates": grad_label(student.expected_graduation),
            "_sort": ((user.last_name if user and user.last_name else student.name.split()[-1]).casefold(), student.name),
            "_student": student,
            "_riskFlag": risk_flag,
        })
    return rows, ctx


def list_for(db: Session, advisor: Advisor, status: str = "All", q: str | None = None, day: date | None = None) -> dict:
    """The advisees screen: tab counts over every advisee, then the rows matching status and q."""
    rows, _ = caseload(db, advisor, day)
    tabs = [{"label": label, "count": len(rows) if label == "All" else sum(1 for r in rows if r["status"] == label)}
            for label in TABS]
    shown = rows
    if status == "At risk":
        shown = [r for r in shown if r["risk"] == "High"]
    elif status != "All":
        shown = [r for r in shown if r["status"] == status]
    if q and q.strip():
        needle = q.strip().casefold()
        shown = [r for r in shown if needle in r["fullName"].casefold()]
    attention = lambda r: r["status"] == "Needs attention"  # noqa: E731
    shown.sort(key=lambda r: (not attention(r), LEVELS.index(r["risk"]) if attention(r) else 0, r["_sort"]))
    for row in rows:
        del row["_sort"], row["_student"], row["_riskFlag"]
    return {"subtitle": _subtitle(len(rows), advisor.department), "tabs": tabs, "rows": shown, "total": len(rows)}
