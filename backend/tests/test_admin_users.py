"""Admin users (spec 31). conftest pins today to 2026-10-01. Tests make their own users (an auth test activates
Priya's seeded invite, so she isn't reliably "Invited") and use fresh email addresses each run."""
import re
import uuid
from datetime import datetime, time, timedelta

import pytest

from core.errors import ApiError
from core.security import sha256_hex
from core.time import local_zone, today
from database import SessionLocal
from models import (Advisor, AdvisorStudentAssignment, AuditEvent, AuthToken, ConversationParticipant, Message,
                    Student, User, UserSession)
from services import admin_users as au
from services import mailer

ADMIN_ID = 3


def fresh(prefix: str = "new") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@pac.edu"


@pytest.fixture
def sent(monkeypatch):
    """Captures mail instead of logging it."""
    mails = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: mails.append((to, subject, text)))
    return mails


@pytest.fixture
def student_user(make_user):
    """A throwaway active student with a students row (no enrollments, no advisor)."""
    def create() -> User:
        user = make_user("student")
        with SessionLocal() as db:
            db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
            db.commit()
        return user
    return create


def token_from(text: str) -> str:
    return re.search(r"token=([\w-]+)", text).group(1)


# --- labels -------------------------------------------------------------------------------------------------------

def test_labels():
    assert au._last_active(None) == "Never"
    at = lambda day: datetime.combine(day, time(12), local_zone())  # noqa: E731
    assert au._last_active(at(today())) == "Today"
    assert au._last_active(at(today() - timedelta(days=1))) == "Yesterday"
    assert au._last_active(at(today() - timedelta(days=12))) == "Sep 19"
    assert au._last_active(at(today() - timedelta(days=60))) == "Aug 2026"
    assert [au.normalize_role(r) for r in (None, "ALL", "Student", "students", "admin")] == \
        ["all", "all", "student", "student", "admin"]
    with pytest.raises(ApiError):
        au.normalize_role("teacher")


def test_status_of():
    assert au.status_of(User(is_active=True, password_hash="x")) == "Active"
    assert au.status_of(User(is_active=False, password_hash=None)) == "Invited"
    assert au.status_of(User(is_active=False, password_hash="x")) == "Deactivated"


# --- list ---------------------------------------------------------------------------------------------------------

def test_list_users(db):
    data = au.list_users(db)
    by_role = {role: db.query(User).filter(User.role == role).count() for role in au.ROLES}
    assert data["counts"] == {"All": sum(by_role.values()), "Students": by_role["student"],
                              "Advisors": by_role["advisor"], "Admins": by_role["admin"]}
    assert data["total"] == data["counts"]["All"] and data["page"] == 1 and data["pageSize"] == 50
    names = [r["name"] for r in data["rows"]]
    assert names == sorted(names, key=str.lower)

    amara = next(r for r in data["rows"] if r["id"] == 1)
    assert {k: amara[k] for k in ("role", "dept", "status", "studentId", "advisorId", "advisorName", "programId")} == {
        "role": "Student", "dept": "M.S. Computer Science", "status": "Active", "studentId": 101, "advisorId": 201,
        "advisorName": "Dr. Sarah Smith", "programId": 1}
    kim = next(r for r in data["rows"] if r["id"] == 9)
    assert (kim["role"], kim["dept"], kim["studentId"]) == ("Advisor", "Computer Science", None)  # department
    sam = next(r for r in data["rows"] if r["id"] == 4)
    assert sam["status"] == "Deactivated"

    assert {a["id"] for a in data["advisors"]} >= {201, 203, 204}
    assert next(a for a in data["advisors"] if a["id"] == 203)["advisees"] == 3
    assert data["programs"] == [{"id": 1, "name": "M.S. Computer Science"}]


def test_list_filters(db):
    smith = au.list_users(db, q="smi")
    assert [r["name"] for r in smith["rows"]] == ["Dr. Sarah Smith"]
    assert smith["counts"] == {"All": 1, "Students": 0, "Advisors": 1, "Admins": 0}  # tabs follow the search
    assert au.list_users(db, q="okafor@PAC")["rows"][0]["id"] == 1  # email, case-insensitive
    assert au.list_users(db, q="100%")["total"] == 0  # % is literal
    students = au.list_users(db, role="Students")
    assert {r["role"] for r in students["rows"]} == {"Student"} and students["total"] == students["counts"]["Students"]
    deactivated = au.list_users(db, status="Deactivated")
    assert 4 in [r["id"] for r in deactivated["rows"]] and {r["status"] for r in deactivated["rows"]} == {"Deactivated"}
    page = au.list_users(db, page=2, size=3)
    assert len(page["rows"]) == 3 and page["rows"][0]["id"] not in [r["id"] for r in au.list_users(db, size=3)["rows"]]


# --- invite -------------------------------------------------------------------------------------------------------

