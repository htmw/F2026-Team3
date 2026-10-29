"""Advisor dashboard (spec 20) and the approve / reopen decisions it uses (spec 23; the queue is in test_approvals.py)."""
from database import SessionLocal
from models import ApprovalRequest, AssignmentSubmission, AuditEvent, PlanItem
from test_foundation import assert_envelope

DASHBOARD = "/api/v1/advisor/dashboard"
APPROVALS = "/api/v1/advisor/approvals"
PRIYA_PLAN, DANIEL_FORM, MARCUS_DROP, AMARA_PLAN, LINA_PLAN, KIM_PLAN = 1706, 1707, 1708, 1709, 1710, 1704
PRIYA_ITEMS = (9003, 9004, 9006)


def test_needs_an_advisor(client, as_user):
    assert_envelope(client.get(DASHBOARD), 401, "UNAUTHENTICATED")
    assert_envelope(client.post(f"{APPROVALS}/{PRIYA_PLAN}/approve"), 401, "UNAUTHENTICATED")
    for role in ("student", "admin"):
        as_user(role)
        assert_envelope(client.get(DASHBOARD), 403, "FORBIDDEN")
        assert_envelope(client.post(f"{APPROVALS}/{PRIYA_PLAN}/approve"), 403, "FORBIDDEN")


def test_seeded_dashboard(client, as_user):
    as_user("advisor")
    data = client.get(DASHBOARD).json()
    assert data["advisor"] == {"displayName": "Dr. Smith", "subtitle": "Faculty advisor, Computer Science · Fall 2026",
                               "initials": "SS"}
    stats = {s["key"]: s for s in data["stats"]}
    assert (stats["advisees"]["value"], stats["advisees"]["note"]) == ("8", "M.S. CS")
    assert (stats["waiting"]["value"], stats["waiting"]["tag"], stats["waiting"]["tone"]) == ("5", "Action", "amber")
    assert stats["attention"]["value"] == "4"

    # Oldest first; quick approve is only offered when no blocking check failed.
    assert [q["id"] for q in data["queue"]] == [PRIYA_PLAN, DANIEL_FORM, LINA_PLAN, MARCUS_DROP, AMARA_PLAN]
    assert data["queueTotal"] == 5
    priya, daniel, lina, marcus, _ = data["queue"]
    assert lina["ok"] is False
    assert (priya["type"], priya["ok"], priya["check"], priya["name"]) == \
        ("Course plan", True, "meets all remaining requirements", "Priya S.")
    assert (daniel["type"], daniel["ok"], daniel["check"]) == ("Form", False, "project summary is missing")
    assert (marcus["type"], marcus["ok"]) == ("Request", False)

    today = data["today"]
    assert today["label"] == "Thu, Oct 1"
    assert [(m["time"], m["who"]) for m in today["meetings"]] == [
        ("10:00", "Drop-in office hours"), ("11:00", "Jonah W."), ("13:00", "Priya S."), ("15:00", "Amara O.")]
    assert today["meetings"][0]["action"] == "Details"
    assert today["meetings"][3]["action"] in ("Open", "Join", "Notes")  # depends on the time of day the tests run

    assert [a["level"] for a in data["attention"]] == ["High", "High", "Medium"]
    assert sum(c["n"] for c in data["caseload"]) == int(stats["advisees"]["value"])
    assert [(c["label"], c["n"]) for c in data["caseload"]] == [("On track", 4), ("Needs attention", 2), ("At risk", 2)]
    assert data["graduation"] == [{"n": 3, "label": "Dec 2026"}, {"n": 3, "label": "May 2027"}, {"n": 2, "label": "Later"}]


def test_approve_then_reopen(client, as_user):
    as_user("advisor")
    approved = client.post(f"{APPROVALS}/{PRIYA_PLAN}/approve", json={"comment": "Looks good."})
    assert approved.status_code == 200
    assert (approved.json()["id"], approved.json()["status"], approved.json()["canUndo"]) == (PRIYA_PLAN, "Approved", True)
    with SessionLocal() as db:
        assert {i.status for i in db.query(PlanItem).filter(PlanItem.id.in_(PRIYA_ITEMS))} == {"approved"}
        assert db.query(AuditEvent).filter(AuditEvent.action == "approval.approve",
                                           AuditEvent.target_id == str(PRIYA_PLAN)).count() == 1
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 4
    assert_envelope(client.post(f"{APPROVALS}/{PRIYA_PLAN}/approve"), 409, "CONFLICT")

    reopened = client.post(f"{APPROVALS}/{PRIYA_PLAN}/reopen").json()
    assert (reopened["id"], reopened["status"], reopened["canUndo"]) == (PRIYA_PLAN, "Pending", False)
    with SessionLocal() as db:
        assert {i.status for i in db.query(PlanItem).filter(PlanItem.id.in_(PRIYA_ITEMS))} == {"pending_approval"}
        request = db.get(ApprovalRequest, PRIYA_PLAN)
        assert (request.decided_at, request.decided_by, "before" in request.payload) == (None, None, False)
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 5
    assert_envelope(client.post(f"{APPROVALS}/{PRIYA_PLAN}/reopen"), 409, "CONFLICT")  # already pending


def test_ownership_and_reopen_window(client, as_user):
    as_user("advisor")
    assert_envelope(client.post(f"{APPROVALS}/{KIM_PLAN}/approve"), 404, "NOT_FOUND")  # Prof. Kim's queue
    assert_envelope(client.post(f"{APPROVALS}/999999/approve"), 404, "NOT_FOUND")
    error = assert_envelope(client.post(f"{APPROVALS}/1701/reopen"), 409, "CONFLICT")  # decided days ago
    assert error["message"] == "This decision can't be reopened anymore."


def test_approve_form_and_restore(client, as_user):
    """A failed check only disables the dashboard's quick approve; the decision itself is allowed (spec 23)."""
    def daniel_form():
        with SessionLocal() as db:
            sub = db.query(AssignmentSubmission).filter_by(assignment_id=1105, student_id=110).one()
            return sub.status, sub.score_text

    as_user("advisor")
    assert client.post(f"{APPROVALS}/{DANIEL_FORM}/approve").status_code == 200
    assert daniel_form() == ("graded", "Approved")
    assert client.post(f"{APPROVALS}/{DANIEL_FORM}/reopen").status_code == 200
    assert daniel_form() == ("submitted", None)
