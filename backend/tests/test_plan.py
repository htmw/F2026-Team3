"""Degree plan (spec 12): degree audit, term plan, add / remove / submit. conftest pins today to 2026-10-01."""
import pytest

from conftest import login
from database import SessionLocal
from models import ApprovalRequest, Message, PlanItem, Student, Term
from services import plan as plan_service
from test_foundation import assert_envelope

AUDIT = "/api/v1/students/me/degree-audit"
PLAN = "/api/v1/students/me/plan"
AMARA = "amara.okafor@pac.edu"
FALL_2026, SPRING_2027, SUMMER_2027, FALL_2027 = 4, 5, 6, 7
AMARA_NOTICES = 1304  # her seeded Acadmate system conversation


@pytest.fixture
def restore_plan():
    """Tests that change Amara's plan put the seeded plan back afterwards (the seeded database is shared)."""
    columns = ("id", "student_id", "course_id", "term_id", "status", "note", "source", "created_at")
    with SessionLocal() as db:
        saved = [{name: getattr(item, name) for name in columns}
                 for item in db.query(PlanItem).filter(PlanItem.student_id == 101)]
    yield
    with SessionLocal() as db:
        db.query(ApprovalRequest).filter(ApprovalRequest.student_id == 101).delete()
        # The submit notice in Amara's Acadmate conversation (spec 16).
        db.query(Message).filter(Message.conversation_id == AMARA_NOTICES, Message.text.like("%waiting for advisor approval.")).delete(
            synchronize_session=False)
        db.query(PlanItem).filter(PlanItem.student_id == 101).delete()
        db.add_all(PlanItem(**row) for row in saved)
        db.commit()


@pytest.fixture
def new_student(client, make_user):
    """A signed-in student with no enrollments or plan."""
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1, start_term_id=4,
                       expected_graduation="May 2028"))
        db.commit()
    login(client, user.email)
    return user


def test_degree_audit_for_seeded_student(client):
    login(client, AMARA)
    response = client.get(AUDIT)
    assert response.status_code == 200
    data = response.json()

    assert data["subtitle"] == "M.S. Computer Science · catalog year 2025–26 · expected graduation May 2027"
    assert data["requirementsSubtitle"] == "M.S. Computer Science · 12 courses · 36 credits"
    assert data["graduation"] == {"label": "May 2027", "status": "Pending capstone approval"}
    assert data["alert"] == "Capstone registration opens Nov 3. Pre-approval form is still missing."

    stats = [(s["label"], s["value"], s["pct"], s["warn"], s["color"], s["note"]) for s in data["stats"]]
    assert stats[:3] == [
        ("Credits earned", "21 / 36", 58, False, None, "7 of 12 courses complete"),
        ("In progress", "9", 25, False, "violet", "3 courses this Fall"),
        ("Left after this term", "6", 17, False, "amber", "Capstone and 1 elective"),
    ]
    assert stats[3][:2] == ("Expected graduation", "May 2027") and 0 < stats[3][2] < 100

    groups = {group["title"]: group for group in data["groups"]}
    assert list(groups) == ["Foundation", "Core courses", "Electives", "Capstone"]
    assert [(g["required"], g["count"], g["allDone"]) for g in groups.values()] == [
        (2, "2 of 2 done", True),
        (4, "4 of 4 done", True),
        (5, "1 of 5 done · 3 in progress", False),
        (1, "0 of 1 done", False),
    ]
    assert [(item["code"], item["status"], item["meta"]) for item in groups["Electives"]["items"]] == [
        ("CS 650", "Completed", "Summer 2026"),
        ("CS 608", "In progress", "Fall 2026"),
        ("CS 661", "In progress", "Fall 2026"),
        ("CS 675", "In progress", "Fall 2026"),
        ("CS 680", "Planned", "Spring 2027"),
    ]
    assert groups["Capstone"]["items"] == [{"code": "CS 691", "name": "Capstone Project", "status": "Needs approval",
                                            "meta": "Spring 2027"}]


