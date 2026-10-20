"""Settings (spec 17): /users/me profile, preferences, Google link, export and self-service deletion.
conftest pins today to 2026-10-01."""
from copy import deepcopy

import pytest

from conftest import login
from database import SessionLocal
from models import AiThread, AuditEvent, Enrollment, Student, User, UserPreference
from seed_data import DEMO_PASSWORD
from test_foundation import assert_envelope

ME = "/api/v1/users/me"
PREFS = "/api/v1/users/me/preferences"
AMARA, SARAH, JORDAN = "amara.okafor@pac.edu", "sarah.smith@pac.edu", "jordan.lee@pac.edu"


@pytest.fixture
def restore_amara():
    """Tests that change Amara's preferences or profile put the seeded values back."""
    with SessionLocal() as db:
        saved_prefs = deepcopy(db.get(UserPreference, 1).data)
        user, student = db.get(User, 1), db.get(Student, 101)
        saved_user = (user.name, user.first_name, user.last_name, user.preferred_name, user.email)
        saved_student = (student.name, student.email, student.expected_graduation)
    yield
    with SessionLocal() as db:
        db.get(UserPreference, 1).data = saved_prefs
        user, student = db.get(User, 1), db.get(Student, 101)
        user.name, user.first_name, user.last_name, user.preferred_name, user.email = saved_user
        student.name, student.email, student.expected_graduation = saved_student
        db.commit()


@pytest.fixture
def new_student(client, make_user):
    """A signed-in student with a password and no other data."""
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
    login(client, user.email)
    return user


# --- GET /users/me ----------------------------------------------------------------------------------------------

def test_me_for_student(client):
    login(client, AMARA)
    data = client.get(ME).json()
    assert data["profile"] == {
        "fullName": "Amara Okafor", "preferredName": "Amara", "email": AMARA, "initials": "AO", "role": "student",
        "hasPassword": True, "studentNumber": "S1002101", "program": "M.S. Computer Science", "advisor": "Dr. Sarah Smith",
        "expectedGraduation": "May 2027",
    }
    assert data["preferences"] == {
        "notify": {"deadlines": True, "messages": True, "suggestions": True, "weeklySummary": False, "sms": False},
        "reminderTiming": "2 days before",
        "ai": {"useGrades": True, "useSchedule": True, "dashboardSuggestions": True, "shareWithAdvisor": False},
        "aiStyle": "Concise", "targetGraduation": "May 2027", "classTime": "Evening",
        "graduationOptions": ["December 2026", "May 2027", "August 2027", "December 2027"],
    }
    assert data["google"] == {"available": False, "connected": False, "email": None}


def test_me_for_staff_has_no_student_fields(client):
    login(client, SARAH)
    profile = client.get(ME).json()["profile"]
    assert profile["role"] == "advisor" and profile["studentNumber"] is None and profile["program"] is None


def test_me_requires_sign_in(client):
    assert_envelope(client.get(ME), 401, "UNAUTHENTICATED")


# --- PATCH /users/me --------------------------------------------------------------------------------------------

def test_preferred_name_changes_greeting(client, restore_amara):
    login(client, AMARA)
    response = client.patch(ME, json={"preferredName": "  Mara  "})
    assert response.status_code == 200
    user = response.json()["user"]
    assert (user["preferredName"], user["firstName"], user["fullName"], user["initials"]) == ("Mara", "Mara", "Amara Okafor", "AO")
    assert client.get("/api/v1/auth/me").json()["user"]["firstName"] == "Mara"
    assert client.get("/api/v1/students/me/dashboard").json()["student"]["firstName"] == "Mara"

    user = client.patch(ME, json={"preferredName": None}).json()["user"]
    assert (user["preferredName"], user["firstName"]) == (None, "Amara")
    assert client.patch(ME, json={"preferredName": ""}).json()["user"]["preferredName"] is None


def test_update_name_and_email(client, new_student):
    response = client.patch(ME, json={"fullName": "  Ada   Grace  Lovelace ", "email": " ADA.Lovelace@pac.edu "})
    assert response.status_code == 200
    user = response.json()["user"]
    assert (user["fullName"], user["firstName"], user["initials"], user["email"]) == (
        "Ada Grace Lovelace", "Ada Grace", "AL", "ada.lovelace@pac.edu")
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.user_id == new_student.user_id).one()
        assert (student.name, student.email) == ("Ada Grace Lovelace", "ada.lovelace@pac.edu")
    assert login(client, "ada.lovelace@pac.edu").status_code == 200


