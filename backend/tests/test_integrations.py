"""Admin integrations (spec 35): CSV imports, SMTP, calendar connect, API keys and the key-authenticated report.
Tests that change an integration put it back as seeded; imports use throwaway students and course codes."""
import smtplib
import uuid

import httpx
import pytest

from conftest import login
from core.config import settings
from database import SessionLocal
from models import AuditEvent, Course, Enrollment, GradeItem, Integration, IntegrationEvent, Student
from services import mailer
from test_foundation import assert_envelope

ADMIN = "/api/v1/admin"
JORDAN = "jordan.lee@pac.edu"
SMTP = {"host": "smtp.example.edu", "port": 587, "username": "acadmate", "password": "s3cret!", "from": "noreply@pac.edu"}


@pytest.fixture
def admin(client):
    assert login(client, JORDAN).status_code == 200
    return client


@pytest.fixture(autouse=True)
def restore_integrations():
    yield
    with SessionLocal() as db:
        for row in db.query(Integration):
            row.enabled, row.config, row.last_error = row.id == "csv", {}, None
        db.commit()
    mailer.configure(None)


@pytest.fixture
def smtp_ok(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "_smtp_send", lambda cfg, to, subject, text: sent.append((cfg, to, subject)))
    return sent


def _audited(action: str) -> bool:
    with SessionLocal() as db:
        return db.query(AuditEvent).filter(AuditEvent.action == action).count() > 0


def calls(client):
    return [
        client.get(f"{ADMIN}/integrations"),
        client.post(f"{ADMIN}/integrations/csv/connect"),
        client.get(f"{ADMIN}/integrations/gcal/callback?code=x&state=y"),
        client.post(f"{ADMIN}/integrations/csv/disconnect"),
        client.post(f"{ADMIN}/integrations/csv/sync"),
        client.post(f"{ADMIN}/imports?type=courses", content="code,name,credits,type,description\n",
                    headers={"Content-Type": "text/csv"}),
        client.get(f"{ADMIN}/api-keys"),
        client.post(f"{ADMIN}/api-keys", json={"name": "X"}),
        client.delete(f"{ADMIN}/api-keys/1"),
    ]


def test_integration_routes_need_an_admin(client, as_user):
    for response in calls(client) + [client.get(f"{ADMIN}/reports/overview.csv")]:
        assert_envelope(response, 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for response in calls(client):
            assert_envelope(response, 403, "FORBIDDEN")


def test_report_needs_an_admin_or_a_key(client):
    """reports_access reads the session cookie itself (a key must not need one), so sign in for real."""
    login(client, "amara.okafor@pac.edu")
    assert_envelope(client.get(f"{ADMIN}/reports/overview.csv"), 403, "FORBIDDEN")


def test_list_shape(admin):
    rows = {row["id"]: row for row in admin.get(f"{ADMIN}/integrations").json()["integrations"]}
    assert list(rows) == ["csv", "mail", "gcal", "outlook"]
    assert (rows["csv"]["status"], rows["csv"]["sync"]) == ("Connected", "Last import today 06:00")
    assert rows["csv"]["log"][0] == {"a": "Imported 1,284 grades", "b": "Today 06:00"}
    for key in ("mail", "gcal", "outlook"):
        assert (rows[key]["status"], rows[key]["sync"]) == ("Off", "Not connected")
    assert rows["gcal"]["log"] == [{"a": "Never connected", "b": "—"}]


# --- email ----------------------------------------------------------------------------------------------------------

def test_smtp_failure_reports_the_server_message(admin, monkeypatch):
    def refuse(cfg, to, subject, text):
        raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    monkeypatch.setattr(mailer, "_smtp_send", refuse)
    error = assert_envelope(admin.post(f"{ADMIN}/integrations/mail/connect", json=SMTP), 400, "SMTP_FAILED")
    assert "Username and Password not accepted" in error["message"]
    rows = {row["id"]: row for row in admin.get(f"{ADMIN}/integrations").json()["integrations"]}
    assert rows["mail"]["status"] == "Off"


def test_smtp_connect_encrypts_the_password_and_sends_through_it(admin, smtp_ok):
    body = admin.post(f"{ADMIN}/integrations/mail/connect", json=SMTP).json()
    assert body["status"] == "Connected" and body["config"]["host"] == "smtp.example.edu"
    assert "password" not in body["config"]
    assert smtp_ok[0][1] == JORDAN  # the test email went to the admin
    with SessionLocal() as db:
        stored = db.get(Integration, "mail").config["password"]
    assert stored and stored != SMTP["password"]

    mailer.send("someone@pac.edu", "Hello", "Body")
    assert smtp_ok[-1][0]["password"] == SMTP["password"] and smtp_ok[-1][1] == "someone@pac.edu"
    assert _audited("integration.connect")

    body = admin.post(f"{ADMIN}/integrations/mail/disconnect").json()
    assert body["status"] == "Off" and _audited("integration.disconnect")
    count = len(smtp_ok)
    mailer.send("someone@pac.edu", "Hello", "Body")  # back to the log
    assert len(smtp_ok) == count


def test_mail_connect_needs_settings(admin):
    assert_envelope(admin.post(f"{ADMIN}/integrations/mail/connect"), 422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{ADMIN}/integrations/mail/connect", json={**SMTP, "port": 0}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{ADMIN}/integrations/nope/connect"), 404, "NOT_FOUND")


