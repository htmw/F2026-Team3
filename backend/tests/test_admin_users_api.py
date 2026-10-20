"""Admin users over HTTP (spec 31): /api/v1/admin/users*. Service rules are covered in test_admin_users.py.
conftest pins today to 2026-10-01."""
import re
import uuid

import pytest

from conftest import login
from database import SessionLocal
from models import AuditEvent, Student, User
from services import admin_users, mailer
from test_foundation import assert_envelope

USERS = "/api/v1/admin/users"
JORDAN = "jordan.lee@pac.edu"
CSV = {"Content-Type": "text/csv"}


def fresh(prefix: str = "api") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@pac.edu"


@pytest.fixture
def admin(client):
    assert login(client, JORDAN).status_code == 200
    return client


def calls(client):
    """One request per route (bodies valid enough to reach the role check)."""
    return [
        client.get(USERS),
        client.post(f"{USERS}/invite", json={"emails": [fresh()], "role": "student"}),
        client.post(f"{USERS}/import", content=b"name,email,role,program\n", headers=CSV),
        client.patch(f"{USERS}/1", json={}),
        client.post(f"{USERS}/1/reset"),
    ]


def test_users_routes_need_an_admin(client, as_user):
    for response in calls(client):
        assert_envelope(response, 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for response in calls(client):
            assert_envelope(response, 403, "FORBIDDEN")


def test_list_route(admin):
    body = admin.get(USERS, params={"role": "student", "pageSize": 200}).json()  # the AI settings test box call
    assert {"rows", "total", "page", "pageSize", "counts", "advisors", "programs"} <= set(body)
    assert body["pageSize"] == 200 and set(body["counts"]) == {"All", "Students", "Advisors", "Admins"}
    assert {r["role"] for r in body["rows"]} == {"Student"}
    amara = next(r for r in body["rows"] if r["id"] == 1)
    assert {"lastActive", "lastActiveAt", "studentId", "advisorName", "programId"} <= set(amara)
    assert amara["dept"] == "M.S. Computer Science"
    assert [r["name"] for r in admin.get(USERS, params={"q": "smi"}).json()["rows"]] == ["Dr. Sarah Smith"]
    assert {r["status"] for r in admin.get(USERS, params={"status": "Deactivated"}).json()["rows"]} == {"Deactivated"}

    assert_envelope(admin.get(USERS, params={"pageSize": 201}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.get(USERS, params={"page": 0}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.get(USERS, params={"status": "Gone"}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.get(USERS, params={"role": "teacher"}), 400, "BAD_REQUEST")


def test_invite_route(admin):
    response = admin.post(f"{USERS}/invite", json={"emails": [fresh()], "role": "advisor"})
    assert response.status_code == 200 and response.json() == {"sent": 1, "skipped": []}
    assert_envelope(admin.post(f"{USERS}/invite", json={"emails": [], "role": "student"}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{USERS}/invite", json={"emails": [fresh()], "role": "owner"}), 422, "VALIDATION_ERROR")


def test_import_route(admin):
    text = f"name,email,role,program\nNew Person,{fresh('csv')},student,M.S. Computer Science\n"
    response = admin.post(f"{USERS}/import", content=text.encode(), headers=CSV)
    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 0, "skipped": [], "file": None}

    too_big = b"name,email,role,program\n" + b"x" * (1024 * 1024)
    error = assert_envelope(admin.post(f"{USERS}/import", content=too_big, headers=CSV), 400, "BAD_REQUEST")
    assert error["message"] == "The file is larger than 1 MB."
    error = assert_envelope(admin.post(f"{USERS}/import", content="name,email\n".encode("utf-16"), headers=CSV),
                            400, "BAD_REQUEST")
    assert error["message"] == "Save the file as a UTF-8 CSV."
    error = assert_envelope(admin.post(f"{USERS}/import", content=b"email,name\n", headers=CSV), 400, "BAD_REQUEST")
    assert error["message"].startswith("The first line must be the header")


def test_patch_route(admin, make_user, db):
    user = make_user("student")
    db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
    db.commit()

    row = admin.patch(f"{USERS}/{user.user_id}", json={"advisorId": 204}).json()
    assert (row["advisorId"], row["advisorName"], row["role"]) == (204, "Maya Brooks", "Student")
    assert admin.patch(f"{USERS}/{user.user_id}", json={"advisorId": None}).json()["advisorId"] is None
    assert admin.patch(f"{USERS}/{user.user_id}", json={}).json()["id"] == user.user_id

    assert_envelope(admin.patch(f"{USERS}/{user.user_id}", json={"role": None}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.patch(f"{USERS}/{user.user_id}", json={"status": "Invited"}), 422, "VALIDATION_ERROR")
    error = assert_envelope(admin.patch(f"{USERS}/3", json={"status": "Deactivated"}), 409, "CONFLICT")
    assert error["message"] == "You can't change your own account here."
    assert_envelope(admin.patch(f"{USERS}/999999", json={}), 404, "NOT_FOUND")


def test_reset_route(admin, make_user):
    user = make_user("student")
    response = admin.post(f"{USERS}/{user.user_id}/reset")
    assert response.status_code == 202 and response.json() == {"ok": True}
    assert_envelope(admin.post(f"{USERS}/999999/reset"), 404, "NOT_FOUND")
    assert_envelope(admin.post(f"{USERS}/4/reset"), 409, "CONFLICT")  # Sam Rivera is deactivated


# --- end-to-end flows (spec 31 acceptance) ----------------------------------------------------------------------------

@pytest.fixture
def mail(monkeypatch):
    """Captured emails as (to, subject, text)."""
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def token_of(message) -> str:
    return re.search(r"token=([\w-]+)", message[2]).group(1)


def row_for(client, email: str) -> dict:
    rows = client.get(USERS, params={"q": email}).json()["rows"]
    assert len(rows) == 1, rows
    return rows[0]


@pytest.fixture
def student_with_row(make_user, db):
    def create() -> User:
        user = make_user("student")
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
        return user
    return create


@pytest.fixture(scope="module")
def page_users():
    """200 throwaway students named "Page Test 000" … "Page Test 199"."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as session:
        users = [User(name=f"Page Test {i:03}", first_name="Page", last_name=f"Test{i:03}",
                      email=f"page.{tag}.{i}@pac.edu", password_hash="x", role="student") for i in range(200)]
        session.add_all(users)
        session.commit()
        ids = [u.user_id for u in users]
    yield ids
    with SessionLocal() as session:
        session.query(User).filter(User.user_id.in_(ids)).delete(synchronize_session=False)
        session.commit()


def test_paging_through_200_users(admin, page_users):
    seen, names = [], []
    for page in range(1, 6):
        body = admin.get(USERS, params={"q": "Page Test", "pageSize": 50, "page": page}).json()
        assert body["total"] == 200 and body["counts"]["Students"] == 200 and body["page"] == page
        assert len(body["rows"]) == (50 if page <= 4 else 0)
        seen += [r["id"] for r in body["rows"]]
        names += [r["name"] for r in body["rows"]]
    assert sorted(seen) == sorted(page_users) and len(set(seen)) == 200
    assert names == [f"Page Test {i:03}" for i in range(200)]

    admins = admin.get(USERS, params={"q": "Page Test", "role": "admin"}).json()
    assert admins["total"] == 0 and admins["rows"] == [] and admins["counts"]["Students"] == 200


def test_invite_through_to_sign_in(admin, client, mail):
    email = fresh("invitee")
    assert admin.post(f"{USERS}/invite", json={"emails": [email], "role": "advisor"}).json() == {"sent": 1, "skipped": []}
    token = token_of(mail[-1])
    row = row_for(admin, email)
    assert (row["status"], row["lastActive"], row["role"]) == ("Invited", "Never", "Advisor")

    link = admin.get(f"/api/v1/auth/password-reset/{token}")
    assert link.json() == {"email": email, "purpose": "invite"}  # the page shows "Set up your account"
    assert admin.post("/api/v1/auth/password-reset/confirm",
                      json={"token": token, "password": "advisor-pass-1"}).status_code == 204

    newcomer = client.__class__(client.app)
    response = login(newcomer, email, "advisor-pass-1")
    assert response.status_code == 200 and response.json()["home"] == "/advisor"
    row = row_for(admin, email)
    assert (row["status"], row["lastActive"]) == ("Active", "Today")

    again = admin.post(f"{USERS}/invite", json={"emails": [email], "role": "advisor"}).json()
    assert again == {"sent": 0, "skipped": [{"email": email, "reason": "already has an account"}]}


def test_resent_invite_replaces_the_old_link(admin, mail):
    email = fresh("resend")
    admin.post(f"{USERS}/invite", json={"emails": [email], "role": "student"})
    first = token_of(mail[-1])
    user_id = row_for(admin, email)["id"]
    assert admin.post(f"{USERS}/{user_id}/reset").status_code == 202
    second = token_of(mail[-1])
    assert mail[-1][1] == "You're invited to Acadmate" and second != first
    assert_envelope(admin.get(f"/api/v1/auth/password-reset/{first}"), 410, "LINK_EXPIRED")
    assert admin.get(f"/api/v1/auth/password-reset/{second}").json()["purpose"] == "invite"


def test_deactivation_signs_the_person_out(admin, client, make_user):
    user = make_user("student")
    browser = client.__class__(client.app)
    assert login(browser, user.email).status_code == 200
    assert browser.get("/api/v1/auth/me").status_code == 200

    assert admin.patch(f"{USERS}/{user.user_id}", json={"status": "Deactivated"}).json()["status"] == "Deactivated"
    assert_envelope(browser.get("/api/v1/auth/me"), 401, "UNAUTHENTICATED")
    assert_envelope(login(browser, user.email), 403, "DEACTIVATED")

    assert admin.patch(f"{USERS}/{user.user_id}", json={"status": "Active"}).json()["status"] == "Active"
    assert login(browser, user.email).status_code == 200


def test_admin_cannot_change_own_role(admin):
    error = assert_envelope(admin.patch(f"{USERS}/3", json={"role": "student"}), 409, "CONFLICT")
    assert error["message"] == "You can't change your own account here."
    me = row_for(admin, JORDAN)
    assert (me["role"], me["status"]) == ("Admin", "Active")


def test_import_with_a_bad_program(admin, db, mail, monkeypatch):
    student, advisor = fresh("imp"), fresh("impadv")
    text = (f"name,email,role,program\n"
            f"Lina Park,{student},student,M.S. Computer Science\n"
            f"Tom Reyes,{advisor},advisor,Data Science\n"
            f"Bad Program,{fresh('impbad')},student,MS Bio\n")
    body = admin.post(f"{USERS}/import", content=text.encode(), headers=CSV).json()
    assert (body["created"], body["updated"]) == (2, 0)
    assert body["skipped"] == [{"line": 4, "reason": 'Unknown program "MS Bio"'}]
    assert (row_for(admin, student)["status"], row_for(admin, student)["dept"]) == ("Invited", "M.S. Computer Science")
    assert (row_for(admin, advisor)["role"], row_for(admin, advisor)["dept"]) == ("Advisor", "Data Science")
    assert sorted(m[0] for m in mail) == sorted([student, advisor])
    event = db.query(AuditEvent).filter(AuditEvent.action == "user.import").order_by(AuditEvent.id.desc()).first()
    assert event.changes == {"created": 2, "updated": 0, "skipped": 1}

    monkeypatch.setattr(admin_users, "MAX_IMPORT_ROWS", 2)
    error = assert_envelope(admin.post(f"{USERS}/import", content=text.encode(), headers=CSV), 400, "BAD_REQUEST")
    assert error["message"] == "Import at most 2 users at a time."


def test_advisor_change_reaches_the_student(admin, client, student_with_row):
    user = student_with_row()
    before = next(a for a in admin.get(USERS).json()["advisors"] if a["id"] == 204)["advisees"]
    assert admin.patch(f"{USERS}/{user.user_id}", json={"advisorId": 204}).json()["advisorName"] == "Maya Brooks"
    after = admin.get(USERS, params={"q": user.email}).json()
    assert next(a for a in after["advisors"] if a["id"] == 204)["advisees"] == before + 1
    assert after["rows"][0]["advisorName"] == "Maya Brooks"

    student = client.__class__(client.app)
    login(student, user.email)
    system = next(c for c in student.get("/api/v1/conversations").json()["conversations"] if c["kind"] == "system")
    assert (system["unread"], system["preview"]) == (1, "Your advisor is now Maya Brooks.")


def test_reset_email_for_an_active_user(admin, db, mail, make_user):
    user = make_user("student")
    assert admin.post(f"{USERS}/{user.user_id}/reset").status_code == 202
    assert mail[-1][0] == user.email and mail[-1][1] == "Reset your Acadmate password"
    assert admin.get(f"/api/v1/auth/password-reset/{token_of(mail[-1])}").json()["purpose"] == "reset"
    event = db.query(AuditEvent).filter(AuditEvent.action == "user.reset",
                                        AuditEvent.target_id == str(user.user_id)).one()
    assert event.summary == f"Sent a password reset to {user.name}"
