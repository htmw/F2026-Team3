"""Admin users (spec 31): the user list, invites, CSV import, edits and password resets.
Status: Active = is_active; Invited = inactive and never set a password; Deactivated = inactive with a password.
"Program or department" is the student's program, an advisor's department (spec 32), else the staff title."""
import csv
import io
from datetime import timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.errors import ApiError, bad_request, conflict, not_found
from core.time import MONTH_NAMES, iso_z, local_zone, now, short_date, today
from models import Advisor, AdvisorStudentAssignment, Enrollment, Program, Student, User, UserSession
from services import audit, mailer, messages
from services.auth import DEFAULT_PROGRAM_ID, issue_invite, issue_reset_link, name_from_email, split_name, user_payload

ROLES = ("student", "advisor", "admin")
ROLE_LABELS = {"student": "Student", "advisor": "Advisor", "admin": "Admin"}
TAB_KEYS = {"student": "Students", "advisor": "Advisors", "admin": "Admins"}
STATUSES = ("Active", "Invited", "Deactivated")
MAX_IMPORT_ROWS = 5000
MAX_IMPORT_BYTES = 1024 * 1024
IMPORT_HEADER = ["name", "email", "role", "program"]
RECENT_DAYS = 30
SELF_CHANGE = "You can't change your own account here."


# --- status, labels and rows ---------------------------------------------------------------------------------------

def status_of(user: User) -> str:
    if user.is_active:
        return "Active"
    return "Invited" if user.password_hash is None else "Deactivated"


def _status_filter(status: str):
    if status == "Active":
        return User.is_active.is_(True)
    if status == "Invited":
        return (User.is_active.is_(False)) & (User.password_hash.is_(None))
    return (User.is_active.is_(False)) & (User.password_hash.isnot(None))


def _last_active(at) -> str:
    """"Today", "Yesterday", "Sep 29" within 30 days, else "Aug 2026"; "Never" without a sign-in."""
    if at is None:
        return "Never"
    day = at.astimezone(local_zone()).date()
    if day == today():
        return "Today"
    if day == today() - timedelta(days=1):
        return "Yesterday"
    if today() - day <= timedelta(days=RECENT_DAYS):
        return short_date(day)
    return f"{MONTH_NAMES[day.month - 1]} {day.year}"


def normalize_role(role: str | None) -> str:
    """"all" | "student" | "advisor" | "admin"; accepts "Student", "Students", "ALL"."""
    value = (role or "all").strip().lower()
    value = value[:-1] if value.endswith("s") and value[:-1] in ROLES else value
    if value != "all" and value not in ROLES:
        raise bad_request(f"Unknown role \"{role}\".")
    return value


def _rows(db: Session, users: list[User]) -> list[dict]:
    """Contract rows for `users`, loading their student, program, advisor and last sign-in in a few batch queries."""
    ids = [user.user_id for user in users]
    if not ids:
        return []
    students = {s.user_id: s for s in db.query(Student).filter(Student.user_id.in_(ids))}
    programs = {p.program_id: p.program_name for p in db.query(Program)}
    student_ids = [s.student_id for s in students.values()]
    assigned = dict(db.query(AdvisorStudentAssignment.student_id, AdvisorStudentAssignment.advisor_id)
                    .filter(AdvisorStudentAssignment.student_id.in_(student_ids))) if student_ids else {}
    advisor_names = dict(db.query(Advisor.advisor_id, User.name).join(User, User.user_id == Advisor.user_id)
                         .filter(Advisor.advisor_id.in_(set(assigned.values())))) if assigned else {}
    departments = dict(db.query(Advisor.user_id, Advisor.department).filter(Advisor.user_id.in_(ids)))
    last = dict(db.query(UserSession.user_id, func.max(UserSession.created_at))
                .filter(UserSession.user_id.in_(ids)).group_by(UserSession.user_id))
    out = []
    for user in users:
        student = students.get(user.user_id) if user.role == "student" else None
        advisor_id = assigned.get(student.student_id) if student else None
        at = last.get(user.user_id)
        out.append({
            "id": user.user_id,
            "name": user.name,
            "initials": user_payload(user)["initials"],
            "email": user.email,
            "role": ROLE_LABELS[user.role],
            "dept": programs.get(student.program_id, "—") if student
            else ((departments.get(user.user_id) if user.role == "advisor" else None) or user.title or "—"),
            "programId": student.program_id if student else None,
            "status": status_of(user),
            "lastActive": _last_active(at),
            "lastActiveAt": iso_z(at) if at else None,
            "studentId": student.student_id if student else None,
            "advisorId": advisor_id,
            "advisorName": advisor_names.get(advisor_id),
        })
    return out


