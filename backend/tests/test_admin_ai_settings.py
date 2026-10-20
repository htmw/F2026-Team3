"""Admin AI settings and the test box (spec 34): /api/v1/admin/ai/settings and /admin/ai/test. Every test starts and
ends with no stored settings, so the rest of the suite sees the defaults. The flags endpoints are in test_admin_flags.py."""
import pytest

from conftest import login
from core.config import settings
from database import SessionLocal
from models import AiMessage, AiThread, AuditEvent, Student, SystemSetting
from services.ai import context
from services.ai import settings as ai_config
from test_foundation import assert_envelope

AI = "/api/v1/admin/ai"
JORDAN = "jordan.lee@pac.edu"
AMARA = "amara.okafor@pac.edu"
VISA = "Will dropping a course affect my visa?"


def _clear():
    with SessionLocal() as db:
        db.query(SystemSetting).filter(SystemSetting.key == "ai").delete()
        db.commit()


@pytest.fixture(autouse=True)
def stored_settings(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    _clear()
    yield
    _clear()


@pytest.fixture
def admin(client):
    """The signed-in admin. It is the same client as `client`, so tests sign back in after acting as Amara."""
    assert login(client, JORDAN).status_code == 200
    return client


def calls(client):
    return [
        client.get(f"{AI}/settings"),
        client.patch(f"{AI}/settings", json={"dailyLimit": 10}),
        client.post(f"{AI}/test", json={"question": "Hi", "studentId": 1}),
    ]


def test_settings_routes_need_an_admin(client, as_user):
    for response in calls(client):
        assert_envelope(response, 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for response in calls(client):
            assert_envelope(response, 403, "FORBIDDEN")


def test_get_returns_defaults(admin):
    assert admin.get(f"{AI}/settings").json() == {**ai_config.DEFAULTS, "claudeAvailable": False}


def test_patch_merges_dedupes_and_audits(admin):
    response = admin.patch(f"{AI}/settings", json={
        "dailyLimit": 10, "features": {"gradeInsights": False},
        "blockedTopics": ["Housing", " housing ", "Visa and immigration"]})
    assert response.status_code == 200
    body = response.json()
    assert body["dailyLimit"] == 10
    assert body["features"] == {**ai_config.DEFAULTS["features"], "gradeInsights": False}
    assert body["blockedTopics"] == ["Housing", "Visa and immigration"]
    assert admin.get(f"{AI}/settings").json() == body
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter(AuditEvent.action == "ai.settings").order_by(AuditEvent.id.desc()).first()
        assert event.changes["dailyLimit"] == [25, 10] and event.changes["features.gradeInsights"] == [True, False]


def test_patch_validation(admin):
    assert_envelope(admin.patch(f"{AI}/settings", json={"dailyLimit": 0}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.patch(f"{AI}/settings", json={"blockedTopics": [f"Topic {i}" for i in range(31)]}),
                    422, "VALIDATION_ERROR")
    assert_envelope(admin.patch(f"{AI}/settings", json={"style": "Chatty"}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.patch(f"{AI}/settings", json={"engine": None}), 422, "VALIDATION_ERROR")


def test_claude_needs_a_key(admin, monkeypatch):
    error = assert_envelope(admin.patch(f"{AI}/settings", json={"engine": "Claude"}), 400, "CLAUDE_UNAVAILABLE")
    assert error["message"] == "Claude isn't configured on this server."
    assert admin.patch(f"{AI}/settings", json={"engine": "Rules"}).json()["engine"] == "Rules"
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    body = admin.patch(f"{AI}/settings", json={"engine": "Claude"}).json()
    assert (body["engine"], body["claudeAvailable"]) == ("Claude", True)


def test_turning_the_advisor_off_reaches_students(admin, client):
    admin.patch(f"{AI}/settings", json={"features": {"advisor": False}})
    login(client, AMARA)
    assert client.get("/api/v1/students/me/ai/context").json()["enabled"] is False
    assert_envelope(client.post("/api/v1/students/me/ai/threads", json={"text": "Hi"}), 403, "AI_DISABLED")


def _counts():
    with SessionLocal() as db:
        return db.query(AiThread).count(), db.query(AiMessage).count()


def test_test_box_hands_off_blocked_topics_and_stores_nothing(admin):
    before = _counts()
    body = admin.post(f"{AI}/test", json={"question": VISA, "studentId": 1}).json()
    assert (body["engine"], body["advisorOn"], body["reply"]["kind"]) == ("Rules", True, "handoff")
    assert _counts() == before


def test_test_box_uses_unsaved_settings(admin):
    body = admin.post(f"{AI}/test", json={"question": "Am I on track to graduate?", "studentId": 1,
                                          "settings": {"features": {"advisor": False}, "blockedTopics": []}}).json()
    assert body["advisorOn"] is False and body["reply"]["kind"] == "answer" and body["reply"]["text"]
    # Without the visa topic blocked, the same question gets an engine answer instead of the handoff.
    body = admin.post(f"{AI}/test", json={"question": VISA, "studentId": 1, "settings": {"blockedTopics": ["Housing"]}}).json()
    assert body["reply"]["kind"] != "handoff"
    assert admin.get(f"{AI}/settings").json()["features"]["advisor"] is True  # nothing saved


def test_test_box_needs_a_student(admin):
    assert_envelope(admin.post(f"{AI}/test", json={"question": "Hi", "studentId": 3}), 404, "NOT_FOUND")
    assert_envelope(admin.post(f"{AI}/test", json={"question": "Hi", "studentId": 99999}), 404, "NOT_FOUND")
    assert_envelope(admin.post(f"{AI}/test", json={"question": "", "studentId": 1}), 422, "VALIDATION_ERROR")


def test_grades_source_off_hides_grades(db):
    student = db.query(Student).filter(Student.user_id == 1).one()
    cfg = ai_config.merge(ai_config.DEFAULTS, {"sources": {"grades": False}})
    ctx = context.build(db, student, cfg)
    assert ctx["sources"]["grades"] is False
    assert "Grades" not in [name for key, name in context.SOURCE_NAMES.items() if ctx["sources"].get(key)]


def test_grade_insights_off_hides_course_tips(admin, client):
    login(client, AMARA)
    cards = {card["code"]: card for card in client.get("/api/v1/students/me/courses").json()["current"]}
    assert cards["CS 661"]["insight"]
    login(admin, JORDAN)
    admin.patch(f"{AI}/settings", json={"features": {"gradeInsights": False}})
    login(client, AMARA)
    cards = client.get("/api/v1/students/me/courses").json()["current"]
    assert all(card["insight"] is None for card in cards)