def test_invite(db, sent):
    admin = db.get(User, ADMIN_ID)
    new = fresh("Maria.Lopez")
    result = au.invite(db, admin, [new, "amara.okafor@pac.edu", "not-an-email", new.upper()], "student")
    assert result == {"sent": 1, "skipped": [
        {"email": "amara.okafor@pac.edu", "reason": "already has an account"},
        {"email": "not-an-email", "reason": "not a valid email"},
        {"email": new.lower(), "reason": "listed twice"}]}

    user = db.query(User).filter(User.email == new.lower()).one()
    assert user.name.startswith("Maria Lopez ")  # name_from_email; the random suffix is the last word
    assert (user.role, au.status_of(user)) == ("student", "Invited")
    assert db.query(Student).filter(Student.user_id == user.user_id).one().program_id == 1
    assert len(sent) == 1 and sent[0][0] == user.email and "Jordan Lee invited you" in sent[0][2]
    token = db.query(AuthToken).filter(AuthToken.token_hash == sha256_hex(token_from(sent[0][2]))).one()
    assert token.purpose == "invite" and token.user_id == user.user_id
    event = db.query(AuditEvent).filter(AuditEvent.action == "user.invite").order_by(AuditEvent.id.desc()).first()
    assert event.summary == "Invited 1 student" and event.changes["emails"] == [user.email]


def test_invite_advisor_gets_advisor_row(db, sent):
    email = fresh("adv")
    assert au.invite(db, db.get(User, ADMIN_ID), [email], "advisor")["sent"] == 1
    user = db.query(User).filter(User.email == email).one()
    assert db.query(Advisor).filter(Advisor.user_id == user.user_id).one().capacity == 40


# --- import -------------------------------------------------------------------------------------------------------

def test_import_csv(db, sent, student_user):
    existing = student_user()
    new_student, new_advisor = fresh("csv"), fresh("csvadv")
    text = ("﻿Name, Email ,Role,Program\n"
            f"Nadia Haddad,{new_student},student,M.S. Computer Science\n"
            f"Renamed Person,{existing.email},Student,m.s. computer science\n"
            f"Bad Program,{fresh('bad')},student,MS Bio\n"
            "\n"
            f"Omar Farouk,{new_advisor},advisor,Mathematics\n"
            "No Email,,student,M.S. Computer Science\n"
            f"Amara Okafor,amara.okafor@pac.edu,advisor,\n"
            f"Dup,{new_student},student,M.S. Computer Science\n")
    result = au.import_csv(db, db.get(User, ADMIN_ID), text)
    assert (result["created"], result["updated"], result["file"]) == (2, 1, None)
    assert result["skipped"] == [
        {"line": 4, "reason": 'Unknown program "MS Bio"'},
        {"line": 7, "reason": 'Not a valid email ""'},
        {"line": 8, "reason": "Students with course records can't change role."},
        {"line": 9, "reason": f"{new_student} is listed earlier in the file"},
    ]

    renamed = db.get(User, existing.user_id)
    db.refresh(renamed)
    assert renamed.name == "Renamed Person" and renamed.last_name == "Person"
    assert db.query(Student).filter(Student.user_id == existing.user_id).one().name == "Renamed Person"
    advisor = db.query(User).filter(User.email == new_advisor).one()
    assert (advisor.role, au.status_of(advisor)) == ("advisor", "Invited")
    assert db.query(Advisor).filter(Advisor.user_id == advisor.user_id).one().department == "Mathematics"
    assert sorted(m[0] for m in sent) == sorted([new_student, new_advisor])  # invites only for new users
    assert db.get(User, 1).role == "student"


@pytest.mark.parametrize("text, message", [
    ("", "The first line must be the header: name,email,role,program."),
    ("email,name,role,program\nx,y,student,z\n", "The first line must be the header: name,email,role,program."),
    ("name,email,role,program\n\n", "The file has no users."),
])
def test_import_rejects_bad_files(db, text, message):
    with pytest.raises(ApiError) as err:
        au.import_csv(db, db.get(User, ADMIN_ID), text)
    assert (err.value.status, err.value.message) == (400, message)


def test_import_row_limit(db, monkeypatch):
    monkeypatch.setattr(au, "MAX_IMPORT_ROWS", 2)
    text = "name,email,role,program\n" + "".join(f"U{i},u{i}@pac.edu,admin,\n" for i in range(3))
    with pytest.raises(ApiError) as err:
        au.import_csv(db, db.get(User, ADMIN_ID), text)
    assert err.value.message == "Import at most 2 users at a time."


# --- update -------------------------------------------------------------------------------------------------------

