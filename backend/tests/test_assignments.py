"""Assignments (spec 15). conftest pins today to 2026-10-01 (Thu)."""
from datetime import date, datetime

import pytest

from conftest import login
from core.time import local_zone
from database import SessionLocal
from models import ApprovalRequest, AssignmentSubmission, Student
from services import assignments
from test_foundation import assert_envelope

PATH = "/api/v1/students/me/assignments"
AMARA = "amara.okafor@pac.edu"
PROPOSAL, TUTORIAL, PS4, CHECKPOINT, FORM, LAB4 = 1101, 1102, 1103, 1104, 1105, 1106
LONG_SUMMARY = " ".join(["word"] * 60)


def progress(client, assignment_id, body):
    return client.patch(f"/api/v1/assignments/{assignment_id}/progress", json=body)


def submit(client, assignment_id, body=None):
    return client.post(f"/api/v1/assignments/{assignment_id}/submit", json=body)


@pytest.fixture
def restore_assignments():
    """Put Amara's seeded submissions back and drop the form requests a test created (the database is shared)."""
    columns = ("id", "assignment_id", "student_id", "status", "steps_done", "submitted_at", "score", "score_text",
               "form_fields", "feedback")
    with SessionLocal() as db:
        saved = [{name: getattr(row, name) for name in columns}
                 for row in db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == 101)]
    yield
    with SessionLocal() as db:
        db.query(ApprovalRequest).filter(ApprovalRequest.student_id == 101, ApprovalRequest.type == "form").delete()
        db.query(AssignmentSubmission).filter(AssignmentSubmission.student_id == 101).delete()
        db.add_all(AssignmentSubmission(**row) for row in saved)
        db.commit()


def test_list_for_seeded_student(client):
    login(client, AMARA)
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()

    assert data["subtitle"] == "Fall 2026 · 8 items across 3 courses and advising"
    assert [(tab["label"], tab["count"]) for tab in data["tabs"]] == [
        ("All", 8), ("To do", 3), ("In progress", 2), ("Submitted", 1), ("Graded", 2)]
    assert [course["value"] for course in data["courses"]] == ["CS 675", "CS 661", "CS 608", "Advising"]
    assert [(stat["label"], stat["value"], stat["note"]) for stat in data["stats"]] == [
        ("Due in next 10 days", "3", "Next: proposal on Oct 3"),
        ("In progress", "2", "CS 675 and CS 661"),
        ("Awaiting grade", "1", "Lab 4 · CS 675"),
        ("Graded average", "91%", "Across 2 graded items"),
    ]

    rows = data["rows"]
    assert [row["id"] for row in rows] == [1101, 1102, 1103, 1104, 1105, 1106, 1107, 1108]
    proposal = rows[0]
    assert {key: proposal[key] for key in ("course", "due", "dueDate", "status", "deadline", "score", "weight", "type")} == {
        "course": "CS 675", "due": "Oct 3", "dueDate": "2026-10-03", "status": "In progress", "deadline": "Due soon",
        "score": "—", "weight": "5%", "type": "Team"}
    assert proposal["submissionUrl"] == "https://lms.example.edu/cs675/a/1101"
    assert [step["done"] for step in proposal["steps"]] == [True, False, False, False]
    assert proposal["steps"][0]["text"] == "Agree on the topic with the team"

    form = next(row for row in rows if row["id"] == FORM)
    assert (form["course"], form["weight"], form["type"], form["deadline"], form["submissionUrl"]) == (
        "Advising", "Required", "Form", "Not started", None)
    assert [(row["status"], row["score"], row["deadline"]) for row in rows[5:]] == [
        ("Submitted", "—", "Done"), ("Graded", "84%", "Done"), ("Graded", "98%", "Done")]