# --- calendars ------------------------------------------------------------------------------------------------------

def test_calendar_without_provider_settings(admin, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    error = assert_envelope(admin.post(f"{ADMIN}/integrations/gcal/connect"), 400, "PROVIDER_NOT_CONFIGURED")
    assert error["message"] == "Google Calendar isn't configured on this server."


def test_calendar_oauth_round_trip(admin, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-123")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "secret")
    url = admin.post(f"{ADMIN}/integrations/gcal/connect").json()["url"]
    assert url.startswith("https://accounts.google.com/") and "client_id=client-123" in url
    state = httpx.URL(url).params["state"]

    assert_envelope(admin.get(f"{ADMIN}/integrations/gcal/callback", params={"code": "c", "state": "wrong"}),
                    400, "BAD_REQUEST")
    response_json = {"access_token": "a", "refresh_token": "refresh-xyz"}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, json=response_json, request=httpx.Request("POST", a[0])))
    response = admin.get(f"{ADMIN}/integrations/gcal/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].endswith("/admin/integrations?id=gcal")
    rows = {row["id"]: row for row in admin.get(f"{ADMIN}/integrations").json()["integrations"]}
    assert rows["gcal"]["status"] == "Connected"
    with SessionLocal() as db:
        assert db.get(Integration, "gcal").config["refreshToken"] != "refresh-xyz"


# --- CSV imports ----------------------------------------------------------------------------------------------------

def _import(client, kind: str, text: str):
    return client.post(f"{ADMIN}/imports", params={"type": kind}, content=text, headers={"Content-Type": "text/csv"})


def test_course_import_upserts_and_skips_bad_rows(admin):
    code = f"ZZ {uuid.uuid4().int % 900 + 100}"
    body = _import(admin, "courses", f"code,name,credits,type,description\n{code},Imported Topics,3,core,\n"
                                     f"ZZ-99,Bad,3,Elective,\n").json()
    assert (body["created"], body["updated"]) == (1, 0)
    assert body["skipped"] == [{"line": 3, "reason": 'Course code "ZZ-99" should look like "CS 612"'}]
    body = _import(admin, "courses", f"code,name,credits,type,description\n{code},Renamed,4,,\n").json()
    assert (body["created"], body["updated"], body["message"]) == (0, 1, "Imported 1 courses")
    with SessionLocal() as db:
        course = db.query(Course).filter(Course.course_code == code).one()
        assert (course.course_name, float(course.credits), course.type) == ("Renamed", 4.0, "Elective")
    assert _audited("import.run")


def test_enrollment_and_grade_imports_update_the_gpa(admin, make_user):
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        db.commit()
    email = user.email
    body = _import(admin, "enrollments", f"student_email,course_code,term,status\n{email},CS 600,Spring 2027,in_progress\n"
                                         f"{email},CS 999,Spring 2027,in_progress\n").json()
    assert body["created"] == 1 and body["skipped"][0]["reason"] == "Unknown course CS 999"

    body = _import(admin, "grades", f"student_email,course_code,term,component,weight,score\n"
                                    f"{email},CS 600,Spring 2027,Midterm,30,88\n").json()
    assert body["created"] == 1

    body = _import(admin, "grades", f"student_email,course_code,term,grade,grade_points\n"
                                    f"{email},CS 501,Fall 2025,A-,\n{email},CS 510,Fall 2025,B,\n").json()
    assert (body["created"], body["message"]) == (2, "Imported 2 grades")
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.user_id == user.user_id).one()
        rows = db.query(Enrollment).filter(Enrollment.student_id == student.student_id).all()
        completed = {r.term + r.grade: float(r.grade_points) for r in rows if r.status == "completed"}
        assert completed == {"Fall 2025A-": 3.7, "Fall 2025B": 3.0}
        current = next(r for r in rows if r.status == "in_progress")
        assert current.section_id == 507  # Spring 2027, so the throwaway student isn't anyone's classmate now
        item = db.query(GradeItem).filter(GradeItem.enrollment_id == current.enrollment_id).one()
        assert (item.label, float(item.score)) == ("Midterm", 88.0)
        assert db.query(IntegrationEvent).filter(IntegrationEvent.text == "Imported 2 grades").count() >= 1
    login(admin, email)
    assert admin.get("/api/v1/students/me/dashboard").json()["gpa"]["cumulative"] == 3.35


