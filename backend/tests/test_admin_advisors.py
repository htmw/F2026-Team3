"""Admin advisors service (spec 32). Every test that changes data builds throwaway advisors and students with
caseload(), so the seeded caseloads that the overview and users tests read stay as seeded."""
import uuid
from datetime import timedelta

import pytest

from core.errors import ApiError
from core.time import now
from database import SessionLocal
from models import (Advisor, AdvisorStudentAssignment, ApprovalRequest, AuditEvent, AuthToken, Conversation,
                    ConversationParticipant, Meeting, Message, Student, User)
from services import admin_advisors as aa
from services import mailer


def caseload(make_user, capacity: int = 40, n: int = 0, names: list[str] | None = None, active: bool = True):
    """A throwaway advisor with n advisees: (advisor_id, advisor user id, [student ids])."""
    advisor_user = make_user("advisor")
    students = [make_user("student") for _ in range(len(names) if names else n)]
    with SessionLocal() as db:
        if not active:
            db.get(User, advisor_user.user_id).is_active = False
        advisor = Advisor(user_id=advisor_user.user_id, capacity=capacity)
        db.add(advisor)
        db.flush()
        ids = []
        for i, user in enumerate(students):
            name = names[i] if names else user.name
            db.get(User, user.user_id).name = name
            student = Student(user_id=user.user_id, name=name, email=user.email, program_id=1)
            db.add(student)
            db.flush()
            db.add(AdvisorStudentAssignment(student_id=student.student_id, advisor_id=advisor.advisor_id))
            ids.append(student.student_id)
        db.commit()
        return advisor.advisor_id, advisor_user.user_id, ids


def notices(user_id: int) -> list[str]:
    """Texts of the user's Acadmate notices, oldest first."""
    with SessionLocal() as db:
        return [text for text, in db.query(Message.text)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
                .filter(Conversation.kind == "system", ConversationParticipant.user_id == user_id)
                .order_by(Message.id)]


def user_of(student_id: int) -> int:
    with SessionLocal() as db:
        return db.get(Student, student_id).user_id


def advisor_of(student_id: int) -> int:
    with SessionLocal() as db:
        return db.get(AdvisorStudentAssignment, student_id).advisor_id


@pytest.fixture
def sent(monkeypatch):
    mails = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: mails.append((to, subject, text)))
    return mails


@pytest.fixture
def admin(db):
    return db.get(User, 3)  # Jordan Lee


@pytest.fixture
def invites_used():
    """Marks the invites of advisors added in a test as used, so the overview's "1 invited" note stays as seeded."""
    emails = []
    yield emails
    with SessionLocal() as db:
        users = db.query(User.user_id).filter(User.email.in_(emails))
        db.query(AuthToken).filter(AuthToken.user_id.in_(users), AuthToken.used_at.is_(None)) \
            .update({AuthToken.used_at: now()}, synchronize_session=False)
        db.commit()


def fresh_email() -> str:
    return f"advisor.{uuid.uuid4().hex[:8]}@pac.edu"


# --- rows ----------------------------------------------------------------------------------------------------------

def test_status_and_days():
    assert aa.status_for(40, 45) == "Has room"
    assert aa.status_for(41, 45) == "Near capacity" and aa.status_for(45, 45) == "Near capacity"
    assert aa.status_for(46, 45) == "Over capacity"
    assert aa.status_for(0, 1) == "Has room"
    assert aa._fmt_days(None) == "—" and aa._fmt_days(1.46) == "1.5 days"


def test_seeded_list(db):
    rows = aa.list_advisors(db)
    by_id = {row["id"]: row for row in rows}
    kim = by_id[203]
    assert (kim["load"], kim["cap"], kim["pending"], kim["status"], kim["dept"]) == (3, 2, 2, "Over capacity",
                                                                                   "Computer Science")
    assert (by_id[201]["resp"], by_id[201]["cap"], by_id[201]["userId"]) == ("1.5 days", 45, 2)
    assert by_id[202]["active"] is False and by_id[202]["dept"] == "Data Science"
    actives = [row["active"] for row in rows]
    assert actives == sorted(actives, reverse=True)  # every active advisor before the invited one
    assert set(kim) == {"id", "userId", "name", "dept", "load", "cap", "pending", "resp", "status", "active"}
    with pytest.raises(ApiError) as err:
        aa.get_row(db, 999999)
    assert err.value.status == 404