def get_row(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    return _rows(db, [user])[0]


def advisor_options(db: Session) -> list[dict]:
    """Active advisors with their advisee counts, for the Assigned advisor select."""
    counts = dict(db.query(AdvisorStudentAssignment.advisor_id, func.count(AdvisorStudentAssignment.student_id))
                  .group_by(AdvisorStudentAssignment.advisor_id))
    rows = (db.query(Advisor, User).join(User, User.user_id == Advisor.user_id)
            .filter(User.is_active.is_(True)).order_by(User.name))
    return [{"id": advisor.advisor_id, "userId": user.user_id, "name": user.name,
             "advisees": counts.get(advisor.advisor_id, 0)} for advisor, user in rows]


def list_users(db: Session, role: str = "all", q: str = "", status: str | None = None, page: int = 1,
               size: int = 50) -> dict:
    """One page of users ordered by name. Tab counts follow the search and status filter, not the role tab."""
    role = normalize_role(role)
    query = db.query(User)
    q = (q or "").strip()
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
    if status:
        query = query.filter(_status_filter(status))
    by_role = dict(query.with_entities(User.role, func.count(User.user_id)).group_by(User.role))
    counts = {"All": sum(by_role.values()), **{TAB_KEYS[r]: by_role.get(r, 0) for r in ROLES}}
    if role != "all":
        query = query.filter(User.role == role)
    total = counts["All"] if role == "all" else counts[TAB_KEYS[role]]
    users = query.order_by(func.lower(User.name), User.user_id).offset((page - 1) * size).limit(size).all()
    return {
        "rows": _rows(db, users),
        "total": total,
        "page": page,
        "pageSize": size,
        "counts": counts,
        "advisors": advisor_options(db),
        "programs": [{"id": p.program_id, "name": p.program_name}
                     for p in db.query(Program).order_by(Program.program_name)],
    }


# --- creating and changing users -----------------------------------------------------------------------------------

def _valid_email(raw: str) -> str | None:
    try:
        return validate_email(raw.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def _email_taken(db: Session, email: str) -> bool:
    return db.query(User.user_id).filter(func.lower(User.email) == email).first() is not None


def _ensure_role_rows(db: Session, user: User, program_id: int = DEFAULT_PROGRAM_ID) -> None:
    """Students need a students row, advisors an advisors row (rows from an earlier role are kept)."""
    if user.role == "student" and db.query(Student).filter(Student.user_id == user.user_id).first() is None:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=program_id))
    if user.role == "advisor" and db.query(Advisor).filter(Advisor.user_id == user.user_id).first() is None:
        db.add(Advisor(user_id=user.user_id))
    db.flush()


def create_invited(db: Session, admin: User, email: str, role: str, name: str | None = None,
                   program_id: int = DEFAULT_PROGRAM_ID, title: str | None = None,
                   department: str | None = None) -> tuple[User, mailer.Mail]:
    """An inactive user with the row their role needs and a fresh invite. Send the mail after the caller commits.
    Shared with admin advisors (spec 32)."""
    full, first, last = split_name(name or name_from_email(email))
    user = User(name=full, first_name=first, last_name=last, email=email, role=role, is_active=False,
                password_hash=None, title=title if role != "student" else None)
    db.add(user)
    db.flush()
    _ensure_role_rows(db, user, program_id)
    if role == "advisor" and department:
        db.query(Advisor).filter(Advisor.user_id == user.user_id).one().department = department
    return user, issue_invite(db, user, admin.name)