def test_steps_and_start(client, restore_assignments):
    login(client, AMARA)
    response = progress(client, PS4, {"stepsDone": []})
    assert response.status_code == 200 and response.json() == {"status": "To do", "stepsDone": []}

    saved = progress(client, PROPOSAL, {"stepsDone": [2, 0, 2]}).json()
    assert saved == {"status": "In progress", "stepsDone": [0, 2]}
    error = assert_envelope(progress(client, PROPOSAL, {"stepsDone": [4]}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "stepsDone"

    assert progress(client, CHECKPOINT, {"status": "In progress"}).json()["status"] == "In progress"
    tabs = {tab["label"]: tab["count"] for tab in client.get(PATH).json()["tabs"]}
    assert (tabs["To do"], tabs["In progress"]) == (2, 3)

    error = assert_envelope(progress(client, LAB4, {"stepsDone": []}), 409, "CONFLICT")
    assert error["message"] == "This assignment is already submitted."


def test_submit_regular_item(client, restore_assignments):
    login(client, AMARA)
    response = submit(client, PS4)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Submitted" and data["precheck"] is None
    submitted = datetime.fromisoformat(data["submittedAt"].replace("Z", "+00:00"))
    assert submitted.astimezone(local_zone()).date() == date(2026, 10, 1)  # today in school time

    error = assert_envelope(submit(client, PS4), 409, "CONFLICT")
    assert error["message"] == "This assignment is already submitted."
    row = next(row for row in client.get(PATH).json()["rows"] if row["id"] == PS4)
    assert (row["status"], row["deadline"]) == ("Submitted", "Done")


def test_submit_capstone_form(client, as_user, restore_assignments):
    login(client, AMARA)
    error = assert_envelope(submit(client, FORM), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "Proposed topic"
    error = assert_envelope(submit(client, FORM, {"fields": {"Proposed topic": "Fraud detection", "Project summary": " "}}),
                            422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "Project summary"
    assert client.get("/api/v1/students/me/degree-audit").json()["alert"] is not None

    response = submit(client, FORM, {"fields": {"Proposed topic": "Fraud detection", "Project summary": "Graph models for card fraud."}})
    assert response.status_code == 200
    precheck = response.json()["precheck"]
    assert precheck["ok"] is True and precheck["text"] == "Ready for your advisor. 1 thing to finish soon."
    assert precheck["checks"][-1] == {"ok": False, "blocking": False, "text": "Project summary looks short."}

    with SessionLocal() as db:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.student_id == 101, ApprovalRequest.type == "form").one()
        assert (request.status, request.advisor_id, request.title) == ("pending", 201, "Capstone pre-approval form")
        assert request.payload == {"assignmentId": FORM, "fields": {"Proposed topic": "Fraud detection",
                                                                    "Project summary": "Graph models for card fraud."}}

    # The degree plan sees the form (spec 12): no alert, and the precheck passes that check.
    assert client.get("/api/v1/students/me/degree-audit").json()["alert"] is None
    assert "Capstone pre-approval is due" not in (client.get("/api/v1/students/me/plan").json()["notice"] or "")
    assert_envelope(submit(client, FORM, {"fields": {"Proposed topic": "x", "Project summary": LONG_SUMMARY}}), 409, "CONFLICT")

    as_user("advisor")
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 1


def test_form_decision(client, restore_assignments):
    login(client, AMARA)
    submit(client, FORM, {"fields": {"Proposed topic": "Fraud detection", "Project summary": LONG_SUMMARY}})
    with SessionLocal() as db:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.student_id == 101, ApprovalRequest.type == "form").one()
        request.status, request.comment = "changes_requested", "Name a dataset."
        assignments.apply_form_decision(db, request)
        db.commit()
    row = next(row for row in client.get(PATH).json()["rows"] if row["id"] == FORM)
    assert row["status"] == "In progress" and row["desc"].endswith("Advisor: Name a dataset.")

    with SessionLocal() as db:
        request = db.query(ApprovalRequest).filter(ApprovalRequest.student_id == 101, ApprovalRequest.type == "form").one()
        request.status = "approved"
        assignments.apply_form_decision(db, request)
        db.commit()
    row = next(row for row in client.get(PATH).json()["rows"] if row["id"] == FORM)
    assert (row["status"], row["score"]) == ("Graded", "Approved")


def test_other_students_and_roles(client, as_user, make_user):
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
    login(client, user.email)
    rows = client.get(PATH).json()["rows"]
    assert [row["id"] for row in rows] == [FORM]  # no current sections: only the program's advising item
    assert_envelope(progress(client, PS4, {"stepsDone": []}), 404, "NOT_FOUND")
    assert_envelope(submit(client, PS4), 404, "NOT_FOUND")

    client.cookies.clear()
    assert_envelope(client.get(PATH), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(PATH), 403, "FORBIDDEN")
    assert_envelope(submit(client, PS4), 403, "FORBIDDEN")