def test_update_advisor_and_program(db, student_user):
    user = student_user()
    admin = db.get(User, ADMIN_ID)
    row = au.update(db, admin, user.user_id, {"advisorId": 204})
    assert (row["advisorId"], row["advisorName"]) == (204, "Maya Brooks")
    student = db.query(Student).filter(Student.user_id == user.user_id).one()
    assert db.get(AdvisorStudentAssignment, student.student_id).advisor_id == 204
    notice = (db.query(Message.text).join(ConversationParticipant,
                                          ConversationParticipant.conversation_id == Message.conversation_id)
              .filter(ConversationParticipant.user_id == user.user_id).all())
    assert ("Your advisor is now Maya Brooks.",) in notice
    event = db.query(AuditEvent).filter(AuditEvent.action == "user.update",
                                        AuditEvent.target_id == str(user.user_id)).one()
    assert event.changes == {"advisor": [None, 204]}

    assert au.update(db, admin, user.user_id, {"advisorId": None})["advisorId"] is None
    with pytest.raises(ApiError) as err:
        au.update(db, admin, user.user_id, {"advisorId": 999})
    assert err.value.message == "Choose an active advisor."
    with pytest.raises(ApiError) as err:
        au.update(db, admin, user.user_id, {"programId": 99})
    assert err.value.message == "Unknown program."
    with pytest.raises(ApiError) as err:
        au.update(db, admin, 9, {"advisorId": 201})
    assert err.value.message == "Only students have an advisor and a program."


def test_update_role_rules(db, student_user, make_user):
    admin = db.get(User, ADMIN_ID)
    with pytest.raises(ApiError) as err:
        au.update(db, admin, 1, {"role": "advisor"})  # Amara has enrollments
    assert (err.value.status, err.value.message) == (409, "Students with course records can't change role.")
    with pytest.raises(ApiError) as err:
        au.update(db, admin, 2, {"role": "admin"})  # Dr. Smith advises Amara
    assert err.value.message == "Move their advisees first."
    db.rollback()

    user = student_user()
    au.update(db, admin, user.user_id, {"advisorId": 201})
    row = au.update(db, admin, user.user_id, {"role": "advisor"})
    assert (row["role"], row["studentId"], row["advisorId"]) == ("Advisor", None, None)
    student = db.query(Student).filter(Student.user_id == user.user_id).one()
    assert db.get(AdvisorStudentAssignment, student.student_id) is None  # assignment removed
    assert db.query(Advisor).filter(Advisor.user_id == user.user_id).one() is not None
    assert au.update(db, admin, user.user_id, {"role": "student"})["studentId"] == student.student_id  # row kept


def test_update_status(db, make_user):
    admin = db.get(User, ADMIN_ID)
    user = make_user("student")
    db.add(UserSession(user_id=user.user_id, token_hash=sha256_hex(uuid.uuid4().hex),
                       expires_at=datetime.now(local_zone()) + timedelta(days=1)))
    db.commit()
    assert au.update(db, admin, user.user_id, {"status": "Deactivated"})["status"] == "Deactivated"
    assert db.query(UserSession).filter(UserSession.user_id == user.user_id,
                                        UserSession.revoked_at.is_(None)).count() == 0
    assert au.update(db, admin, user.user_id, {"status": "Active"})["status"] == "Active"

    for patch in ({"status": "Deactivated"}, {"role": "student"}):
        with pytest.raises(ApiError) as err:
            au.update(db, admin, ADMIN_ID, patch)
        assert (err.value.status, err.value.message) == (409, au.SELF_CHANGE)

    invited = User(name="Inv Ited", first_name="Inv", last_name="Ited", email=fresh("inv"), role="admin",
                   is_active=False, password_hash=None)
    db.add(invited)
    db.commit()
    with pytest.raises(ApiError) as err:
        au.update(db, admin, invited.user_id, {"status": "Active"})
    assert err.value.status == 409 and "Re-send the invite" in err.value.message
    with pytest.raises(ApiError) as err:
        au.update(db, admin, 999999, {"status": "Active"})
    assert err.value.status == 404


# --- reset --------------------------------------------------------------------------------------------------------

def test_send_reset(db, sent, make_user):
    admin = db.get(User, ADMIN_ID)
    active = make_user("student")
    au.send_reset(db, admin, active.user_id)
    assert sent[-1][1] == "Reset your Acadmate password"
    assert db.query(AuthToken).filter(AuthToken.token_hash == sha256_hex(token_from(sent[-1][2]))).one().purpose == "reset"

    email = fresh("again")
    au.invite(db, admin, [email], "admin")
    first = token_from(sent[-1][2])
    invited = db.query(User).filter(User.email == email).one()
    au.send_reset(db, admin, invited.user_id)
    assert sent[-1][1] == "You're invited to Acadmate"
    assert db.query(AuthToken).filter(AuthToken.token_hash == sha256_hex(first)).one().used_at is not None

    with pytest.raises(ApiError) as err:
        au.send_reset(db, admin, 4)  # Sam Rivera, deactivated
    assert (err.value.status, err.value.message) == (409, "Reactivate the account first.")
    with pytest.raises(ApiError) as err:
        au.send_reset(db, admin, 999999)
    assert err.value.status == 404
