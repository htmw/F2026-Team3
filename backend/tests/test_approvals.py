"""Advisor approvals queue (spec 23): list and detail rows, the drop effect, reopen rules and the badge."""
from datetime import timedelta

import pytest

from conftest import login
from database import SessionLocal
from models import ApprovalRequest, AssignmentSubmission, Enrollment, PlanItem
from test_foundation import assert_envelope
from test_messages import restore_messages  # noqa: F401 (fixture: decisions post notices to the students)

APPROVALS = "/api/v1/advisor/approvals"
PRIYA_PLAN, DANIEL_FORM, MARCUS_DROP, AMARA_PLAN, LINA_PLAN, KIM_PLAN = 1706, 1707, 1708, 1709, 1710, 1704
SMITH_PENDING = (PRIYA_PLAN, DANIEL_FORM, MARCUS_DROP, AMARA_PLAN, LINA_PLAN)
PLAN_ITEMS = (9001, 9002, 9003, 9004, 9005, 9006)


@pytest.fixture
def restore_queue(restore_messages):  # noqa: F811
    """Puts Dr. Smith's five requests and everything they touch back to the seeded state (notices via restore_messages)."""
    yield
    with SessionLocal() as session:
        for request in session.query(ApprovalRequest).filter(ApprovalRequest.id.in_(SMITH_PENDING)):
            payload = dict(request.payload or {})
            payload.pop("before", None)
            request.payload, request.status, request.comment = payload, "pending", None
            request.decided_at = request.decided_by = None
        for item in session.query(PlanItem).filter(PlanItem.id.in_(PLAN_ITEMS)):
            item.status = "pending_approval"
        form = session.query(AssignmentSubmission).filter_by(assignment_id=1105, student_id=110).one()
        form.status, form.score_text, form.feedback = "submitted", None, None
        session.query(Enrollment).filter_by(student_id=108, course_id=18, term="Fall 2026").one().status = "in_progress"
        session.commit()


def test_access(client, as_user):
    assert_envelope(client.get(APPROVALS), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(APPROVALS), 403, "FORBIDDEN")
    as_user("advisor")
    assert_envelope(client.get(f"{APPROVALS}/999999"), 404, "NOT_FOUND")
    assert_envelope(client.get(f"{APPROVALS}/{KIM_PLAN}"), 404, "NOT_FOUND")  # Prof. Kim's queue
    assert_envelope(client.get(f"{APPROVALS}?status=Done"), 422, "VALIDATION_ERROR")


def test_pending_tab(client, as_user):
    as_user("advisor")
    data = client.get(APPROVALS).json()
    assert data["tabs"] == [{"label": "Pending", "count": 5}, {"label": "Approved", "count": 2},
                            {"label": "Changes requested", "count": 1}]
    rows = data["rows"]
    assert [r["id"] for r in rows] == [PRIYA_PLAN, DANIEL_FORM, LINA_PLAN, MARCUS_DROP, AMARA_PLAN]  # oldest first
    assert all(r["status"] == "Pending" and r["canUndo"] is False for r in rows)
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 5

    decided = client.get(f"{APPROVALS}?status=Approved").json()["rows"]
    assert [r["id"] for r in decided] == [1702, 1701]  # newest decision first


def test_rows(client, as_user):
    as_user("advisor")
    rows = {r["id"]: r for r in client.get(APPROVALS).json()["rows"]}

    priya = rows[PRIYA_PLAN]
    assert (priya["name"], priya["type"], priya["ok"], priya["checkShort"]) == ("Priya S.", "Course plan", True, "Pre-check passed")
    assert priya["check"] == "9 credits keeps full-time status."
    assert [line["a"] for line in priya["lines"]] == ["CS 691 Capstone Project", "CS 680 Machine Learning", "CS 665 Computer Vision"]
    assert all(line["b"].endswith("3 cr") for line in priya["lines"])

    daniel = rows[DANIEL_FORM]
    assert (daniel["type"], daniel["ok"], daniel["checkShort"]) == ("Form", False, "Needs a look")
    assert daniel["check"] == "The project summary section is empty. Approving now would leave the form incomplete."
    assert {"a": "Project summary", "b": "Missing"} in daniel["lines"]

    marcus = rows[MARCUS_DROP]
    assert (marcus["type"], marcus["ok"]) == ("Request", False)
    assert marcus["check"].startswith("Dropping leaves 6 credits, below full-time status.")
    assert marcus["lines"] == [{"a": "Drop", "b": "CS 608 · 3 cr"}, {"a": "Credits after drop", "b": "6"}]

    lina = rows[LINA_PLAN]
    assert lina["ok"] is False and "CS 691" in lina["check"]

    assert client.get(f"{APPROVALS}/{AMARA_PLAN}").json() == rows[AMARA_PLAN]


