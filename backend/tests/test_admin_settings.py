"""Admin settings (spec 37): /api/v1/admin/settings, the settings consumers, retention and the demo reset."""
from datetime import timedelta

import pytest

from conftest import login
from core import time as clock
from core.config import settings as env
from core.time import now
from database import SessionLocal
from models import AiThread, AuditEvent, Student, SystemSetting, User, UserSession
from services import catalog, settings
from services.ai import retention
from test_foundation import assert_envelope

SETTINGS = "/api/v1/admin/settings"
RESET = "/api/v1/admin/demo/reset"
JORDAN = "jordan.lee@pac.edu"


@pytest.fixture(autouse=True)
def restore_defaults():
    yield
    with SessionLocal() as db:
        db.query(SystemSetting).filter(SystemSetting.key.in_(settings.KEYS)).delete(synchronize_session=False)
        db.commit()
    clock.set_zone(clock.DEFAULT_ZONE)


@pytest.fixture
def admin(client):
    assert login(client, JORDAN).status_code == 200
    return client


def _patch(client, body):
    return client.patch(SETTINGS, json=body)


def test_settings_routes_need_an_admin(client, as_user):
    calls = (("get", SETTINGS, None), ("patch", SETTINGS, {}), ("post", RESET, None))
    for method, path, body in calls:
        assert_envelope(client.request(method, path, json=body), 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for method, path, body in calls:
            assert_envelope(client.request(method, path, json=body), 403, "FORBIDDEN")


def test_get_returns_defaults_and_terms(admin):
    data = admin.get(SETTINGS).json()
    assert data["institution"] == {
        "name": "Pace University", "domain": "pac.edu", "supportEmail": "acadmate-help@pac.edu", "currentTermId": 4,
        "terms": [{"id": 3, "name": "Summer 2026"}, {"id": 4, "name": "Fall 2026"}, {"id": 5, "name": "Spring 2027"}],
        "timeZone": "Eastern", "selfSignup": True}
    assert data["security"] == {"google": True, "mfa": True, "ipLog": True, "timeout": "2 hours"}
    assert data["retention"] == {"ai": "1 year", "audit": "1 year"}
    assert data["branding"] == {"accent": "#0F766E"} and data["demoMode"] is False


def test_accent_change_is_saved_public_and_audited(admin, client):
    data = _patch(admin, {"branding": {"accent": "#1d4ed8"}}).json()
    assert data["branding"]["accent"] == "#1D4ED8" and data["institution"]["name"] == "Pace University"
    assert client.get("/api/v1/auth/config").json()["accent"] == "#1D4ED8"
    event = admin.get("/api/v1/admin/audit", params={"q": "settings.update"}).json()["events"][0]
    assert event["changes"] == [{"field": "branding.accent", "from": "#0F766E", "to": "#1D4ED8"}]
    assert event["link"] == {"to": "/admin/settings", "label": "Open settings"}
    # Saving the same value again changes nothing and writes no audit event.
    _patch(admin, {"branding": {"accent": "#1D4ED8"}})
    again = admin.get("/api/v1/admin/audit", params={"q": "settings.update"}).json()["events"][0]
    assert again["id"] == event["id"]


@pytest.mark.parametrize("body, field", [
    ({"branding": {"accent": "#123456"}}, "accent"),
    ({"security": {"timeout": "1 hour"}}, "timeout"),
    ({"retention": {"ai": "Forever"}}, "ai"),
    ({"institution": {"timeZone": "Mountain"}}, "timeZone"),
    ({"institution": {"domain": "not a domain"}}, "domain"),
    ({"institution": {"supportEmail": "help"}}, "supportEmail"),
    ({"institution": {"name": "  "}}, "name"),
    ({"institution": {"name": None}}, "name"),
    ({"institution": {"terms": []}}, "terms"),
    ({"demoMode": True}, "demoMode"),
])
def test_patch_validation(admin, body, field):
    error = assert_envelope(_patch(admin, body), 422, "VALIDATION_ERROR")
    assert any(detail["field"] == field for detail in error["details"])


def test_google_switch_hides_google_sign_in(admin, client, monkeypatch):
    monkeypatch.setattr(env, "GOOGLE_CLIENT_ID", "id")
    monkeypatch.setattr(env, "GOOGLE_CLIENT_SECRET", "secret")
    assert client.get("/api/v1/auth/config").json()["googleEnabled"] is True
    _patch(admin, {"security": {"google": False}})
    assert client.get("/api/v1/auth/config").json()["googleEnabled"] is False


def test_thirty_minute_timeout_signs_idle_sessions_out(admin, client):
    _patch(admin, {"security": {"timeout": "30 min"}})
    client.cookies.clear()
    assert login(client, "amara.okafor@pac.edu").status_code == 200
    with SessionLocal() as db:
        session = db.query(UserSession).filter(UserSession.user_id == 1).order_by(UserSession.id.desc()).first()
        assert session.expires_at - session.created_at <= timedelta(minutes=30, seconds=5)
        session.expires_at = now() - timedelta(minutes=1)  # idle for 31 minutes
        db.commit()
    assert_envelope(client.get("/api/v1/auth/me"), 401, "UNAUTHENTICATED")


def test_signup_uses_the_school_domain(admin, client):
    _patch(admin, {"institution": {"domain": "Example.edu"}})
    client.cookies.clear()
    response = client.post("/api/v1/auth/signup", json={"name": "Ana Diaz", "email": "ana.diaz@pac.edu", "password": "longenough"})
    error = assert_envelope(response, 422, "VALIDATION_ERROR")
    assert error["details"] == [{"field": "email", "message": "Use your school email (example.edu)."}]


def test_ip_log_off_stores_no_ip(admin):
    _patch(admin, {"security": {"ipLog": False}})
    _patch(admin, {"branding": {"accent": "#7C3AED"}})
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter(AuditEvent.action == "settings.update").order_by(AuditEvent.id.desc()).first()
        assert event.ip is None and "branding.accent" in event.changes


def test_time_zone_applies_app_wide(admin):
    assert _patch(admin, {"institution": {"timeZone": "Pacific"}}).json()["institution"]["timeZone"] == "Pacific"
    assert clock.local_zone().key == "America/Los_Angeles"
    _patch(admin, {"institution": {"timeZone": "Eastern"}})
    assert clock.local_zone().key == "America/New_York"


def test_current_term_override(admin):
    data = _patch(admin, {"institution": {"currentTermId": 5}}).json()
    assert data["institution"]["currentTermId"] == 5
    assert [t["id"] for t in data["institution"]["terms"]] == [4, 5, 6]
    with SessionLocal() as db:
        assert catalog.current_term(db).name == "Spring 2027"
    # Picking the term that contains today goes back to following the calendar.
    assert _patch(admin, {"institution": {"currentTermId": 4}}).json()["institution"]["currentTermId"] == 4
    with SessionLocal() as db:
        assert settings.get(db, "institution")["currentTermId"] is None
    error = assert_envelope(_patch(admin, {"institution": {"currentTermId": 999}}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "currentTermId"


def _thread(db, student_id: int, days_old: int) -> int:
    thread = AiThread(student_id=student_id, title="Retention test", created_at=now() - timedelta(days=days_old),
                      updated_at=now() - timedelta(days=days_old))
    db.add(thread)
    db.commit()
    return thread.id


def test_ai_retention(admin, make_user):
    with SessionLocal() as db:
        old, recent = _thread(db, 101, 40), _thread(db, 101, 5)
    _patch(admin, {"retention": {"ai": "30 days"}})
    with SessionLocal() as db:
        assert retention.prune_threads(db) >= 1
        assert db.get(AiThread, old) is None and db.get(AiThread, recent) is not None

    user = make_user("student")
    with SessionLocal() as db:
        student = Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1, expected_graduation="May 2025")
        db.add(student)
        db.commit()
        graduated = _thread(db, student.student_id, 1)
    _patch(admin, {"retention": {"ai": "Until graduation"}})
    with SessionLocal() as db:
        retention.prune_threads(db)
        assert db.get(AiThread, graduated) is None and db.get(AiThread, recent) is not None
        db.delete(db.get(AiThread, recent))
        db.commit()


def test_graduation_date():
    assert retention.graduation_date("May 2027").isoformat() == "2027-05-31"
    assert retention.graduation_date("December 2026").isoformat() == "2026-12-31"
    assert retention.graduation_date("Someday") is None and retention.graduation_date(None) is None


def test_demo_reset_is_404_outside_demo_mode(admin):
    assert_envelope(admin.post(RESET), 404, "NOT_FOUND")


def test_demo_reset_restores_the_seed_and_keeps_the_admin_signed_in(admin, make_user, monkeypatch):
    """Runs last in this file: it rebuilds the shared test database from the seed."""
    monkeypatch.setattr(env, "DEMO_MODE", True)
    throwaway = make_user("student")
    _patch(admin, {"branding": {"accent": "#B45309"}})
    response = admin.post(RESET)
    assert response.status_code == 202 and response.json() == {"message": "Demo data reset."}
    assert admin.get("/api/v1/auth/me").json()["user"]["email"] == JORDAN
    assert admin.get(SETTINGS).json()["branding"]["accent"] == "#0F766E"
    with SessionLocal() as db:
        assert db.get(User, throwaway.user_id) is None and db.get(User, 1).name == "Amara Okafor"
        event = db.query(AuditEvent).filter(AuditEvent.action == "demo.reset").one()
        assert event.actor_id == 3
