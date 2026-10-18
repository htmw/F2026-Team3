"""Audit log (spec 36): /api/v1/admin/audit and /admin/audit.csv, link_for and prune. Seeded events are 1801-1812;
tests that add events tag their summaries with a unique token and search for it."""
import csv
import io
import uuid
from datetime import date, datetime, time, timedelta

import pytest

from conftest import login
from core.time import local_zone, now, today
from database import SessionLocal
from models import AuditEvent, User
from services import audit
from test_foundation import assert_envelope

AUDIT = "/api/v1/admin/audit"
JORDAN = "jordan.lee@pac.edu"
EVENT_KEYS = {"id", "eventId", "when", "at", "who", "role", "action", "key", "target", "ip", "result", "error",
              "changes", "link"}


@pytest.fixture
def admin(client):
    assert login(client, JORDAN).status_code == 200
    return client


def _record(n: int, token: str, role_user_id: int | None = 3) -> None:
    with SessionLocal() as db:
        actor = db.get(User, role_user_id) if role_user_id else None
        for i in range(n):
            audit.record(db, actor, "test.event", f"{token} event {i}")
        db.commit()


def test_audit_routes_need_an_admin(client, as_user):
    for path in (AUDIT, f"{AUDIT}.csv"):
        assert_envelope(client.get(path), 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for path in (AUDIT, f"{AUDIT}.csv"):
            assert_envelope(client.get(path), 403, "FORBIDDEN")


def test_list_shape_and_seeded_events(admin):
    events = admin.get(AUDIT, params={"q": "grade-based"}).json()["events"]
    assert len(events) == 1
    event = events[0]
    assert set(event) == EVENT_KEYS
    assert (event["eventId"], event["who"], event["role"], event["result"]) == ("evt_1807", "Jordan Lee", "Admin", "Success")
    assert event["changes"] == [{"field": "features.gradeInsights", "from": False, "to": True}]
    assert event["link"] == {"to": "/admin/ai", "label": "Open AI settings"}

    system = admin.get(AUDIT, params={"role": "System"}).json()["events"]
    assert {e["eventId"] for e in system} >= {"evt_1806", "evt_1812"}
    csv_import = next(e for e in system if e["eventId"] == "evt_1812")
    assert (csv_import["who"], csv_import["ip"], csv_import["when"]) == ("CSV import", None, "Today 06:00")

    ids = [e["id"] for e in admin.get(AUDIT).json()["events"]]
    assert ids == sorted(ids, reverse=True)


def test_filters_combine(admin):
    students = admin.get(AUDIT, params={"role": "Student"}).json()["events"]
    assert students and all(e["role"] == "Student" for e in students)

    for e in admin.get(AUDIT, params={"range": "today"}).json()["events"]:
        assert e["when"].startswith("Today")
    # Other tests add events today, so narrow by text: 1807 is 3 days old, 1801 is 9 days old.
    week = lambda q: [e["eventId"] for e in admin.get(AUDIT, params={"range": "7d", "q": q}).json()["events"]]  # noqa: E731
    assert week("grade-based insights") == ["evt_1807"] and week("Invited 12 students") == []

    # Other tests add catalog events today, so search for text only the seeded event has (8 days ago).
    catalog = admin.get(AUDIT, params={"q": "catalog"}).json()["events"]
    assert catalog and all("catalog" in f"{e['action']} {e['key']} {e['who']}".lower() for e in catalog)
    ids = lambda **filters: [e["eventId"] for e in admin.get(AUDIT, params={"q": "changed cs 650", **filters}).json()["events"]]  # noqa: E731
    assert ids() == ["evt_1802"]
    assert ids(role="Admin", range="30d") == ["evt_1802"]
    assert ids(role="Admin", range="7d") == [] and ids(role="Student") == []

    assert_envelope(admin.get(AUDIT, params={"role": "Bogus"}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.get(AUDIT, params={"range": "1y"}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.get(AUDIT, params={"cursor": "abc"}), 422, "VALIDATION_ERROR")


def test_search_treats_wildcards_literally(admin):
    assert admin.get(AUDIT, params={"q": "%"}).json()["events"] == []


def test_load_more_pages_without_duplicates(admin):
    token = f"page-{uuid.uuid4().hex[:8]}"
    _record(60, token)
    first = admin.get(AUDIT, params={"q": token}).json()
    assert len(first["events"]) == 50 and first["nextCursor"]
    second = admin.get(AUDIT, params={"q": token, "cursor": first["nextCursor"]}).json()
    assert len(second["events"]) == 10 and second["nextCursor"] is None
    ids = [e["id"] for e in first["events"] + second["events"]]
    assert len(set(ids)) == 60 and ids == sorted(ids, reverse=True)


def test_admin_action_shows_up_at_once(admin):
    admin.patch("/api/v1/admin/advisors/204", json={"capacity": 41})
    try:
        top = admin.get(AUDIT, params={"q": "advisor.update"}).json()["events"][0]
        assert top["key"] == "advisor.update" and top["link"] == {"to": "/admin/advisors?id=204", "label": "Open advisors"}
        assert top["changes"][0]["to"] == 41
    finally:
        admin.patch("/api/v1/admin/advisors/204", json={"capacity": 40})


def test_failed_login_is_listed_as_failed(admin, client):
    client.post("/api/v1/auth/login", json={"email": "amara.okafor@pac.edu", "password": "wrong-password"})
    login(client, JORDAN)
    failed = client.get(AUDIT, params={"q": "Failed sign-in", "range": "today"}).json()["events"]
    assert failed and failed[0]["result"] == "Failed" and failed[0]["error"] == "Wrong email or password"


def test_csv_export_respects_filters(admin):
    response = admin.get(f"{AUDIT}.csv", params={"role": "System"})
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="audit-{today().isoformat()}.csv"'
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["time", "actor", "role", "action", "target", "ip", "result", "event_id"]
    assert rows[1:] and all(row[2] == "System" for row in rows[1:])
    assert ["CSV import", "System", "Imported 1,284 grades from a CSV file", "import:grades", "", "success", "evt_1812"] \
        in [row[1:] for row in rows[1:]]
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter(AuditEvent.action == "report.export").order_by(AuditEvent.id.desc()).first()
        assert event.summary == "Exported the audit log" and event.target_id == "audit"


@pytest.mark.parametrize("target, action, link", [
    (("user", "12"), "user.update", {"to": "/admin/users?id=12", "label": "Open user"}),
    (None, "user.import", {"to": "/admin/users", "label": "Open users"}),
    (("advisor", "203"), "advisor.reassign", {"to": "/admin/advisors?id=203", "label": "Open advisors"}),
    (("integration", "mail"), "integration.connect", {"to": "/admin/integrations?id=mail", "label": "Open integrations"}),
    (("api_key", "4"), "api_key.create", {"to": "/admin/integrations", "label": "Open integrations"}),
    (("import", "grades"), "import.run", {"to": "/admin/integrations?id=csv", "label": "Open integrations"}),
    (("course", "CS 650"), "catalog.course.draft", {"to": "/admin/catalog?course=CS%20650", "label": "Open catalog"}),
    (("term", "5"), "catalog.term.draft", {"to": "/admin/catalog?tab=terms", "label": "Open catalog"}),
    (("program", "1"), "catalog.requirements.draft", {"to": "/admin/catalog?tab=requirements", "label": "Open catalog"}),
    (("settings", "ai"), "ai.settings", {"to": "/admin/ai", "label": "Open AI settings"}),
    (("ai_flag", "902"), "ai.flag.resolve", {"to": "/admin/ai#flags", "label": "Open AI settings"}),
    (("report", "overview"), "report.export", {"to": "/admin", "label": "Open overview"}),
    (("meeting", "1502"), "meeting.book", None),
    (None, "auth.logout", None),
])
def test_link_for(target, action, link):
    event = AuditEvent(action=action, target_type=target[0] if target else None, target_id=target[1] if target else None)
    assert audit.link_for(event) == link


def test_prune_keeps_a_year(db):
    old = AuditEvent(at=now() - timedelta(days=400), actor_label="Acadmate", actor_role="System", action="test.old",
                     summary="Old event", result="success")
    recent = AuditEvent(at=now() - timedelta(days=30), actor_label="Acadmate", actor_role="System", action="test.recent",
                        summary="Recent event", result="success")
    db.add_all([old, recent])
    db.commit()
    old_id, recent_id = old.id, recent.id
    assert audit.prune(db) >= 1
    db.expire_all()
    assert db.get(AuditEvent, old_id) is None and db.get(AuditEvent, recent_id) is not None
    db.delete(db.get(AuditEvent, recent_id))
    db.commit()


def test_when_label():
    def at(day, hour, minute):
        return datetime.combine(day, time(hour, minute), local_zone())

    assert audit.when_label(at(today(), 14, 2)) == "Today 14:02"
    assert audit.when_label(at(today() - timedelta(days=1), 17, 20)) == "Yesterday 17:20"
    assert audit.when_label(at(date(2026, 9, 28), 16, 10)) == "Sep 28 16:10"
    assert audit.when_label(at(date(2025, 9, 28), 16, 10)) == "Sep 28, 2025 16:10"
