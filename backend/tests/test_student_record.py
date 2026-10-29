"""Advisor student record (spec 22): GET /advisor/advisees/{id}, private notes, shared AI threads and the request
changes decision (spec 23's core). Amara's Spring 2027 plan is seeded as pending request 1709."""
from datetime import timedelta

import pytest

from conftest import login
from database import SessionLocal
from models import ApprovalRequest, AuditEvent, PlanItem, UserPreference
from test_foundation import assert_envelope

RECORD = "/api/v1/advisor/advisees"
APPROVALS = "/api/v1/advisor/approvals"
AMARA, AMARA_PLAN, SMITH_NOTE = 101, 1709, 1901
NOTE_TEXT = "Strong in data science; consider recommending her for the research assistant opening."


@pytest.fixture
def restore_plan():
    """Puts request 1709 and items 9001-9002 back to pending after a test decides it."""
    yield
    with SessionLocal() as session:
        request = session.get(ApprovalRequest, AMARA_PLAN)
        payload = dict(request.payload or {})
        payload.pop("before", None)
        request.payload, request.status, request.comment = payload, "pending", None
        request.decided_at = request.decided_by = None
        for item in session.query(PlanItem).filter(PlanItem.id.in_((9001, 9002))):
            item.status = "pending_approval"
        session.commit()


def test_access(client, as_user):
    assert_envelope(client.get(f"{RECORD}/{AMARA}"), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(f"{RECORD}/{AMARA}"), 403, "FORBIDDEN")
    as_user("advisor")
    assert_envelope(client.get(f"{RECORD}/999999"), 404, "NOT_FOUND")


def test_other_advisor_is_forbidden(client):
    login(client, "daniel.kim@pac.edu")
    assert_envelope(client.get(f"{RECORD}/{AMARA}"), 403, "FORBIDDEN")
    assert_envelope(client.post(f"{RECORD}/{AMARA}/notes", json={"text": "hi"}), 403, "FORBIDDEN")
    assert_envelope(client.delete(f"/api/v1/advisor/notes/{SMITH_NOTE}"), 403, "FORBIDDEN")


def test_seeded_record(client, as_user):
    as_user("advisor")
    data = client.get(f"{RECORD}/{AMARA}").json()
    student = data["student"]
    assert (student["name"], student["firstName"], student["initials"], student["userId"]) == ("Amara O.", "Amara", "AO", 1)
    assert student["subtitle"].startswith("M.S. Computer Science · your advisee since ")

    stats = {s["label"]: s for s in data["stats"]}
    assert stats["Cumulative GPA"]["value"] == "3.73"
    assert (stats["Credits"]["value"], stats["Credits"]["tag"]) == ("21 / 36", "58%")
    assert stats["Credits"]["note"] == "9 in progress · 6 left after Fall"
    assert (stats["Expected graduation"]["tag"], stats["Expected graduation"]["note"]) == ("Pending", "If this plan is approved")

    review = data["review"]
    assert (review["requestId"], review["title"], review["status"], review["statusLabel"]) == \
        (AMARA_PLAN, "Spring 2027 plan", "pending", "Waiting for you")
    assert review["subtitle"].startswith("Built with Acadmate · shared by Amara on ")
    assert [row["code"] for row in review["plan"]] == ["CS 680", "CS 691"]
    assert any(row["fulfills"] == "Capstone" for row in review["plan"])
    assert any("pre-approval form not submitted" in check["text"] for check in review["checks"])
    assert review["studentNote"].startswith("I prefer evening classes") and review["canUndo"] is False
    assert review["registrationOpens"]
    assert data["plannedTerm"] is None

    assert data["groups"] and all({"done", "inProgress", "required"} <= set(g) for g in data["groups"])
    assert data["meetings"][0]["meta"].startswith("Today · 15:00")
    assert [n["text"] for n in data["notes"]] == [NOTE_TEXT] and data["notes"][0]["mine"] is True
    texts = [a["text"] for a in data["activity"]]
    assert "Shared the Spring 2027 plan from Acadmate." in texts
    assert any(t.startswith("Booked “") for t in texts)
    assert data["aiShared"] is False


def test_approve_and_undo(client, as_user, restore_plan):
    as_user("advisor")
    response = client.post(f"{APPROVALS}/{AMARA_PLAN}/approve", json={"comment": "Send the capstone form soon."})
    assert response.status_code == 200 and response.json()["status"] == "Approved"
    review = client.get(f"{RECORD}/{AMARA}").json()["review"]
    assert (review["statusLabel"], review["comment"], review["canUndo"]) == ("Approved", "Send the capstone form soon.", True)
    with SessionLocal() as session:
        assert {i.status for i in session.query(PlanItem).filter(PlanItem.id.in_((9001, 9002)))} == {"approved"}

    # The student sees the comment in their Acadmate notices.
    as_user("student")
    threads = client.get("/api/v1/conversations").json()["conversations"]
    system = next(c for c in threads if c["kind"] == "system")
    messages = client.get(f"/api/v1/conversations/{system['id']}/messages").json()["messages"]
    assert any("Send the capstone form soon." in m["text"] for m in messages)

    as_user("advisor")
    assert client.post(f"{APPROVALS}/{AMARA_PLAN}/reopen").json()["status"] == "Pending"
    assert client.get(f"{RECORD}/{AMARA}").json()["review"]["statusLabel"] == "Waiting for you"


