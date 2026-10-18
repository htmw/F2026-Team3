"""The signed-in user's own account (spec 17, shared with advisor settings in spec 27): profile, preferences,
Google link, data export and self-service deletion."""
from datetime import date, datetime
from decimal import Decimal

from pydantic.alias_generators import to_camel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import ApiError, forbidden
from core.security import verify_password
from core.time import iso_z, now
from models import (AiMessage, AiThread, Assignment, AssignmentSubmission, CalendarFeed, Conversation, Course,
                    Enrollment, Event, Message, PlanItem, Program, Student, Term, User, UserPreference, UserSession)
from services import audit, auth, meetings, preferences
from services.ai.context import advisor_of

DELETED_NAME = "Deleted user"


def _student(db: Session, user: User) -> Student | None:
    if user.role != "student":
        return None
    return db.query(Student).filter(Student.user_id == user.user_id).one_or_none()


def preferences_out(db: Session, user: User) -> dict:
    return {**preferences.get(db, user), "graduationOptions": preferences.graduation_options(db)}


def profile(db: Session, user: User) -> dict:
    payload = auth.user_payload(user)
    out = {
        "full_name": user.name,
        "preferred_name": user.preferred_name,
        "email": user.email,
        "initials": payload["initials"],
        "role": user.role,
        "has_password": user.password_hash is not None,
    }
    student = _student(db, user)
    if student is not None:
        program = db.get(Program, student.program_id)
        advisor = advisor_of(db, student)
        out.update({
            "student_number": student.student_number,
            "program": program.program_name if program else None,
            "advisor": advisor["name"] if advisor else None,
            "expected_graduation": preferences.get(db, user)["targetGraduation"] or student.expected_graduation,
        })
    return out


def me(db: Session, user: User) -> dict:
    return {
        "profile": profile(db, user),
        "preferences": preferences_out(db, user),
        # Phase B (spec 02) stores the linked Google address; until then only whether a link exists.
        "google": {"available": auth.google_enabled(db), "connected": user.google_sub is not None, "email": None},
    }


def update_profile(db: Session, user: User, data: dict) -> User:
    """data holds only the fields the caller sent (full_name, preferred_name, email)."""
    student = _student(db, user)
    if "full_name" in data:
        name, first, last = auth.split_name(data["full_name"])
        user.name, user.first_name, user.last_name = name, first, last
        if student is not None:
            student.name = name
    if "preferred_name" in data:
        user.preferred_name = " ".join((data["preferred_name"] or "").split()) or None
    if "email" in data:
        email = auth.normalize_email(data["email"])
        taken = db.query(User).filter(func.lower(User.email) == email, User.user_id != user.user_id).first()
        if taken is not None or (student is not None and db.query(Student).filter(
                func.lower(Student.email) == email, Student.student_id != student.student_id).first() is not None):
            raise ApiError(409, "EMAIL_TAKEN", "An account with this email already exists.")
        user.email = email
        if student is not None:
            student.email = email
    db.commit()
    return user


def google_connect(db: Session, user: User) -> str:
    """The Google consent URL. Google linking is spec 02 Phase B, which isn't built: always refused for now."""
    if not auth.google_enabled(db):
        raise ApiError(400, "GOOGLE_DISABLED", "Google sign-in isn't turned on for your school.")
    raise ApiError(400, "GOOGLE_DISABLED", "Google sign-in isn't available yet.")  # Phase B builds the consent URL here


def google_disconnect(db: Session, user: User) -> None:
    if user.google_sub is None:
        return
    if user.password_hash is None:
        raise ApiError(409, "NO_PASSWORD", "Set a password first so you can still sign in.")
    user.google_sub = None
    db.commit()


# --- export -----------------------------------------------------------------------------------------------------

