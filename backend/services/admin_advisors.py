"""Admin advisors (spec 32): caseload vs. capacity, adding advisors, capacity edits and reassignment.
Status: load above capacity is Over capacity, above 90% Near capacity, else Has room. Average response is the mean
decision time over the last 60 days. Reassigning moves the chosen students' assignments and their pending approval
requests; their upcoming meetings stay with the old advisor. A target may go at most 20% over its capacity."""
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import bad_request, conflict, not_found
from core.time import now
from models import MEETING_ACTIVE, Advisor, AdvisorStudentAssignment, ApprovalRequest, Meeting, Student, User
from services import audit, mailer, messages
from services.admin_users import create_invited
from services.approvals import avg_decision_days

RESPONSE_WINDOW = timedelta(days=60)
MEETING_WINDOW = timedelta(days=7)  # students with a meeting this soon stay with their advisor if possible
MIN_CAPACITY, MAX_CAPACITY = 1, 200
MAX_NAMES = 5  # names listed in the new advisor's notice


def status_for(load: int, cap: int) -> str:
    if load > cap:
        return "Over capacity"
    if load > 0.9 * cap:
        return "Near capacity"
    return "Has room"


def _fmt_days(days: float | None) -> str:
    return "—" if days is None else f"{days:.1f} days"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --- rows ----------------------------------------------------------------------------------------------------------

def list_advisors(db: Session, ids: list[int] | None = None) -> list[dict]:
    """Every advisor (invited and deactivated ones too), active first, then by name."""
    query = db.query(Advisor, User).join(User, User.user_id == Advisor.user_id)
    if ids is not None:
        query = query.filter(Advisor.advisor_id.in_(ids))
    pairs = query.all()
    loads = dict(db.query(AdvisorStudentAssignment.advisor_id, func.count(AdvisorStudentAssignment.student_id))
                 .group_by(AdvisorStudentAssignment.advisor_id))
    pending = dict(db.query(ApprovalRequest.advisor_id, func.count(ApprovalRequest.id))
                   .filter(ApprovalRequest.status == "pending", ApprovalRequest.advisor_id.isnot(None))
                   .group_by(ApprovalRequest.advisor_id))
    response = avg_decision_days(db, now() - RESPONSE_WINDOW)
    rows = []
    for advisor, user in sorted(pairs, key=lambda pair: (not pair[1].is_active, pair[1].name.lower())):
        load = loads.get(advisor.advisor_id, 0)
        rows.append({
            "id": advisor.advisor_id,
            "userId": user.user_id,
            "name": user.name,
            "dept": advisor.department or user.title or "—",
            "load": load,
            "cap": advisor.capacity,
            "pending": pending.get(advisor.advisor_id, 0),
            "resp": _fmt_days(response.get(advisor.advisor_id)),
            "status": status_for(load, advisor.capacity),
            "active": user.is_active,
        })
    return rows


def get_row(db: Session, advisor_id: int) -> dict:
    rows = list_advisors(db, [advisor_id])
    if not rows:
        raise not_found("Advisor")
    return rows[0]


def _advisor(db: Session, advisor_id: int) -> tuple[Advisor, User]:
    advisor = db.get(Advisor, advisor_id)
    if advisor is None:
        raise not_found("Advisor")
    return advisor, db.get(User, advisor.user_id)


# --- adding and editing --------------------------------------------------------------------------------------------

def add(db: Session, admin: User, data: dict, ip: str | None = None) -> dict:
    """An invited advisor (inactive until they accept). `data`: name, email, department, capacity."""
    email = data["email"].strip().lower()
    if db.query(User.user_id).filter(func.lower(User.email) == email).first() is not None:
        raise conflict("An account with this email already exists.")
    user, mail = create_invited(db, admin, email, "advisor", name=data["name"],
                                department=(data.get("department") or "").strip() or None)
    advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one()
    advisor.capacity = data.get("capacity") or 40
    audit.record(db, admin, "advisor.add", f"Added advisor {user.name}", ("advisor", advisor.advisor_id),
                 {"email": email, "department": advisor.department, "capacity": advisor.capacity}, ip=ip)
    db.commit()
    mailer.send_all([mail])
    return get_row(db, advisor.advisor_id)


def update(db: Session, admin: User, advisor_id: int, patch: dict, ip: str | None = None) -> dict:
    """`patch` holds only the fields sent: capacity, department (empty clears it), title (the user's title)."""
    advisor, user = _advisor(db, advisor_id)
    changes = {}
    if "capacity" in patch and patch["capacity"] != advisor.capacity:
        if not MIN_CAPACITY <= patch["capacity"] <= MAX_CAPACITY:
            raise bad_request(f"Capacity must be between {MIN_CAPACITY} and {MAX_CAPACITY}.")
        changes["capacity"] = [advisor.capacity, patch["capacity"]]
        advisor.capacity = patch["capacity"]
    if "department" in patch:
        department = (patch["department"] or "").strip() or None
        if department != advisor.department:
            changes["department"] = [advisor.department, department]
            advisor.department = department
    if "title" in patch:
        title = (patch["title"] or "").strip() or None
        if title != user.title:
            changes["title"] = [user.title, title]
            user.title = title
    if changes:
        audit.record(db, admin, "advisor.update", f"Updated {user.name}: {', '.join(changes)}",
                     ("advisor", advisor_id), changes, ip=ip)
    db.commit()
    return get_row(db, advisor_id)


# --- reassignment --------------------------------------------------------------------------------------------------

def _advisees(db: Session, advisor: Advisor) -> list[Student]:
    return (db.query(Student)
            .join(AdvisorStudentAssignment, AdvisorStudentAssignment.student_id == Student.student_id)
            .filter(AdvisorStudentAssignment.advisor_id == advisor.advisor_id).all())


