"""Advisor meetings (spec 24): agenda, requests, free slots, booking for an advisee, notes and office hours.
conftest pins today to Thu 2026-10-01; seed_advisor_meetings adds 1508-1513 to Dr. Smith's week."""
import pytest

from conftest import login
from database import SessionLocal
from models import AdvisorAvailability, AuditEvent, Meeting
from test_foundation import assert_envelope
from test_messages import restore_messages  # noqa: F401 (fixture: actions post notices)

PAGE = "/api/v1/advisor/meetings"
SLOTS = f"{PAGE}/free-slots"
HOURS = "/api/v1/advisor/office-hours"
SARAH_USER, LAST_SEEDED_MEETING = 2, 1513
FIELDS = ("starts_at", "ends_at", "status", "proposed_starts_at", "advisor_notes")


@pytest.fixture
def restore(restore_messages):  # noqa: F811
    """Puts Dr. Smith's meetings and office hours back as seeded (same ids: the schedule tests check them)."""
    with SessionLocal() as db:
        saved = {m.id: {f: getattr(m, f) for f in FIELDS} for m in db.query(Meeting).filter(Meeting.staff_user_id == SARAH_USER)}
        hours = [dict(id=w.id, staff_user_id=w.staff_user_id, weekday=w.weekday, start_time=w.start_time,
                      end_time=w.end_time, kind=w.kind, location=w.location)
                 for w in db.query(AdvisorAvailability).filter_by(staff_user_id=SARAH_USER, kind="office_hours")]
    yield
    with SessionLocal() as db:
        db.query(Meeting).filter(Meeting.id > LAST_SEEDED_MEETING).delete(synchronize_session=False)
        for meeting in db.query(Meeting).filter(Meeting.id.in_(saved)):
            for field, value in saved[meeting.id].items():
                setattr(meeting, field, value)
        db.query(AdvisorAvailability).filter_by(staff_user_id=SARAH_USER, kind="office_hours").delete()
        db.add_all(AdvisorAvailability(**row) for row in hours)
        db.commit()


def _times(rows):
    return [(r["day"], r["time"], r["who"]) for r in rows]


def test_access(client, as_user):
    assert_envelope(client.get(PAGE), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(PAGE), 403, "FORBIDDEN")
    as_user("advisor")
    assert_envelope(client.get(f"{PAGE}?range=month"), 422, "VALIDATION_ERROR")


def test_agenda_and_requests(client, as_user):
    as_user("advisor")
    data = client.get(PAGE).json()
    assert _times(data["agenda"]) == [("Today", "10:00", "Drop-in office hours"), ("Today", "11:00", "Jonah W."),
                                      ("Today", "13:00", "Priya S."), ("Today", "15:00", "Amara O.")]
    office, jonah = data["agenda"][0], data["agenda"][1]
    assert (office["kind"], office["topic"], office["location"]) == ("office_hours", "Open to all advisees",
                                                                     "Room 4.12, Science Hall")
    assert (jonah["kind"], jonah["format"], jonah["status"], jonah["studentId"]) == ("meeting", "In person", "confirmed", 113)
    assert data["agenda"][2]["videoUrl"] == "https://meet.example.edu/1509"

    week = client.get(f"{PAGE}?range=week").json()["agenda"]
    assert ("Mon, Oct 5", "11:00", "Daniel O.") in _times(week) and ("Wed, Oct 7", "16:00", "Marcus T.") in _times(week)
    assert all(r["status"] != "requested" for r in week)  # requests have their own list

    assert [(r["id"], r["who"], r["when"]) for r in data["requests"]] == [
        (1512, "Lina H.", "Tue, Oct 6 · 16:00"), (1502, "Amara O.", "Thu, Oct 8 · 15:00"),
        (1513, "Jonah W.", "Fri, Oct 9 · 10:00"), (1507, "Kofi M.", "Fri, Oct 9 · 14:00")]
    assert data["requests"][0]["topic"] == "Capstone prerequisite question · Online"
    assert data["officeHours"] == {"days": ["Thu"], "start": "10:00", "end": "11:00",
                                   "location": "Room 4.12, Science Hall", "summary": "Thu · 10:00–11:00"}


def test_accept_moves_request_to_agenda(client, restore):
    login(client, "sarah.smith@pac.edu")
    assert client.post("/api/v1/meetings/1512/accept").json()["status"] == "confirmed"
    data = client.get(f"{PAGE}?range=week").json()
    assert 1512 in [r["id"] for r in data["agenda"]] and 1512 not in [r["id"] for r in data["requests"]]

    login(client, "lina.haddad@pac.edu")
    system = next(c for c in client.get("/api/v1/conversations").json()["conversations"] if c["kind"] == "system")
    texts = [m["text"] for m in client.get(f"/api/v1/conversations/{system['id']}/messages").json()["messages"]]
    assert any(t.startswith("Dr. Sarah Smith confirmed your meeting on Tue, Oct 6 at 16:00") for t in texts)