def _plain(value):
    """JSON-friendly values: ISO dates, numbers for Decimals."""
    if isinstance(value, datetime):
        return iso_z(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row(**fields) -> dict:
    return {key: _plain(value) for key, value in fields.items()}


def export(db: Session, user: User) -> dict:
    """Everything Acadmate holds about the user, as one JSON document. Conversations include only their own messages."""
    student = _student(db, user)
    data = {
        "exportedAt": iso_z(now()),
        "profile": {to_camel(key): value for key, value in profile(db, user).items()},
        "preferences": preferences.get(db, user),
        "enrollments": [], "plan": [], "assignments": [], "events": [],
        "meetings": [],
        "conversations": [], "aiThreads": [],
    }
    if student is not None:
        data["meetings"] = meetings.export_rows(db, student)
        data["enrollments"] = [
            _row(code=course.course_code, name=course.course_name, term=enrollment.term, status=enrollment.status,
                 grade=enrollment.grade, credits=course.credits)
            for enrollment, course in db.query(Enrollment, Course).join(Course, Enrollment.course_id == Course.course_id)
            .filter(Enrollment.student_id == student.student_id).order_by(Enrollment.enrollment_id)]
        data["plan"] = [
            _row(code=course.course_code, name=course.course_name, term=term.name, status=item.status, note=item.note,
                 source=item.source, createdAt=item.created_at)
            for item, course, term in db.query(PlanItem, Course, Term).join(Course, PlanItem.course_id == Course.course_id)
            .join(Term, PlanItem.term_id == Term.id).filter(PlanItem.student_id == student.student_id).order_by(PlanItem.id)]
        data["assignments"] = [
            _row(title=assignment.title, dueAt=assignment.due_at, status=submission.status, submittedAt=submission.submitted_at,
                 score=submission.score, scoreText=submission.score_text, formFields=submission.form_fields)
            for submission, assignment in db.query(AssignmentSubmission, Assignment)
            .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
            .filter(AssignmentSubmission.student_id == student.student_id).order_by(Assignment.due_at)]
        data["events"] = [
            _row(title=event.title, type=event.type, date=event.date, start=event.start_time.strftime("%H:%M"),
                 end=event.end_time.strftime("%H:%M"), location=event.location, note=event.note)
            for event in db.query(Event).filter(Event.student_id == student.student_id).order_by(Event.date, Event.start_time)]
        for thread in db.query(AiThread).filter(AiThread.student_id == student.student_id).order_by(AiThread.created_at):
            messages = db.query(AiMessage).filter(AiMessage.thread_id == thread.id).order_by(AiMessage.created_at, AiMessage.id)
            data["aiThreads"].append({"title": thread.title, "createdAt": iso_z(thread.created_at), "messages": [
                _row(role=message.role, text=message.text, createdAt=message.created_at) for message in messages]})

    conversations: dict[int, dict] = {}
    for message, conversation in (db.query(Message, Conversation).join(Conversation, Message.conversation_id == Conversation.id)
                                  .filter(Message.sender_id == user.user_id).order_by(Message.created_at, Message.id)):
        entry = conversations.setdefault(conversation.id, {"id": conversation.id, "kind": conversation.kind,
                                                           "title": conversation.title, "messages": []})
        entry["messages"].append(_row(text=message.text, sentAt=message.created_at))
    data["conversations"] = list(conversations.values())
    return data


# --- deletion ---------------------------------------------------------------------------------------------------

def delete_self(db: Session, user: User, password: str | None, ip: str | None = None) -> None:
    """Deactivates and anonymises the account. School records (enrollments, grades, plans, approvals, past meetings)
    stay; personal data (sessions, AI threads, events, calendar feed, preferences) goes, and upcoming meetings are
    cancelled. Sent messages stay as "Deleted user"."""
    if user.role == "admin":
        raise forbidden("Admins can't delete their own account.")
    if user.password_hash is not None and not (password and verify_password(password, user.password_hash)):
        raise ApiError(403, "INVALID_CREDENTIALS", "That password isn't right.")

    audit.record(db, user, "user.self_delete", f"{user.name} deleted their account", target=("user", user.user_id), ip=ip)
    student = _student(db, user)
    if student is not None:
        meetings.cancel_future_for(db, student)  # before the name is anonymised: the staff notice names the student
        db.query(AiThread).filter(AiThread.student_id == student.student_id).delete(synchronize_session=False)
        db.query(Event).filter(Event.student_id == student.student_id).delete(synchronize_session=False)
        db.query(CalendarFeed).filter(CalendarFeed.student_id == student.student_id).delete(synchronize_session=False)
        student.name = DELETED_NAME
        student.email = f"deleted-{user.user_id}@invalid"
    db.query(UserPreference).filter(UserPreference.user_id == user.user_id).delete(synchronize_session=False)
    db.query(UserSession).filter(UserSession.user_id == user.user_id).delete(synchronize_session=False)

    user.name, user.first_name, user.last_name, user.preferred_name = DELETED_NAME, "Deleted", "user", None
    user.email = f"deleted-{user.user_id}@invalid"
    user.password_hash = user.google_sub = user.totp_secret = None
    user.mfa_enabled = False
    user.is_active = False
    db.commit()