def test_import_errors(admin):
    assert_envelope(_import(admin, "grades", "email,grade\nx,A\n"), 400, "BAD_REQUEST")
    assert_envelope(_import(admin, "courses", "code,name,credits,type,description\n"), 400, "BAD_REQUEST")
    assert_envelope(_import(admin, "bogus", "a\n1\n"), 422, "VALIDATION_ERROR")
    admin.post(f"{ADMIN}/integrations/csv/disconnect")
    assert_envelope(_import(admin, "courses", "code,name,credits,type,description\nZZ 100,X,3,,\n"), 409, "CONFLICT")
    assert_envelope(admin.post(f"{ADMIN}/integrations/csv/sync"), 409, "CONFLICT")


def test_csv_sync_reruns_the_latest_import(admin):
    code = f"ZY {uuid.uuid4().int % 900 + 100}"
    _import(admin, "courses", f"code,name,credits,type,description\n{code},Sync Topics,3,,\n")
    body = admin.post(f"{ADMIN}/integrations/csv/sync").json()
    assert body["log"][0]["a"] == "Imported 1 courses" and _audited("integration.sync")


# --- API keys -------------------------------------------------------------------------------------------------------

def test_api_key_lifecycle(admin, client):
    created = admin.post(f"{ADMIN}/api-keys", json={"name": "Nightly export"})
    assert created.status_code == 201
    key = created.json()
    assert key["key"].startswith("acm_") and len(key["key"]) == 36 and key["mask"] == f"acm_••••••••{key['key'][-4:]}"
    listed = admin.get(f"{ADMIN}/api-keys").json()["keys"]
    row = next(k for k in listed if k["id"] == key["id"])
    assert "key" not in row and row["mask"] == key["mask"] and row["lastUsedAt"] is None

    assert admin.get(f"{ADMIN}/reports/overview.csv").status_code == 200  # admin session, no header
    admin.post("/api/v1/auth/logout")
    response = client.get(f"{ADMIN}/reports/overview.csv", headers={"Authorization": f"Bearer {key['key']}"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert_envelope(client.get(f"{ADMIN}/reports/overview.csv", headers={"Authorization": "Bearer acm_nope"}),
                    401, "UNAUTHENTICATED")

    login(client, JORDAN)
    assert next(k for k in client.get(f"{ADMIN}/api-keys").json()["keys"] if k["id"] == key["id"])["lastUsedAt"]
    assert client.delete(f"{ADMIN}/api-keys/{key['id']}").status_code == 204
    assert_envelope(client.delete(f"{ADMIN}/api-keys/{key['id']}"), 404, "NOT_FOUND")
    assert all(k["id"] != key["id"] for k in client.get(f"{ADMIN}/api-keys").json()["keys"])
    assert_envelope(client.get(f"{ADMIN}/reports/overview.csv", headers={"Authorization": f"Bearer {key['key']}"}),
                    401, "UNAUTHENTICATED")
    assert _audited("api_key.create") and _audited("api_key.revoke")


def test_api_key_validation(admin):
    assert_envelope(admin.post(f"{ADMIN}/api-keys", json={"name": ""}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{ADMIN}/api-keys", json={"name": "X", "scope": "users:write"}), 422, "VALIDATION_ERROR")
