"""GET /students/me/dashboard (spec 10). conftest pins today to 2026-10-01 (Thu, Fall 2026 week 6)."""
from conftest import login
from database import SessionLocal
from models import Student
from services import dashboard
from test_foundation import assert_envelope

PATH = "/api/v1/students/me/dashboard"


def test_dashboard_for_seeded_student(client, as_user):
    login(client, "amara.okafor@pac.edu")
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()

    assert data["student"] == {"firstName": "Amara", "initials": "AO",
                               "termLabel": "Fall 2026 · Week 6 · M.S. Computer Science"}

    gpa = data["gpa"]
    assert gpa["cumulative"] == 3.73 and gpa["change"] == 0.05 and gpa["status"] == "On track"
    assert [point["term"] for point in gpa["trend"]] == ["Fall 2025", "Spring 2026", "Summer 2026", "Fall 2026"]
    assert [point["gpa"] for point in gpa["trend"][:3]] == [3.7, 3.65, 3.85]
    assert gpa["trend"][-1]["current"] is True and not gpa["trend"][0]["current"]

    stats = {stat["key"]: stat for stat in data["stats"]}
    assert list(stats) == ["onTime", "credits", "attendance", "graduation"]
    assert stats["credits"]["value"] == "21 / 36" and stats["credits"]["pct"] == 58
    assert stats["credits"]["note"] == "9 in progress · 6 left after this term"
    assert stats["attendance"]["value"] == "96%" and stats["attendance"]["note"] == "1 absence this term"
    assert stats["graduation"]["value"] == "May 2027"
    assert (stats["onTime"]["value"], stats["onTime"]["pill"], stats["onTime"]["note"]) == ("100%", "Good", "3 of 3 submitted on time")

    requirements = {row["label"]: row for row in data["requirements"]}
    assert requirements["Foundation"]["count"] == "2 of 2" and requirements["Foundation"]["pct"] == 100
    assert requirements["Capstone"] == {"label": "Capstone", "count": "0 of 1", "pct": 0, "warn": True}  # registration Nov 3

    assert data["studyHours"]["total"] == 21.5 and data["studyHours"]["goal"] == 20
    assert [day["today"] for day in data["studyHours"]["days"]].index(True) == 3  # Thursday

    assert data["today"]["label"] == "Thu, Oct 1"
    assert [(event["time"], event["title"], event["meta"]) for event in data["today"]["events"]] == [
        ("10:00", "Data Science (CS 675)", "Room 1201"),
        ("13:30", "Team project sync", "Study room 3 · 45 min"),
        ("15:00", "Advising check-in", "Online · Dr. Sarah Smith · 30 min"),
        ("18:10", "Python Programming (CS 661)", "Room 318")]

    courses = {course["code"]: course for course in data["courses"]}
    assert courses["CS 675"] == {"code": "CS 675", "name": "Data Science", "prof": "Prof. Lina Ortiz",
                                 "pct": 45, "grade": "A-", "tone": "amber"}
    assert [course["grade"] for course in data["courses"]] == ["B+", "A", "A-"]

    assert [(t["id"], t["title"], t["course"], t["due"], t["status"]) for t in data["tasks"]] == [
        (1101, "Project topic proposal", "CS 675", "Oct 3", "Due soon"),
        (1102, "Week 6 tutorial", "CS 661", "Oct 5", "In progress"),
        (1103, "Problem set 4", "CS 608", "Oct 9", "Not started"),
        (1104, "Project 2 checkpoint", "CS 661", "Oct 16", "Not started")]  # assignments (spec 15)
    assert data["alert"] == "Capstone registration opens Nov 3. Pre-approval form is still missing."  # degree audit (spec 12)
    assert data["recommendation"]["title"] == "Spring 2027 recommendation"  # AI advisor rules engine (spec 13)

    # Same GPA as the advisor/admin academic profile.
    as_user("admin")
    profile = client.get("/api/v1/students/101/academic-profile").json()
    assert profile["student"]["gpa"] == gpa["cumulative"]


def test_dashboard_requires_student(client, as_user):
    assert_envelope(client.get(PATH), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(PATH), 403, "FORBIDDEN")
    as_user("admin")
    assert_envelope(client.get(PATH), 403, "FORBIDDEN")


def test_dashboard_without_enrollments(client, make_user):
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
    login(client, user.email)
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()
    assert data["gpa"] == {"cumulative": None, "change": None, "status": "No grades yet", "trend": []}
    assert data["courses"] == [] and data["today"]["events"] == []
    assert data["studyHours"]["total"] == 0
    assert {stat["key"]: stat["value"] for stat in data["stats"]}["credits"] == "0 / 36"


def test_student_row_missing(client, make_user):
    user = make_user("student")
    login(client, user.email)
    assert_envelope(client.get(PATH), 404, "NOT_FOUND")


def test_failed_section_falls_back_to_empty(client, monkeypatch):
    def broken(db, student):
        raise RuntimeError("feature table missing")

    monkeypatch.setattr(dashboard, "today_events", broken)
    # build_dashboard captured the function in its table at call time, so patching the module attribute works.
    login(client, "amara.okafor@pac.edu")
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()
    assert data["today"] == {"label": "Thu, Oct 1", "events": []}
    assert len(data["courses"]) == 3  # other sections unaffected
