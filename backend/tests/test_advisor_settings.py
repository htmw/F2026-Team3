"""Advisor settings (spec 27): profile fields, switches and the per-staff booking rules they drive (spec 18)."""
from datetime import datetime

import pytest

from conftest import login
from database import SessionLocal
from models import Advisor, ApprovalRequest, AuditEvent, Meeting, User, UserPreference
from services import approvals
from test_foundation import assert_envelope
from test_messages import restore_messages  # noqa: F401 (fixture)

SETTINGS = "/api/v1/advisor/settings"
SARAH, AMARA = "sarah.smith@pac.edu", "amara.okafor@pac.edu"
NEXT_WEEK, LAST_SEEDED_MEETING = "2026-10-05", 1513


@pytest.fixture
def restore(restore_messages):  # noqa: F811
    """Puts back Dr. Smith's preferences, title and office, new meetings and the requests' reminder stamps."""
    with SessionLocal() as db:
        row = db.get(UserPreference, 2)
        saved = dict(row.data) if row and row.data else None
        user, advisor = db.get(User, 2), db.get(Advisor, 201)
        title, office = user.title, advisor.office
    yield
    with SessionLocal() as db:
        row = db.get(UserPreference, 2)
        if saved is None and row is not None:
            db.delete(row)
        elif row is not None:
            row.data = saved
        db.get(User, 2).title, db.get(Advisor, 201).office = title, office
        db.query(Meeting).filter(Meeting.id > LAST_SEEDED_MEETING).delete(synchronize_session=False)
        for request in db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending"):
            if request.payload and "remindedAt" in request.payload:
                request.payload = {k: v for k, v in request.payload.items() if k != "remindedAt"}
        db.commit()


def patch(client, body):
    return client.patch(SETTINGS, json=body)


def test_access(client, as_user):
    assert_envelope(client.get(SETTINGS), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(SETTINGS), 403, "FORBIDDEN")


def test_defaults(client):
    login(client, SARAH)
    assert client.get(SETTINGS).json() == {
        "profile": {"fullName": "Dr. Sarah Smith", "email": "sarah.smith@pac.edu", "initials": "SS"},
        "advisor": {"title": "Faculty advisor, Computer Science", "department": "Computer Science",
                    "office": "Science Hall, Room 4.12", "meetingLength": 30, "bookingWindow": "2 weeks ahead",
                    "autoConfirm": False},
        "notify": {"newApproval": True, "booking": True, "messages": True, "weeklyDigest": False},
        "approvals": {"precheck": True, "remindAfter3Days": True},
    }


def test_validation(client):
    login(client, SARAH)
    for body in ({"meetingLength": 20}, {"bookingWindow": "3 weeks ahead"}, {"colour": "red"}, {"title": "x" * 101},
                 {"notify": {"sms": True}}):
        assert_envelope(patch(client, body), 422, "VALIDATION_ERROR")


def test_update_and_audit(client, restore):
    login(client, SARAH)
    data = patch(client, {"title": "Senior advisor", "office": " Science Hall, Room 5.01 ",
                          "notify": {"weeklyDigest": True}, "approvals": {"remindAfter3Days": False}}).json()
    assert (data["advisor"]["title"], data["advisor"]["office"]) == ("Senior advisor", "Science Hall, Room 5.01")
    assert data["notify"]["weeklyDigest"] is True and data["notify"]["booking"] is True
    assert data["approvals"] == {"precheck": True, "remindAfter3Days": False}
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter_by(action="advisor.settings").order_by(AuditEvent.id.desc()).first()
        assert event.changes["title"] == ["Faculty advisor, Computer Science", "Senior advisor"]
    assert client.get(SETTINGS).json() == data


def test_meeting_length_changes_slots(client, restore):
    login(client, SARAH)
    assert patch(client, {"meetingLength": 45}).json()["advisor"]["meetingLength"] == 45
    login(client, AMARA)
    staff = next(s for s in client.get("/api/v1/staff").json()["staff"] if s["id"] == 2)
    assert staff["meetingLength"] == 45
    monday = client.get(f"/api/v1/staff/2/availability?week={NEXT_WEEK}").json()["days"][0]
    assert [s["time"] for s in monday["slots"]][:4] == ["09:00", "09:45", "10:30", "11:15"]
    free = next(s for s in monday["slots"] if not s["taken"])
    booked = client.post("/api/v1/meetings", json={"staffId": 2, "startsAt": free["startsAt"], "format": "Online",
                                                   "topic": "Capstone topics"})
    assert booked.status_code == 201
    with SessionLocal() as db:
        meeting = db.get(Meeting, booked.json()["id"])
        assert (meeting.ends_at - meeting.starts_at).total_seconds() == 45 * 60