def test_plan_for_seeded_student(client):
    login(client, AMARA)
    response = client.get(PLAN)
    assert response.status_code == 200
    data = response.json()

    assert [(t["name"], t["tag"], t["credits"]) for t in data["terms"]] == [
        ("Fall 2025", "Done", "9 credits"),
        ("Spring 2026", "Done", "6 credits"),
        ("Summer 2026", "Done", "6 credits"),
        ("Fall 2026", "Current", "9 credits"),
        ("Spring 2027", "Planned", "6 credits"),
        ("Summer 2027", "Planned", "0 credits"),  # one of the next two terms, nothing planned yet
    ]
    assert [c["code"] for c in data["terms"][3]["courses"]] == ["CS 608", "CS 661", "CS 675"]
    assert data["terms"][3]["courses"][0] == {"enrollmentId": 308, "code": "CS 608", "name": "Algorithms & Computing Theory",
                                              "status": "current", "planStatus": None}
    assert [(c["enrollmentId"], c["code"], c["status"], c["planStatus"]) for c in data["terms"][4]["courses"]] == [
        (9002, "CS 680", "planned", "Planned"), (9001, "CS 691", "planned", "Needs approval")]

    assert data["futureTerms"] == [{"id": SPRING_2027, "name": "Spring 2027"}, {"id": SUMMER_2027, "name": "Summer 2027"},
                                   {"id": FALL_2027, "name": "Fall 2027"}]
    available = {row["code"]: row for row in data["available"]}
    assert available["CS 665"] == {"code": "CS 665", "name": "Computer Vision", "type": "Elective", "offered": True}
    assert "CS 680" not in available and "CS 501" not in available and "CS 608" not in available
    assert data["notice"] == ("Spring 2027 is a draft until your advisor approves it. "
                              "Capstone pre-approval is due Oct 20; registration opens Nov 3.")


def test_add_and_remove(client, restore_plan):
    login(client, AMARA)
    response = client.post(PLAN, json={"courseCode": "CS 665", "termId": SUMMER_2027, "note": "Backup elective"})
    assert response.status_code == 201
    added = response.json()
    assert added == {"enrollmentId": added["enrollmentId"], "code": "CS 665", "name": "Computer Vision",
                     "term": "Summer 2027", "planStatus": "Planned"}
    summer = next(t for t in client.get(PLAN).json()["terms"] if t["name"] == "Summer 2027")
    assert [c["code"] for c in summer["courses"]] == ["CS 665"] and summer["credits"] == "3 credits"

    assert client.delete(f"{PLAN}/{added['enrollmentId']}").status_code == 204
    assert_envelope(client.delete(f"{PLAN}/{added['enrollmentId']}"), 404, "NOT_FOUND")