# --- add and update ------------------------------------------------------------------------------------------------

def test_add_invites_an_advisor(db, admin, sent, invites_used):
    email = fresh_email()
    invites_used.append(email)
    row = aa.add(db, admin, {"name": "Dr. Ada  Quinn", "email": email.upper(), "department": "Mathematics",
                             "capacity": 30})
    assert (row["name"], row["dept"], row["cap"], row["load"], row["active"]) == ("Dr. Ada Quinn", "Mathematics",
                                                                                   30, 0, False)
    user = db.get(User, row["userId"])
    assert (user.email, user.role, user.is_active, user.password_hash) == (email, "advisor", False, None)
    assert sent[-1][0] == email and "token=" in sent[-1][2]
    event = db.query(AuditEvent).filter(AuditEvent.action == "advisor.add").order_by(AuditEvent.id.desc()).first()
    assert event.target_id == str(row["id"]) and event.changes["capacity"] == 30

    with pytest.raises(ApiError) as err:
        aa.add(db, admin, {"name": "Someone Else", "email": email, "department": "Mathematics", "capacity": 40})
    assert (err.value.status, err.value.message) == (409, "An account with this email already exists.")


def test_update(db, admin, make_user):
    advisor_id, advisor_user_id, _ = caseload(make_user, capacity=10)
    row = aa.update(db, admin, advisor_id, {"capacity": 12, "department": "Physics", "title": "Lead advisor"})
    assert (row["cap"], row["dept"]) == (12, "Physics")
    event = db.query(AuditEvent).filter(AuditEvent.action == "advisor.update").order_by(AuditEvent.id.desc()).first()
    assert event.changes == {"capacity": [10, 12], "department": [None, "Physics"], "title": [None, "Lead advisor"]}

    row = aa.update(db, admin, advisor_id, {"department": "  "})
    db.expire_all()
    assert row["dept"] == "Lead advisor" and db.get(Advisor, advisor_id).department is None  # falls back to title
    for patch, status in (({"capacity": 0}, 400), ({"capacity": 201}, 400)):
        with pytest.raises(ApiError) as err:
            aa.update(db, admin, advisor_id, patch)
        assert err.value.status == status
    with pytest.raises(ApiError) as err:
        aa.update(db, admin, 999999, {"capacity": 5})
    assert err.value.status == 404


# --- reassignment --------------------------------------------------------------------------------------------------

def test_pick_students_keeps_in_flight_work(db, make_user):
    advisor_id, advisor_user_id, (a, b, c) = caseload(make_user, names=["Ann Able", "Ben Baker", "Cal Cole"])
    starts = now() + timedelta(days=1)
    with SessionLocal() as session:
        session.add(ApprovalRequest(student_id=a, advisor_id=advisor_id, type="plan", title="Pending plan"))
        session.add(Meeting(student_id=b, advisor_id=advisor_id, staff_user_id=advisor_user_id, starts_at=starts,
                            ends_at=starts + timedelta(minutes=30), format="online", topic="Check-in",
                            status="confirmed"))
        session.commit()
    advisor = db.get(Advisor, advisor_id)
    assert [s.student_id for s in aa.pick_students(db, advisor, 3)] == [c, b, a]
    assert [s.student_id for s in aa.pick_students(db, advisor, 1)] == [c]