def test_booking_window_and_auto_confirm(client, restore):
    login(client, SARAH)
    patch(client, {"bookingWindow": "1 week ahead", "autoConfirm": True})
    login(client, AMARA)
    staff = next(s for s in client.get("/api/v1/staff").json()["staff"] if s["id"] == 2)
    assert staff["bookingWindowWeeks"] == 1
    assert_envelope(client.get(f"/api/v1/staff/2/availability?week={NEXT_WEEK}"), 400, "BAD_REQUEST")

    login(client, SARAH)
    patch(client, {"bookingWindow": "4 weeks ahead"})
    login(client, AMARA)
    slots = client.get(f"/api/v1/staff/2/availability?week={NEXT_WEEK}").json()["days"][1]["slots"]
    free = next(s for s in slots if not s["taken"])
    booked = client.post("/api/v1/meetings", json={"staffId": 2, "startsAt": free["startsAt"], "format": "Online",
                                                   "topic": "Capstone topics"})
    assert booked.json()["status"] == "confirmed"
    assert client.get("/api/v1/staff/2/availability?week=2026-10-19").status_code == 200  # week 4 is open now


def test_booking_notice_switch(client, restore):
    login(client, SARAH)
    patch(client, {"notify": {"booking": False}})

    def notices() -> int:
        login(client, SARAH)
        return client.get("/api/v1/users/me/badges").json()["badges"]["messages"]

    before = notices()
    login(client, AMARA)
    slots = client.get(f"/api/v1/staff/2/availability?week={NEXT_WEEK}").json()["days"][1]["slots"]
    free = next(s for s in slots if not s["taken"])
    client.post("/api/v1/meetings", json={"staffId": 2, "startsAt": free["startsAt"], "format": "Online",
                                          "topic": "Capstone topics"})
    assert notices() == before


def test_precheck_switch(client, restore):
    login(client, SARAH)
    assert client.get("/api/v1/advisor/dashboard").json()["prechecks"] is True
    patch(client, {"approvals": {"precheck": False}})
    assert client.get("/api/v1/advisor/dashboard").json()["prechecks"] is False
    assert client.get("/api/v1/advisor/approvals").json()["prechecks"] is False


def test_stale_request_reminders(client, restore):
    def smith_notices(db) -> list[str]:
        login(client, SARAH)
        rows = client.get("/api/v1/conversations").json()["conversations"]
        system = next(c for c in rows if c["kind"] == "system")
        return [m["text"] for m in client.get(f"/api/v1/conversations/{system['id']}/messages").json()["messages"]]

    with SessionLocal() as db:
        assert approvals.remind_stale(db) >= 1  # Priya's plan (6 days) and Daniel's form (3 days) for Dr. Smith
    with SessionLocal() as db:
        texts = smith_notices(db)
        assert any("waited more than 3 days" in t and "Spring 2027 plan · Capstone + 2 electives" in t for t in texts)
        stamped = db.get(ApprovalRequest, 1706).payload["remindedAt"]
        assert datetime.fromisoformat(stamped.replace("Z", "+00:00"))
        assert approvals.remind_stale(db) == 0  # each request is reminded once

    # Turned off: no notice for a request that crosses 3 days later.
    login(client, SARAH)
    patch(client, {"approvals": {"remindAfter3Days": False}})
    with SessionLocal() as db:
        request = db.get(ApprovalRequest, 1709)
        created = request.created_at
        request.payload = {k: v for k, v in request.payload.items() if k != "remindedAt"}
        request.created_at = created.replace(year=2026, month=9, day=20)
        db.commit()
    try:
        with SessionLocal() as db:
            approvals.remind_stale(db)
            assert "remindedAt" not in (db.get(ApprovalRequest, 1709).payload or {})
    finally:
        with SessionLocal() as db:
            db.get(ApprovalRequest, 1709).created_at = created
            db.commit()