def test_add_validation(client, restore_plan):
    login(client, AMARA)
    error = assert_envelope(client.post(PLAN, json={"courseCode": "CS 680", "termId": SUMMER_2027}), 409, "CONFLICT")
    assert error["message"] == "CS 680 is already on your record or plan."
    error = assert_envelope(client.post(PLAN, json={"courseCode": "CS 501", "termId": SUMMER_2027}), 409, "CONFLICT")
    assert error["message"] == "CS 501 is already on your record or plan."
    error = assert_envelope(client.post(PLAN, json={"courseCode": "CS 665", "termId": FALL_2026}), 400, "BAD_REQUEST")
    assert error["message"] == "Fall 2026 has already started."
    assert_envelope(client.post(PLAN, json={"courseCode": "CS 999", "termId": SUMMER_2027}), 404, "NOT_FOUND")
    assert_envelope(client.post(PLAN, json={"courseCode": "CS 665", "termId": 999}), 404, "NOT_FOUND")
    error = assert_envelope(client.post(PLAN, json={"courseCode": "CS 665", "termId": SUMMER_2027, "note": "x" * 501}),
                            422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "note"


def test_prerequisites(client, new_student):
    error = assert_envelope(client.post(PLAN, json={"courseCode": "CS 680", "termId": SPRING_2027}), 400, "BAD_REQUEST")
    assert error["message"] == "Take CS 675 before CS 680."
    assert client.post(PLAN, json={"courseCode": "CS 675", "termId": SPRING_2027}).status_code == 201
    # Planned in the same term doesn't count; an earlier term does.
    assert_envelope(client.post(PLAN, json={"courseCode": "CS 680", "termId": SPRING_2027}), 400, "BAD_REQUEST")
    assert client.post(PLAN, json={"courseCode": "CS 680", "termId": SUMMER_2027}).status_code == 201
    # The capstone's prerequisites are missing too; the first one (by code) is named.
    capstone = client.post(PLAN, json={"courseCode": "CS 691", "termId": FALL_2027})
    assert capstone.status_code == 400 and capstone.json()["error"]["message"] == "Take CS 600 before CS 691."


def test_submit_spring_plan(client, as_user, restore_plan):
    login(client, AMARA)
    response = client.post(f"{PLAN}/submit", json={"termId": SPRING_2027})
    assert response.status_code == 200
    data = response.json()
    assert data["precheck"] == {
        "ok": True,
        "text": "Ready for your advisor. 1 thing to finish soon.",
        "checks": [
            {"ok": True, "blocking": False, "text": "Covers all remaining requirements (6 credits)"},
            {"ok": True, "blocking": False, "text": "Prerequisites met for both courses"},
            {"ok": False, "blocking": False, "text": "Capstone pre-approval form not submitted yet (due Oct 20)"},
        ],
    }
    spring = next(t for t in client.get(PLAN).json()["terms"] if t["name"] == "Spring 2027")
    assert {c["planStatus"] for c in spring["courses"]} == {"Pending approval"}

    with SessionLocal() as db:
        request = db.get(ApprovalRequest, data["requestId"])
        assert (request.type, request.status, request.advisor_id, request.term_id) == ("plan", "pending", 201, SPRING_2027)
        assert request.title == "Spring 2027 plan · Machine Learning + Capstone Project"
        assert sorted(request.payload["planItemIds"]) == [9001, 9002]
        notice = db.query(Message).filter(Message.conversation_id == AMARA_NOTICES).order_by(Message.id.desc()).first()
        assert (notice.sender_id, notice.text) == (None, "Your Spring 2027 plan is waiting for advisor approval.")

    error = assert_envelope(client.post(f"{PLAN}/submit", json={"termId": SPRING_2027}), 409, "CONFLICT")
    assert error["message"] == "Your Spring 2027 plan is already waiting for your advisor."
    error = assert_envelope(client.delete(f"{PLAN}/9001"), 409, "CONFLICT")
    assert error["message"] == "This course is waiting for your advisor. Ask them to send it back first."
    error = assert_envelope(client.post(f"{PLAN}/submit", json={"termId": FALL_2027}), 400, "BAD_REQUEST")
    assert error["message"] == "Fall 2027 has no planned courses to send."

    as_user("advisor")
    assert client.get("/api/v1/users/me/badges").json()["badges"]["approvals"] == 1


def test_precheck_blocking_and_warnings(client, new_student):
    assert client.post(PLAN, json={"courseCode": "CS 675", "termId": SPRING_2027}).status_code == 201
    assert client.post(PLAN, json={"courseCode": "CS 680", "termId": SUMMER_2027}).status_code == 201
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.user_id == new_student.user_id).one()
        # A prerequisite moved to a later term makes the earlier plan blocking.
        item = db.query(PlanItem).filter(PlanItem.student_id == student.student_id, PlanItem.course_id == 20).one()
        item.term_id = FALL_2027
        db.commit()
        result = plan_service.precheck(db, student, db.get(Term, SUMMER_2027))
    assert result["ok"] is False and result["text"] == "1 thing to fix before your advisor can approve."
    texts = {check["text"]: check for check in result["checks"]}
    assert texts["Take CS 675 before CS 680"]["blocking"] is True
    assert texts["CS 680 isn't offered in Summer 2027"]["blocking"] is False
    assert any(text.startswith("Leaves ") for text in texts)


def test_plan_requires_student(client, as_user):
    assert_envelope(client.get(AUDIT), 401, "UNAUTHENTICATED")
    assert_envelope(client.get(PLAN), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(AUDIT), 403, "FORBIDDEN")
    assert_envelope(client.post(PLAN, json={"courseCode": "CS 665", "termId": SUMMER_2027}), 403, "FORBIDDEN")


def test_cannot_remove_someone_elses_item(client, new_student):
    assert_envelope(client.delete(f"{PLAN}/9001"), 404, "NOT_FOUND")