def _meeting_students(db: Session, advisor: Advisor, student_ids: list[int], until=None) -> set[int]:
    """Students among `student_ids` with an active meeting with the advisor from now (until `until`, if given)."""
    if not student_ids:
        return set()
    query = db.query(Meeting.student_id).filter(
        Meeting.staff_user_id == advisor.user_id, Meeting.student_id.in_(student_ids),
        Meeting.status.in_(MEETING_ACTIVE), Meeting.starts_at >= now())
    if until is not None:
        query = query.filter(Meeting.starts_at < until)
    return {student_id for student_id, in query}


def pick_students(db: Session, advisor: Advisor, n: int) -> list[Student]:
    """The n advisees to move: fewest pending requests with this advisor first, then those without a meeting with
    them in the next 7 days, then by name, so in-flight work stays with the current advisor."""
    students = _advisees(db, advisor)
    ids = [s.student_id for s in students]
    pending = dict(db.query(ApprovalRequest.student_id, func.count(ApprovalRequest.id))
                   .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.status == "pending",
                           ApprovalRequest.student_id.in_(ids))
                   .group_by(ApprovalRequest.student_id)) if ids else {}
    soon = _meeting_students(db, advisor, ids, now() + MEETING_WINDOW)
    students.sort(key=lambda s: (pending.get(s.student_id, 0), s.student_id in soon, s.name.lower(), s.student_id))
    return students[:n]


def _chosen(db: Session, source: Advisor, source_user: User, count: int | None,
            student_ids: list[int] | None) -> list[Student]:
    load = db.query(func.count(AdvisorStudentAssignment.student_id)) \
        .filter(AdvisorStudentAssignment.advisor_id == source.advisor_id).scalar()
    if student_ids is not None:
        wanted = list(dict.fromkeys(student_ids))
        if not wanted:
            raise bad_request("Choose at least one advisee to move.")
        by_id = {s.student_id: s for s in _advisees(db, source)}
        if any(student_id not in by_id for student_id in wanted):
            raise bad_request(f"Those students aren't advised by {source_user.name}.")
        return [by_id[student_id] for student_id in wanted]
    if load == 0:
        raise bad_request(f"{source_user.name} has no advisees to move.")
    if count is None or not 1 <= count <= load:
        raise bad_request(f"Choose between 1 and {load} advisees.")
    return pick_students(db, source, count)


def reassign(db: Session, admin: User, from_id: int, to_id: int, count: int | None = None,
             student_ids: list[int] | None = None, ip: str | None = None) -> dict:
    """Moves `count` advisees (picked by pick_students) or exactly `student_ids` from one advisor to another."""
    source, source_user = _advisor(db, from_id)
    target, target_user = _advisor(db, to_id)
    if from_id == to_id:
        raise bad_request("Choose a different advisor.")
    if not target_user.is_active:
        raise bad_request("Choose an active advisor.")
    students = _chosen(db, source, source_user, count, student_ids)
    n = len(students)

    target_load = db.query(func.count(AdvisorStudentAssignment.student_id)) \
        .filter(AdvisorStudentAssignment.advisor_id == to_id).scalar()
    limit = target.capacity * 12 // 10
    if target_load + n > limit:
        room = max(0, limit - target_load)
        raise conflict(f"{target_user.name} can take at most {_plural(room, 'more advisee')} "
                       f"(capacity {target.capacity} + 20%).")

    ids = [s.student_id for s in students]
    at = now()
    db.query(AdvisorStudentAssignment).filter(AdvisorStudentAssignment.student_id.in_(ids)) \
        .update({AdvisorStudentAssignment.advisor_id: to_id, AdvisorStudentAssignment.updated_at: at},
                synchronize_session=False)
    db.query(ApprovalRequest).filter(ApprovalRequest.student_id.in_(ids), ApprovalRequest.advisor_id == from_id,
                                     ApprovalRequest.status == "pending") \
        .update({ApprovalRequest.advisor_id: to_id}, synchronize_session=False)

    mails = []
    student_users = {u.user_id: u for u in db.query(User).filter(User.user_id.in_([s.user_id for s in students]))}
    for student in students:
        messages.notify(db, student.user_id, f"Your advisor is now {target_user.name}.")
        user = student_users.get(student.user_id)
        if user is not None and user.is_active:
            mails.append(mailer.Mail(
                user.email, "Your advisor has changed",
                f"Hi {user.first_name or user.name},\n\nYour advisor is now {target_user.name}. "
                f"You can message them from Acadmate.\n\nAny meetings you already booked stay as they are."))
    kept = _meeting_students(db, source, ids)
    messages.notify(db, source_user.user_id, f"{n} of your advisees moved to {target_user.name}."
                    + (" Upcoming meetings stay on your calendar." if kept else ""))
    names = [s.name for s in sorted(students, key=lambda s: s.name.lower())]
    listed = ", ".join(names[:MAX_NAMES]) + (f" and {len(names) - MAX_NAMES} more" if len(names) > MAX_NAMES else "")
    messages.notify(db, target_user.user_id,
                    f"{_plural(n, 'advisee')} moved to you from {source_user.name}: {listed}.")
    audit.record(db, admin, "advisor.reassign",
                 f"Moved {_plural(n, 'advisee')} from {source_user.name} to {target_user.name}",
                 ("advisor", from_id), {"to": to_id, "studentIds": ids}, ip=ip)
    db.commit()
    mailer.send_all(mails)
    rows = {row["id"]: row for row in list_advisors(db, [from_id, to_id])}
    return {
        "moved": n,
        "from": rows[from_id],
        "to": rows[to_id],
        "message": f"Moved {_plural(n, 'advisee')} to {target_user.name}. "
                   + ("Students get an email." if n > 1 else "The student gets an email."),
    }