def _apply_role(db: Session, user: User, new_role: str) -> None:
    """Checks before changing anything, so a refusal leaves the user as it was."""
    if new_role == user.role:
        return
    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user.user_id).first()
        if student is not None:
            if db.query(Enrollment.enrollment_id).filter(Enrollment.student_id == student.student_id).first():
                raise conflict("Students with course records can't change role.")
            db.query(AdvisorStudentAssignment).filter(
                AdvisorStudentAssignment.student_id == student.student_id).delete()
    if user.role == "advisor":
        advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).first()
        if advisor is not None and db.query(AdvisorStudentAssignment).filter(
                AdvisorStudentAssignment.advisor_id == advisor.advisor_id).first():
            raise conflict("Move their advisees first.")
    user.role = new_role
    _ensure_role_rows(db, user)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def invite(db: Session, admin: User, emails: list[str], role: str, ip: str | None = None) -> dict:
    sent, skipped, seen, mails = [], [], set(), []
    for raw in emails:
        email = _valid_email(raw)
        if email is None:
            skipped.append({"email": raw.strip(), "reason": "not a valid email"})
        elif email in seen:
            skipped.append({"email": email, "reason": "listed twice"})
        elif _email_taken(db, email):
            skipped.append({"email": email, "reason": "already has an account"})
        else:
            mails.append(create_invited(db, admin, email, role)[1])
            sent.append(email)
        if email:
            seen.add(email)
    if sent:
        audit.record(db, admin, "user.invite", f"Invited {_plural(len(sent), ROLE_LABELS[role].lower())}",
                     changes={"emails": sent, "role": role}, ip=ip)
    db.commit()
    mailer.send_all(mails)
    return {"sent": len(sent), "skipped": skipped}