def test_approve_moves_between_tabs(client, as_user, restore_queue):
    as_user("advisor")
    row = client.post(f"{APPROVALS}/{AMARA_PLAN}/approve", json={"comment": "Send the form soon."}).json()
    assert (row["status"], row["comment"], row["canUndo"]) == ("Approved", "Send the form soon.", True)
    tabs = {t["label"]: t["count"] for t in client.get(APPROVALS).json()["tabs"]}
    assert (tabs["Pending"], tabs["Approved"]) == (4, 3)
    assert client.get(f"{APPROVALS}?status=Approved").json()["rows"][0]["id"] == AMARA_PLAN
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 4

    assert client.post(f"{APPROVALS}/{AMARA_PLAN}/reopen").json()["status"] == "Pending"
    with SessionLocal() as session:
        assert {i.status for i in session.query(PlanItem).filter(PlanItem.id.in_((9001, 9002)))} == {"pending_approval"}


def test_drop_withdraws_and_reopen_restores(client, as_user, restore_queue):
    def marcus_cs608():
        with SessionLocal() as session:
            return session.query(Enrollment).filter_by(student_id=108, course_id=18, term="Fall 2026").one().status

    as_user("advisor")
    assert client.post(f"{APPROVALS}/{MARCUS_DROP}/approve").status_code == 200
    assert marcus_cs608() == "withdrawn"
    assert client.post(f"{APPROVALS}/{MARCUS_DROP}/reopen").status_code == 200
    assert marcus_cs608() == "in_progress"

    # Asking for changes leaves the enrollment alone.
    client.post(f"{APPROVALS}/{MARCUS_DROP}/request-changes", json={"comment": "Let's talk about funding first."})
    assert marcus_cs608() == "in_progress"


def test_reopen_refused_once_the_plan_changed(client, as_user, restore_queue):
    as_user("advisor")
    client.post(f"{APPROVALS}/{PRIYA_PLAN}/request-changes", json={"comment": "Swap one elective."})
    with SessionLocal() as session:
        session.get(PlanItem, 9006).status = "planned"  # the student revised the plan
        session.commit()
    error = assert_envelope(client.post(f"{APPROVALS}/{PRIYA_PLAN}/reopen"), 409, "CONFLICT")
    assert error["message"] == "This decision can't be reopened anymore."


def test_reopen_refused_after_24_hours(client, as_user, restore_queue):
    as_user("advisor")
    client.post(f"{APPROVALS}/{LINA_PLAN}/approve")
    with SessionLocal() as session:
        request = session.get(ApprovalRequest, LINA_PLAN)
        request.decided_at = request.decided_at - timedelta(hours=25)
        session.commit()
    assert client.get(f"{APPROVALS}/{LINA_PLAN}").json()["canUndo"] is False
    assert_envelope(client.post(f"{APPROVALS}/{LINA_PLAN}/reopen"), 409, "CONFLICT")


def test_other_advisor_sees_only_their_queue(client):
    login(client, "daniel.kim@pac.edu")
    data = client.get(APPROVALS).json()
    assert {r["id"] for r in data["rows"]} == {1704, 1705}
    assert_envelope(client.post(f"{APPROVALS}/{AMARA_PLAN}/approve"), 404, "NOT_FOUND")
