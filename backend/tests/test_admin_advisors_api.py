"""Admin advisors over HTTP (spec 32): /api/v1/admin/advisors*. Service rules are covered in test_admin_advisors.py,
including the throwaway caseload() helper used here."""
import re
import uuid

import pytest

from conftest import login
from database import SessionLocal
from models import ApprovalRequest, User
from services import mailer
from test_admin_advisors import caseload
from test_foundation import assert_envelope

ADVISORS = "/api/v1/admin/advisors"
JORDAN = "jordan.lee@pac.edu"
ROW_KEYS = {"id", "userId", "name", "dept", "load", "cap", "pending", "resp", "status", "active"}


@pytest.fixture
def admin(client):
    assert login(client, JORDAN).status_code == 200
    return client


@pytest.fixture
def mail(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def calls(client):
    """One request per route (bodies valid enough to reach the role check)."""
    return [
        client.get(ADVISORS),
        client.post(ADVISORS, json={"name": "A B", "email": "a.b@pac.edu", "department": "X"}),
        client.patch(f"{ADVISORS}/201", json={}),
        client.post(f"{ADVISORS}/201/reassign", json={"toAdvisorId": 203, "count": 1}),
    ]


def test_advisor_routes_need_an_admin(client, as_user):
    for response in calls(client):
        assert_envelope(response, 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for response in calls(client):
            assert_envelope(response, 403, "FORBIDDEN")


def test_list_shape(admin):
    rows = admin.get(ADVISORS).json()["advisors"]
    assert all(set(row) == ROW_KEYS for row in rows)
    kim = next(row for row in rows if row["id"] == 203)
    assert (kim["load"], kim["cap"], kim["status"]) == (3, 2, "Over capacity")


def test_add_then_accept_invite(admin, client, mail):
    email = f"advisor.{uuid.uuid4().hex[:8]}@pac.edu"
    response = admin.post(ADVISORS, json={"name": "Dr. Lena Ortiz", "email": email, "department": "Statistics",
                                          "capacity": 35})
    assert response.status_code == 201
    row = response.json()
    assert (row["name"], row["dept"], row["cap"], row["active"], row["status"]) == ("Dr. Lena Ortiz", "Statistics",
                                                                                    35, False, "Has room")
    assert any(r["id"] == row["id"] and not r["active"] for r in admin.get(ADVISORS).json()["advisors"])

    token = re.search(r"token=([\w-]+)", mail[-1][2]).group(1)
    assert admin.get(f"/api/v1/auth/password-reset/{token}").json() == {"email": email, "purpose": "invite"}
    assert admin.post("/api/v1/auth/password-reset/confirm",
                      json={"token": token, "password": "advisor-pass-1"}).status_code == 204
    row = next(r for r in admin.get(ADVISORS).json()["advisors"] if r["id"] == row["id"])
    assert row["active"] is True  # accepting the invite activates the account

    assert_envelope(admin.post(ADVISORS, json={"name": "Copy", "email": email.upper(), "department": "Statistics"}),
                    409, "CONFLICT")


def test_validation(admin):
    bad_adds = [
        {"name": "A B", "email": "not-an-email", "department": "X"},
        {"name": "A B", "email": "a.b@pac.edu"},
        {"name": "", "email": "a.b@pac.edu", "department": "X"},
        {"name": "A B", "email": "a.b@pac.edu", "department": "X", "capacity": 0},
        {"name": "A B", "email": "a.b@pac.edu", "department": "X", "capacity": 201},
    ]
    for body in bad_adds:
        assert_envelope(admin.post(ADVISORS, json=body), 422, "VALIDATION_ERROR")
    for body in ({"capacity": 0}, {"capacity": None}, {"department": None}, {"title": "x" * 61}):
        assert_envelope(admin.patch(f"{ADVISORS}/201", json=body), 422, "VALIDATION_ERROR")
    assert admin.patch(f"{ADVISORS}/201", json={}).json()["cap"] == 45  # nothing sent, nothing changed
    assert_envelope(admin.patch(f"{ADVISORS}/999999", json={"capacity": 5}), 404, "NOT_FOUND")

    for body in ({"toAdvisorId": 201}, {"toAdvisorId": 201, "count": 1, "studentIds": [105]}):
        response = admin.post(f"{ADVISORS}/203/reassign", json=body)
        assert_envelope(response, 422, "VALIDATION_ERROR")
        assert response.json()["error"]["details"][0]["message"] == "Send either count or studentIds."
    for body in ({"toAdvisorId": 201, "count": 0}, {"toAdvisorId": 201, "studentIds": []}):
        assert_envelope(admin.post(f"{ADVISORS}/203/reassign", json=body), 422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{ADVISORS}/203/reassign", json={"toAdvisorId": 203, "count": 1}), 400, "BAD_REQUEST")


def test_reassign_flow(admin, client, make_user, mail):
    """Spec 32 acceptance: move 5 of A's 6 advisees to B; students see B everywhere and B gets their requests."""
    source, source_user, students = caseload(make_user, capacity=5, n=6)
    target, target_user, _ = caseload(make_user, capacity=10)
    with SessionLocal() as db:
        db.add_all([ApprovalRequest(student_id=s, advisor_id=source, type="plan", title="Spring plan")
                    for s in students])
        db.commit()
        target_name = db.get(User, target_user).name

    response = admin.post(f"{ADVISORS}/{source}/reassign", json={"toAdvisorId": target, "count": 5})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"moved", "from", "to", "message"}
    assert (body["moved"], body["from"]["load"], body["to"]["load"]) == (5, 1, 5)
    assert (body["from"]["status"], body["to"]["pending"]) == ("Has room", 5)
    assert body["message"] == f"Moved 5 advisees to {target_name}. Students get an email."
    rows = {r["id"]: r for r in admin.get(ADVISORS).json()["advisors"]}
    assert (rows[source]["load"], rows[target]["load"]) == (1, 5)

    with SessionLocal() as db:
        moved_user = next(db.get(User, uid) for uid, in db.query(User.user_id).filter(User.email == mail[0][0]))
        moved_email = moved_user.email
    student = client.__class__(client.app)
    assert login(student, moved_email).status_code == 200
    contacts = {c["id"] for c in student.get("/api/v1/conversations/contacts").json()["contacts"]}
    assert target_user in contacts and source_user not in contacts
    assert student.get("/api/v1/users/me").json()["profile"]["advisor"] == target_name

    with SessionLocal() as db:
        target_email = db.get(User, target_user).email
    advisor = client.__class__(client.app)
    assert login(advisor, target_email).status_code == 200
    assert advisor.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 5
