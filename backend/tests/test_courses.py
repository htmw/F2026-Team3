"""GET /students/me/courses and GET /courses/{id}/grades (spec 11). conftest pins today to 2026-10-01 (Thu)."""
from conftest import login
from database import SessionLocal
from models import Student
from test_foundation import assert_envelope

PATH = "/api/v1/students/me/courses"
CS608, CS661, CS675, CS501 = 18, 19, 20, 11


def test_my_courses(client):
    login(client, "amara.okafor@pac.edu")
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()

    assert data["subtitle"] == "Fall 2026 · 3 courses · 9 credits in progress"
    assert data["counts"] == {"current": 3, "completed": 7, "planned": 2}
    assert data["addDropUrl"] is None and data["plannedNotice"] == "Spring 2027 registration opens Nov 3."
    assert [(row["enrollmentId"], row["code"], row["term"], row["status"], row["fulfills"]) for row in data["planned"]] == [
        (9002, "CS 680", "Spring 2027", "Planned", "Electives"),
        (9001, "CS 691", "Spring 2027", "Needs approval", "Capstone")]  # degree plan (spec 12)

    cards = {card["code"]: card for card in data["current"]}
    assert list(cards) == ["CS 608", "CS 661", "CS 675"]
    assert [card["tone"] for card in data["current"]] == ["teal", "indigo", "amber"]

    cs608 = cards["CS 608"]
    assert cs608["courseId"] == CS608 and cs608["credits"] == "3 credits"
    assert cs608["when"] == "Mon 18:10–20:55" and cs608["room"] == "Room 210" and cs608["office"] == "Mon 4–5 pm"
    assert cs608["grade"] == "B+" and cs608["pct"] == 40 and cs608["next"] == "Problem set 4 · Oct 9"
    assert cs608["insight"] == ("Problem sets are your lowest component this term. Two office-hour visits before the "
                                "Oct 19 midterm could lift this toward an A-.")

    assert cards["CS 661"]["insight"] == "You are ahead of pace in CS 661. Keep your current study rhythm."
    assert cards["CS 661"]["office"] == "Thu 5–6 pm"

    cs675 = cards["CS 675"]
    assert cs675["prof"] == "Prof. Lina Ortiz" and cs675["when"] == "Thu 10:00–12:45" and cs675["office"] == "Wed 2–3 pm"
    assert cs675["siteUrl"] == "https://lms.example.edu/cs675" and cs675["insight"] is None
    assert cs675["next"] == "Project topic proposal · Oct 3"  # zero-weight checkpoint (deadline until spec 15)
    assert cs675["upcoming"] == [
        {"date": "2026-10-03", "mon": "Oct", "day": "3", "title": "Project topic proposal", "meta": "Not graded separately"},
        {"date": "2026-10-22", "mon": "Oct", "day": "22", "title": "Midterm", "meta": "20% of grade"},
    ]

    week = {day["day"]: day["items"] for day in data["week"]}
    assert list(week) == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert [(item["time"], item["code"], item["kind"]) for item in week["Mon"]] == [
        ("16:00", "CS 608", "office"), ("18:10", "CS 608", "class")]
    assert [(item["time"], item["code"]) for item in week["Thu"]] == [("10:00", "CS 675"), ("18:10", "CS 661")]
    assert week["Tue"] == [] and week["Fri"] == []

    completed = data["completed"]
    assert [row["term"] for row in completed][:2] == ["Summer 2026", "Summer 2026"]
    assert completed[-1]["term"] == "Fall 2025"
    assert data["completedSummary"] == {"credits": 21, "gpa": 3.73}

    dashboard = client.get("/api/v1/students/me/dashboard").json()
    assert dashboard["gpa"]["cumulative"] == data["completedSummary"]["gpa"]


def test_my_courses_requires_student(client, as_user):
    assert_envelope(client.get(PATH), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(PATH), 403, "FORBIDDEN")


def test_my_courses_without_enrollments(client, make_user):
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
    login(client, user.email)
    data = client.get(PATH).json()
    assert data["counts"] == {"current": 0, "completed": 0, "planned": 0}
    assert data["subtitle"] == "Fall 2026 · 0 courses · 0 credits in progress"
    assert data["current"] == [] and all(day["items"] == [] for day in data["week"])
    assert data["completedSummary"] == {"credits": 0, "gpa": None}


def test_grades_for_student(client):
    login(client, "amara.okafor@pac.edu")
    data = client.get(f"/api/v1/courses/{CS608}/grades").json()
    assert data["weightedScore"] == 87.8 and data["letter"] == "B+"
    assert [(part["label"], part["weight"], part["display"]) for part in data["parts"]] == [
        ("Problem sets", 35, "86%"), ("Midterm", 30, "Oct 19"), ("Final", 30, "Dec 14"), ("Participation", 5, "100%")]

    cs675 = client.get(f"/api/v1/courses/{CS675}/grades").json()
    assert cs675["parts"][0] == {"label": "Team project", "weight": 40, "score": None, "display": "In progress"}
    assert cs675["weightedScore"] == 91.9

    assert client.get(f"/api/v1/courses/{CS661}/grades").json()["weightedScore"] == 95.8
    # Completed last year, so not "enrolled this term".
    assert_envelope(client.get(f"/api/v1/courses/{CS501}/grades"), 403, "FORBIDDEN")
    assert_envelope(client.get("/api/v1/courses/999/grades"), 404, "NOT_FOUND")


def test_grades_for_staff(client, as_user, make_user):
    as_user("advisor")
    assert client.get(f"/api/v1/courses/{CS608}/grades?studentId=101").json()["weightedScore"] == 87.8
    assert_envelope(client.get(f"/api/v1/courses/{CS608}/grades"), 400, "BAD_REQUEST")
    assert_envelope(client.get(f"/api/v1/courses/{CS608}/grades?studentId=999"), 403, "FORBIDDEN")  # not assigned

    as_user("admin")
    assert client.get(f"/api/v1/courses/{CS608}/grades?studentId=101").status_code == 200
    assert_envelope(client.get(f"/api/v1/courses/{CS501}/grades?studentId=101"), 404, "NOT_FOUND")