def test_free_slots_and_propose(client, restore):
    login(client, "sarah.smith@pac.edu")
    times = [s["time"] for s in client.get(f"{SLOTS}?date=2026-10-06&studentId=109").json()["slots"]]
    assert "16:00" not in times and "09:00" in times  # Lina's own request holds 16:00
    moving = [s["time"] for s in client.get(f"{SLOTS}?date=2026-10-06&studentId=109&meetingId=1512").json()["slots"]]
    assert "16:00" in moving and len(moving) == 16
    # Amara's Thursday: her CS 675 class, the drop-in office hours and her own request at 15:00.
    thursday = [s["time"] for s in client.get(f"{SLOTS}?date=2026-10-08&studentId=101").json()["slots"]]
    assert not {"10:00", "10:30", "15:00"} & set(thursday) and "09:00" in thursday
    assert client.get(f"{SLOTS}?date=2026-10-10&studentId=109").json() == {"slots": []}  # Saturday
    assert_envelope(client.get(f"{SLOTS}?date=2026-12-01&studentId=109"), 400, "BAD_REQUEST")  # beyond the window
    assert_envelope(client.get(f"{SLOTS}?date=2026-10-06&studentId=105"), 403, "FORBIDDEN")  # Prof. Kim's advisee

    start = next(s for s in client.get(f"{SLOTS}?date=2026-10-09&studentId=113&meetingId=1513").json()["slots"]
                 if s["time"] == "13:00")["startsAt"]
    row = client.post("/api/v1/meetings/1513/propose", json={"startsAt": start}).json()
    assert (row["status"], row["proposedStartsAt"]) == ("proposed", start)


def test_book_for_student(client, restore):
    login(client, "sarah.smith@pac.edu")
    body = {"studentId": 107, "startsAt": "2026-10-05T18:00:00Z", "format": "Online", "topic": "Plan follow-up"}
    response = client.post(PAGE, json=body)
    assert response.status_code == 201
    row = response.json()
    assert (row["status"], row["who"], row["day"], row["time"], row["format"]) == (
        "confirmed", "Priya S.", "Mon, Oct 5", "14:00", "Online")
    assert row["videoUrl"] == f"https://meet.example.edu/{row['id']}"
    assert_envelope(client.post(PAGE, json=body), 409, "SLOT_TAKEN")
    assert_envelope(client.post(PAGE, json={**body, "studentId": 105}), 403, "FORBIDDEN")
    assert_envelope(client.post(PAGE, json={**body, "startsAt": "2026-10-05T18:10:00Z"}), 400, "BAD_REQUEST")
    assert_envelope(client.post(PAGE, json={**body, "topic": ""}), 422, "VALIDATION_ERROR")

    login(client, "priya.shah@pac.edu")
    mine = client.get("/api/v1/students/me/meetings").json()["meetings"]
    assert any(m["id"] == row["id"] and m["status"] == "confirmed" for m in mine)


def test_notes_are_private(client, restore):
    login(client, "sarah.smith@pac.edu")
    secret = "Prefers evening slots; follow up on the capstone form."
    row = client.patch(f"{PAGE}/1501", json={"notes": secret}).json()
    assert row["notes"] == secret
    assert next(r for r in client.get(PAGE).json()["agenda"] if r["id"] == 1501)["notes"] == secret
    assert_envelope(client.patch(f"{PAGE}/9999", json={"notes": "x"}), 404, "NOT_FOUND")
    with SessionLocal() as db:
        audit = db.query(AuditEvent).filter_by(action="meeting.notes").order_by(AuditEvent.id.desc()).first()
        assert secret not in audit.summary

    login(client, "amara.okafor@pac.edu")
    for response in (client.get("/api/v1/students/me/meetings"), client.post("/api/v1/users/me/export"),
                     client.get("/api/v1/students/me/events")):
        assert secret not in response.text

    login(client, "daniel.kim@pac.edu")
    assert_envelope(client.patch(f"{PAGE}/1501", json={"notes": "x"}), 404, "NOT_FOUND")  # not his meeting


def test_office_hours(client, restore):
    login(client, "sarah.smith@pac.edu")
    response = client.put(HOURS, json={"days": ["Wed", "Thu"], "start": "16:30", "end": "17:30"})
    assert response.json()["officeHours"] == {"days": ["Wed", "Thu"], "start": "16:30", "end": "17:30",
                                              "location": "Room 4.12, Science Hall", "summary": "Wed, Thu · 16:30–17:30"}
    error = assert_envelope(client.put(HOURS, json={"days": ["Mon"], "start": "17:00", "end": "16:00"}), 422,
                            "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "end"
    assert_envelope(client.put(HOURS, json={"days": ["Sat"], "start": "16:00", "end": "17:00"}), 422, "VALIDATION_ERROR")
    with SessionLocal() as db:
        audit = db.query(AuditEvent).filter_by(action="office_hours.update").order_by(AuditEvent.id.desc()).first()
        assert audit.changes["days"] == [["Thu"], ["Wed", "Thu"]]

    today_rows = client.get("/api/v1/advisor/dashboard").json()["today"]["meetings"]
    assert ("16:30", "Drop-in office hours") in [(m["time"], m["who"]) for m in today_rows]
    assert ("10:00", "Drop-in office hours") not in [(m["time"], m["who"]) for m in today_rows]

    login(client, "amara.okafor@pac.edu")
    week = client.get("/api/v1/students/me/events").json()
    thursday = next(day for day in week["days"] if day["name"] == "Thu")
    assert [(e["start"], e["title"]) for e in thursday["events"] if e["id"].startswith("aoh-")] == [
        ("16:30", "Advisor office hours")]

    login(client, "sarah.smith@pac.edu")
    assert client.put(HOURS, json={"days": [], "start": "16:30", "end": "17:30"}).json()["officeHours"]["summary"] == \
        "No office hours set"