def import_csv(db: Session, admin: User, text: str, ip: str | None = None) -> dict:
    """Upserts users by email from `name,email,role,program`; bad rows are skipped and reported by line."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if not header or [h.strip().lower() for h in header] != IMPORT_HEADER:
        raise bad_request("The first line must be the header: name,email,role,program.")
    rows = [(reader.line_num, row) for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise bad_request("The file has no users.")
    if len(rows) > MAX_IMPORT_ROWS:
        raise bad_request(f"Import at most {MAX_IMPORT_ROWS:,} users at a time.")

    programs = {p.program_name.strip().lower(): p for p in db.query(Program)}
    created = updated = 0
    skipped, seen, mails = [], set(), []
    for line, row in rows:
        name, email_raw, role, program = ([cell.strip() for cell in row] + [""] * 4)[:4]
        role = role.lower()
        email = _valid_email(email_raw)
        reason = None
        if len(row) > 4:
            reason = "Too many columns"
        elif not name:
            reason = "Missing name"
        elif email is None:
            reason = f"Not a valid email \"{email_raw}\""
        elif email in seen:
            reason = f"{email} is listed earlier in the file"
        elif role not in ROLES:
            reason = f"Unknown role \"{role}\" (use student, advisor or admin)"
        elif role == "student" and program.lower() not in programs:
            reason = f"Unknown program \"{program}\"" if program else "Missing program for a student"
        if reason:
            skipped.append({"line": line, "reason": reason})
            continue
        seen.add(email)
        program_id = programs[program.lower()].program_id if role == "student" else DEFAULT_PROGRAM_ID
        dept = (program or None) if role != "student" else None  # staff rows: the column is their department

        user = db.query(User).filter(func.lower(User.email) == email).one_or_none()
        if user is None:
            mails.append(create_invited(db, admin, email, role, name=name, program_id=program_id,
                                        title=dept if role == "admin" else None,
                                        department=dept if role == "advisor" else None)[1])
            created += 1
            continue
        try:
            _apply_role(db, user, role)
        except ApiError as err:
            skipped.append({"line": line, "reason": err.message})
            continue
        user.name, user.first_name, user.last_name = split_name(name)
        student = db.query(Student).filter(Student.user_id == user.user_id).first()
        if student is not None:
            student.name = user.name
            if role == "student":
                student.program_id = program_id
        if role == "advisor" and dept:
            db.query(Advisor).filter(Advisor.user_id == user.user_id).one().department = dept
        elif role == "admin" and dept:
            user.title = dept
        updated += 1

    audit.record(db, admin, "user.import", f"Imported {_plural(created + updated, 'user')}",
                 changes={"created": created, "updated": updated, "skipped": len(skipped)}, ip=ip)
    db.commit()
    mailer.send_all(mails)
    return {"created": created, "updated": updated, "skipped": skipped, "file": None}


def update(db: Session, admin: User, user_id: int, patch: dict, ip: str | None = None) -> dict:
    """`patch` holds only the fields the admin sent: role, advisorId (None unassigns), programId, status."""
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    if user.user_id == admin.user_id and ({"role", "status"} & patch.keys()):
        raise conflict(SELF_CHANGE)
    changes = {}

    if "role" in patch and patch["role"] != user.role:
        before = user.role
        _apply_role(db, user, patch["role"])
        changes["role"] = [before, user.role]

    if "advisorId" in patch or "programId" in patch:
        student = db.query(Student).filter(Student.user_id == user.user_id).first()
        if user.role != "student" or student is None:
            raise bad_request("Only students have an advisor and a program.")
        if "advisorId" in patch:
            changes.update(_set_advisor(db, user, student, patch["advisorId"]))
        if "programId" in patch and patch["programId"] != student.program_id:
            if db.get(Program, patch["programId"]) is None:
                raise bad_request("Unknown program.")
            changes["program"] = [student.program_id, patch["programId"]]
            student.program_id = patch["programId"]

    if "status" in patch and patch["status"] != status_of(user):
        before = status_of(user)
        if patch["status"] == "Deactivated":
            user.is_active = False
            db.query(UserSession).filter(UserSession.user_id == user.user_id, UserSession.revoked_at.is_(None)) \
                .update({UserSession.revoked_at: now()})
        elif user.password_hash is None:
            raise conflict("Invited users activate through their invite link. Re-send the invite instead.")
        else:
            user.is_active = True
        changes["status"] = [before, status_of(user)]

    if changes:
        audit.record(db, admin, "user.update", f"Updated {user.name}: {', '.join(changes)}", ("user", user.user_id),
                     changes, ip=ip)
    db.commit()
    return get_row(db, user.user_id)


def _set_advisor(db: Session, user: User, student: Student, advisor_id: int | None) -> dict:
    current = db.get(AdvisorStudentAssignment, student.student_id)
    before = current.advisor_id if current else None
    if advisor_id == before:
        return {}
    if advisor_id is None:
        db.delete(current)
        return {"advisor": [before, None]}
    advisor = db.get(Advisor, advisor_id)
    advisor_user = db.get(User, advisor.user_id) if advisor else None
    if advisor_user is None or not advisor_user.is_active:
        raise bad_request("Choose an active advisor.")
    if current is None:
        db.add(AdvisorStudentAssignment(student_id=student.student_id, advisor_id=advisor_id, updated_at=now()))
    else:
        current.advisor_id, current.updated_at = advisor_id, now()
    messages.notify(db, user.user_id, f"Your advisor is now {advisor_user.name}.")
    return {"advisor": [before, advisor_id]}


def send_reset(db: Session, admin: User, user_id: int, ip: str | None = None) -> None:
    """Active: a password reset link. Invited: a fresh invite. Deactivated: refused."""
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    status = status_of(user)
    if status == "Deactivated":
        raise conflict("Reactivate the account first.")
    mail = issue_invite(db, user, admin.name) if status == "Invited" else issue_reset_link(db, user)
    summary = f"Re-sent the invite to {user.name}" if status == "Invited" else f"Sent a password reset to {user.name}"
    audit.record(db, admin, "user.reset", summary, ("user", user.user_id), ip=ip)
    db.commit()
    mailer.send_all([mail])