def test_reassign_by_count(db, admin, make_user, sent):
    source, source_user, students = caseload(make_user, capacity=6, n=6)
    target, target_user, _ = caseload(make_user, capacity=10)
    with SessionLocal() as session:
        session.add_all([ApprovalRequest(student_id=s, advisor_id=source, type="plan", title="Pending plan")
                         for s in students])
        done = ApprovalRequest(student_id=students[0], advisor_id=source, type="form", title="Done form",
                               status="approved", decided_at=now())
        session.add(done)
        session.commit()
        done_id = done.id
    target_name = db.get(User, target_user).name
    source_name = db.get(User, source_user).name

    result = aa.reassign(db, admin, source, target, count=5)
    assert result["moved"] == 5
    assert (result["from"]["load"], result["to"]["load"], result["to"]["pending"]) == (1, 5, 5)
    assert result["message"] == f"Moved 5 advisees to {target_name}. Students get an email."

    moved = [s for s in students if advisor_of(s) == target]
    assert len(moved) == 5
    with SessionLocal() as session:
        assert session.get(ApprovalRequest, done_id).advisor_id == source  # decided requests stay
        assert session.get(AdvisorStudentAssignment, moved[0]).updated_at is not None
        pending = {r.student_id: r.advisor_id for r in session.query(ApprovalRequest)
                   .filter(ApprovalRequest.student_id.in_(students), ApprovalRequest.status == "pending")}
    assert all(pending[s] == (target if s in moved else source) for s in students)

    assert notices(user_of(moved[0]))[-1] == f"Your advisor is now {target_name}."
    assert notices(source_user)[-1] == f"5 of your advisees moved to {target_name}."
    assert notices(target_user)[-1].startswith(f"5 advisees moved to you from {source_name}: Test User")
    assert len(sent) == 5 and all(subject == "Your advisor has changed" for _, subject, _ in sent)
    event = db.query(AuditEvent).filter(AuditEvent.action == "advisor.reassign").order_by(AuditEvent.id.desc()).first()
    assert event.target_id == str(source) and event.changes["to"] == target
    assert sorted(event.changes["studentIds"]) == moved


def test_reassign_by_ids_keeps_meetings(db, admin, make_user, sent):
    source, source_user, (first, second) = caseload(make_user, n=2)
    target, target_user, _ = caseload(make_user)
    starts = now() + timedelta(days=3)
    with SessionLocal() as session:
        session.add(Meeting(student_id=first, advisor_id=source, staff_user_id=source_user, starts_at=starts,
                            ends_at=starts + timedelta(minutes=30), format="online", topic="Check-in",
                            status="confirmed"))
        session.commit()
    target_name = db.get(User, target_user).name

    result = aa.reassign(db, admin, source, target, student_ids=[first, first])
    assert result["moved"] == 1 and result["message"].endswith("The student gets an email.")
    assert (advisor_of(first), advisor_of(second)) == (target, source)
    assert notices(source_user)[-1] == (f"1 of your advisees moved to {target_name}. "
                                        "Upcoming meetings stay on your calendar.")
    with SessionLocal() as session:  # the meeting itself stays with the old advisor
        assert session.query(Meeting).filter(Meeting.student_id == first).one().staff_user_id == source_user
    assert len(sent) == 1


def test_reassign_errors(db, admin, make_user):
    source, source_user, students = caseload(make_user, n=2)
    empty, _, _ = caseload(make_user)
    inactive, _, _ = caseload(make_user, active=False)
    small, _, _ = caseload(make_user, capacity=5, n=5)
    source_name = db.get(User, source_user).name
    cases = [
        (dict(from_id=source, to_id=source, count=1), 400, "Choose a different advisor."),
        (dict(from_id=source, to_id=inactive, count=1), 400, "Choose an active advisor."),
        (dict(from_id=source, to_id=empty, count=0), 400, "Choose between 1 and 2 advisees."),
        (dict(from_id=source, to_id=empty, count=3), 400, "Choose between 1 and 2 advisees."),
        (dict(from_id=source, to_id=empty, student_ids=[101]), 400, f"Those students aren't advised by {source_name}."),
        (dict(from_id=empty, to_id=source, count=1), 400, f"{db.get(User, db.get(Advisor, empty).user_id).name} "
                                                           "has no advisees to move."),
        (dict(from_id=999999, to_id=source, count=1), 404, "Advisor not found."),
    ]
    for kwargs, status, message in cases:
        with pytest.raises(ApiError) as err:
            aa.reassign(db, admin, **kwargs)
        assert (err.value.status, err.value.message) == (status, message), kwargs
    small_name = db.get(User, db.get(Advisor, small).user_id).name
    with pytest.raises(ApiError) as err:  # 5 of 5, limit 6: room for one more
        aa.reassign(db, admin, source, small, count=2)
    assert (err.value.status, err.value.message) == (409, f"{small_name} can take at most 1 more advisee "
                                                          "(capacity 5 + 20%).")
    assert [advisor_of(s) for s in students] == [source, source]  # nothing moved
    assert aa.reassign(db, admin, source, small, count=1)["to"]["load"] == 6  # exactly at the limit is fine