def test_profile_validation(client, new_student):
    error = assert_envelope(client.patch(ME, json={"email": "Sarah.Smith@pac.edu"}), 409, "EMAIL_TAKEN")
    assert error["message"] == "An account with this email already exists."
    assert_envelope(client.patch(ME, json={"fullName": "   "}), 422, "VALIDATION_ERROR")
    assert_envelope(client.patch(ME, json={"fullName": None}), 422, "VALIDATION_ERROR")
    assert_envelope(client.patch(ME, json={"fullName": "x" * 121}), 422, "VALIDATION_ERROR")
    assert_envelope(client.patch(ME, json={"preferredName": "x" * 61}), 422, "VALIDATION_ERROR")
    assert_envelope(client.patch(ME, json={"email": "not-an-email"}), 422, "VALIDATION_ERROR")
    assert_envelope(client.patch(ME, json={"role": "admin"}), 422, "VALIDATION_ERROR")


# --- PATCH /users/me/preferences --------------------------------------------------------------------------------

def test_partial_preferences_merge_and_persist(client, restore_amara):
    login(client, AMARA)
    response = client.patch(PREFS, json={"notify": {"sms": True}, "aiStyle": "Detailed"})
    assert response.status_code == 200
    prefs = response.json()["preferences"]
    assert prefs["notify"] == {"deadlines": True, "messages": True, "suggestions": True, "weeklySummary": False, "sms": True}
    assert (prefs["aiStyle"], prefs["reminderTiming"], prefs["classTime"]) == ("Detailed", "2 days before", "Evening")
    assert client.get(ME).json()["preferences"] == prefs
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter(AuditEvent.action == "prefs.update").order_by(AuditEvent.id.desc()).first()
        assert event.actor_id == 1 and event.changes is None


def test_whole_preferences_object_round_trips(client, restore_amara):
    """The settings screen sends back everything it loaded, graduationOptions included."""
    login(client, AMARA)
    prefs = client.get(ME).json()["preferences"]
    prefs["reminderTiming"] = "1 week before"
    response = client.patch(PREFS, json=prefs)
    assert response.status_code == 200 and response.json()["preferences"] == prefs


def test_preferences_validation(client, new_student):
    for body in ({"theme": "dark"}, {"notify": {"push": True}}, {"reminderTiming": "1 hour before"},
                 {"aiStyle": "Chatty"}, {"targetGraduation": "May 2031"}, {"ai": {"useGrades": "sometimes"}}):
        assert_envelope(client.patch(PREFS, json=body), 422, "VALIDATION_ERROR")


def test_target_graduation_updates_expected_graduation(client, restore_amara):
    login(client, AMARA)
    prefs = client.patch(PREFS, json={"targetGraduation": "August 2027"}).json()["preferences"]
    assert prefs["targetGraduation"] == "August 2027"
    assert client.get(ME).json()["profile"]["expectedGraduation"] == "August 2027"
    with SessionLocal() as db:
        assert db.get(Student, 101).expected_graduation == "August 2027"
    assert client.get("/api/v1/students/me/ai/context").json()["goal"] == "Graduate August 2027"


def test_ai_switches_change_what_the_ai_uses(client, restore_amara):
    login(client, AMARA)
    assert "Grades" in client.get("/api/v1/students/me/ai/context").json()["sources"]
    client.patch(PREFS, json={"ai": {"useGrades": False, "dashboardSuggestions": False}})
    assert "Grades" not in client.get("/api/v1/students/me/ai/context").json()["sources"]
    assert client.get("/api/v1/students/me/dashboard").json()["recommendation"] is None


# --- Google -----------------------------------------------------------------------------------------------------

def test_google_connect_is_off(client, new_student):
    error = assert_envelope(client.post(f"{ME}/google/connect"), 400, "GOOGLE_DISABLED")
    assert error["message"] == "Google sign-in isn't turned on for your school."