def test_undo_window_closes(client, as_user, restore_plan):
    as_user("advisor")
    client.post(f"{APPROVALS}/{AMARA_PLAN}/approve")
    with SessionLocal() as session:
        request = session.get(ApprovalRequest, AMARA_PLAN)
        request.decided_at = request.decided_at - timedelta(minutes=11)
        session.commit()
    assert client.get(f"{RECORD}/{AMARA}").json()["review"]["canUndo"] is False


def test_request_changes(client, as_user, restore_plan):
    as_user("advisor")
    error = assert_envelope(client.post(f"{APPROVALS}/{AMARA_PLAN}/request-changes", json={}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "comment"
    assert_envelope(client.post(f"{APPROVALS}/{AMARA_PLAN}/request-changes", json={"comment": "  "}), 422, "VALIDATION_ERROR")

    response = client.post(f"{APPROVALS}/{AMARA_PLAN}/request-changes", json={"comment": "Swap CS 680 for CS 665."})
    assert response.json()["status"] == "Changes requested"
    review = client.get(f"{RECORD}/{AMARA}").json()["review"]
    assert (review["statusLabel"], review["comment"]) == ("Changes requested", "Swap CS 680 for CS 665.")
    with SessionLocal() as session:
        assert {i.status for i in session.query(PlanItem).filter(PlanItem.id.in_((9001, 9002)))} == {"changes_requested"}
    assert_envelope(client.post(f"{APPROVALS}/{AMARA_PLAN}/request-changes", json={"comment": "again"}), 409, "CONFLICT")

    assert client.post(f"{APPROVALS}/{AMARA_PLAN}/reopen").json()["status"] == "Pending"
    with SessionLocal() as session:
        assert {i.status for i in session.query(PlanItem).filter(PlanItem.id.in_((9001, 9002)))} == {"pending_approval"}


def test_notes(client, as_user):
    as_user("advisor")
    assert_envelope(client.post(f"{RECORD}/{AMARA}/notes", json={"text": ""}), 422, "VALIDATION_ERROR")
    assert_envelope(client.post(f"{RECORD}/{AMARA}/notes", json={"text": "x" * 1001}), 422, "VALIDATION_ERROR")
    secret = "Prefers email over messages; follow up after midterms."
    response = client.post(f"{RECORD}/{AMARA}/notes", json={"text": secret})
    assert response.status_code == 201
    note = response.json()
    assert note["mine"] is True and note["text"] == secret
    assert client.get(f"{RECORD}/{AMARA}").json()["notes"][0]["id"] == note["id"]  # newest first

    with SessionLocal() as session:
        audits = session.query(AuditEvent).filter(AuditEvent.action == "note.add").all()
        assert audits and all(secret not in (a.summary + str(a.changes or "")) for a in audits)

    assert client.delete(f"/api/v1/advisor/notes/{note['id']}").status_code == 204
    assert_envelope(client.delete(f"/api/v1/advisor/notes/{note['id']}"), 404, "NOT_FOUND")
    assert note["id"] not in {n["id"] for n in client.get(f"{RECORD}/{AMARA}").json()["notes"]}


def test_notes_never_reach_the_student(client, as_user):
    as_user("student")
    responses = [client.get(path) for path in ("/api/v1/students/me/dashboard", "/api/v1/students/me/plan",
                                              "/api/v1/students/me/degree-audit", "/api/v1/students/me/ai/context")]
    responses.append(client.post("/api/v1/users/me/export"))
    for response in responses:
        assert response.status_code == 200, response.url
        assert "research assistant opening" not in response.text, response.url


def test_shared_ai_threads(client, as_user):
    as_user("advisor")
    assert_envelope(client.get(f"{RECORD}/{AMARA}/ai-threads"), 403, "NOT_SHARED")
    with SessionLocal() as session:
        row = session.get(UserPreference, 1)
        original = dict(row.data) if row and row.data else None
        data = dict(original or {})
        data["ai"] = {**data.get("ai", {}), "shareWithAdvisor": True}
        if row is None:
            session.add(UserPreference(user_id=1, data=data))
        else:
            row.data = data
        session.commit()
    try:
        threads = client.get(f"{RECORD}/{AMARA}/ai-threads").json()["threads"]
        assert threads and {"id", "title", "updatedAt"} <= set(threads[0])
        record = client.get(f"{RECORD}/{AMARA}").json()
        assert record["aiShared"] is True and any(a["text"].startswith("Asked Acadmate") for a in record["activity"])
    finally:
        with SessionLocal() as session:
            row = session.get(UserPreference, 1)
            if original is None:
                session.delete(row)
            else:
                row.data = original
            session.commit()