def test_google_disconnect(client, new_student):
    assert client.delete(f"{ME}/google").status_code == 204  # not linked: nothing to do
    with SessionLocal() as db:
        user = db.get(User, new_student.user_id)
        user.google_sub, user.password_hash = f"google-{user.user_id}", None
        db.commit()
    error = assert_envelope(client.delete(f"{ME}/google"), 409, "NO_PASSWORD")
    assert error["message"] == "Set a password first so you can still sign in."
    with SessionLocal() as db:
        user = db.get(User, new_student.user_id)
        user.password_hash = db.get(User, 1).password_hash
        db.commit()
    assert client.delete(f"{ME}/google").status_code == 204
    assert client.get(ME).json()["google"]["connected"] is False


# --- export -----------------------------------------------------------------------------------------------------

def test_export_contains_plan_threads_and_own_messages(client):
    login(client, AMARA)
    response = client.post(f"{ME}/export")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"exportedAt", "profile", "preferences", "enrollments", "plan", "assignments", "events",
                         "meetings", "conversations", "aiThreads"}
    assert data["profile"]["studentNumber"] == "S1002101"
    assert {item["code"] for item in data["plan"]} == {"CS 691", "CS 680"}
    assert any(thread["title"] == "Plan my Spring 2027 semester" and thread["messages"] for thread in data["aiThreads"])
    assert len(data["enrollments"]) == 10
    assert [(m["topic"], m["status"]) for m in data["meetings"]] == [
        ("Course planning", "completed"), ("Advising check-in", "confirmed"), ("Capstone topics", "requested")]
    texts = [message["text"] for conversation in data["conversations"] for message in conversation["messages"]]
    assert "Thank you! Could we go over capstone topics at our Oct 8 meeting?" in texts
    assert not any(text.startswith("Yes. Bring two or three ideas") for text in texts)  # the advisor's message


# --- delete account ---------------------------------------------------------------------------------------------

def test_delete_with_wrong_password(client, new_student):
    error = assert_envelope(client.request("DELETE", ME, json={"password": "wrong-password"}), 403, "INVALID_CREDENTIALS")
    assert error["message"] == "That password isn't right."
    assert_envelope(client.request("DELETE", ME, json={}), 403, "INVALID_CREDENTIALS")
    assert client.get(ME).status_code == 200


def test_delete_account(client, new_student):
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.user_id == new_student.user_id).one()
        student_id = student.student_id
        db.add(Enrollment(student_id=student_id, course_id=11, term="Fall 2025", status="completed", grade="A", grade_points=4))
        db.add(AiThread(student_id=student_id, title="Hello"))
        db.commit()
    client.patch(PREFS, json={"aiStyle": "Detailed"})

    response = client.request("DELETE", ME, json={"password": DEMO_PASSWORD})
    assert response.status_code == 204
    assert 'acadmate_session=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]
    assert_envelope(client.get("/api/v1/auth/me"), 401, "UNAUTHENTICATED")
    assert login(client, new_student.email).status_code == 401

    with SessionLocal() as db:
        user = db.get(User, new_student.user_id)
        assert (user.name, user.email, user.is_active, user.password_hash) == (
            "Deleted user", f"deleted-{user.user_id}@invalid", False, None)
        student = db.get(Student, student_id)
        assert (student.name, student.email) == ("Deleted user", f"deleted-{user.user_id}@invalid")
        assert db.query(Enrollment).filter(Enrollment.student_id == student_id).count() == 1  # school records stay
        assert db.query(AiThread).filter(AiThread.student_id == student_id).count() == 0
        assert db.get(UserPreference, user.user_id) is None
        assert db.query(AuditEvent).filter(AuditEvent.action == "user.self_delete", AuditEvent.actor_id == user.user_id).count() == 1


def test_delete_without_password_for_google_only_accounts(client, new_student):
    with SessionLocal() as db:
        user = db.get(User, new_student.user_id)
        user.google_sub, user.password_hash = f"google-only-{user.user_id}", None
        db.commit()
    assert client.get(ME).json()["profile"]["hasPassword"] is False
    assert client.request("DELETE", ME).status_code == 204


def test_admin_cannot_delete_self(client):
    login(client, JORDAN)
    error = assert_envelope(client.request("DELETE", ME, json={"password": DEMO_PASSWORD}), 403, "FORBIDDEN")
    assert error["message"] == "Admins can't delete their own account."
