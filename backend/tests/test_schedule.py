"""Schedule and calendar feeds (spec 14). conftest pins today to 2026-10-01 (Thu); the seeded week is Sep 28 - Oct 4."""
from copy import deepcopy

import pytest

from conftest import login
from database import SessionLocal
from models import Event, Student
from services.ai import settings as ai_config
from test_foundation import assert_envelope

BASE = "/api/v1/students/me"
AMARA = "amara.okafor@pac.edu"
STUDY = {"title": "Study · algorithms", "type": "Study", "date": "2026-10-05", "start": "18:00", "end": "19:30"}


def events_by_day(data):
    return {day["name"]: [(e["start"], e["title"], e["kind"]) for e in day["events"]] for day in data["days"]}


@pytest.fixture
def new_student(make_user):
    def create():
        user = make_user("student")
        with SessionLocal() as db:
            db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
            db.commit()
        return user
    return create


def test_default_week(client):
    login(client, AMARA)
    response = client.get(f"{BASE}/events")
    assert response.status_code == 200
    data = response.json()
    assert (data["from"], data["to"], data["today"]) == ("2026-09-28", "2026-10-04", "2026-10-01")
    assert [day["day"] for day in data["days"]] == [28, 29, 30, 1, 2, 3, 4]

    days = events_by_day(data)
    assert days["Mon"] == [("13:00", "Study · CS 675 labs", "personal"), ("16:00", "CS 608 office hours", "office"),
                           ("18:10", "CS 608 Algorithms & Computing Theory", "class")]
    assert days["Wed"] == [("14:00", "CS 675 office hours", "office"), ("18:00", "Study · CS 608", "personal")]
    assert days["Thu"] == [("10:00", "Advisor office hours", "office"),  # Dr. Smith's drop-in hours (spec 24)
                           ("10:00", "CS 675 Data Science", "class"), ("13:30", "Team project sync", "personal"),
                           ("15:00", "Advising check-in", "meeting"), ("17:00", "CS 661 office hours", "office"),
                           ("18:10", "CS 661 Python Programming", "class")]
    thursday = next(day for day in data["days"] if day["name"] == "Thu")
    office = thursday["events"][0]  # the advisor's drop-in hours (spec 24)
    assert (office["id"], office["editable"], office["location"]) == (
        "aoh-11-2026-10-01", False, "Room 4.12, Science Hall · Dr. Sarah Smith")
    cls = thursday["events"][1]
    assert cls["id"] == "cls-503-2026-10-01" and cls["editable"] is False and cls["location"] == "Room 1201"
    advising = thursday["events"][3]  # a booked meeting (spec 18)
    assert (advising["id"], advising["editable"], advising["type"], advising["status"], advising["location"]) == (
        "mtg-1501", False, "Advising", "confirmed", "Online · Dr. Sarah Smith")

    saturday = next(day for day in data["days"] if day["name"] == "Sat")
    assert saturday["due"] == ["CS 675 Project topic proposal"]
    assert [(d["title"], d["course"], d["label"], d["status"]) for d in data["deadlines"]] == [
        ("Project topic proposal", "CS 675", "Oct 3", "In progress"), ("Week 6 tutorial", "CS 661", "Oct 5", "In progress"),
        ("Problem set 4", "CS 608", "Oct 9", "To do")]  # open assignments due in the next two weeks (spec 15)
    assert data["suggestion"] == {
        "title": "Study · CS 675 Project topic proposal",
        "text": ("You have a free 2-hour window on Friday evening. Blocking it for Project topic proposal gives you "
                 "2 sessions before the Oct 3 deadline."),
        "date": "2026-10-02", "start": "17:30", "end": "19:30",
    }


def test_other_week_and_ranges(client):
    login(client, AMARA)
    data = client.get(f"{BASE}/events?from=2026-10-05&to=2026-10-11").json()
    days = events_by_day(data)
    assert days["Mon"] == [("16:00", "CS 608 office hours", "office"), ("18:10", "CS 608 Algorithms & Computing Theory", "class")]
    assert all(kind != "personal" for events in days.values() for _, _, kind in events)

    assert_envelope(client.get(f"{BASE}/events?from=2026-10-05&to=2026-10-01"), 422, "VALIDATION_ERROR")
    assert_envelope(client.get(f"{BASE}/events?from=2026-10-01&to=2026-12-01"), 422, "VALIDATION_ERROR")
    assert_envelope(client.get(f"{BASE}/events?from=2026-10-01"), 422, "VALIDATION_ERROR")
    assert_envelope(client.get(f"{BASE}/events?from=not-a-date&to=2026-10-01"), 422, "VALIDATION_ERROR")


def test_create_validation(client):
    login(client, AMARA)
    error = assert_envelope(client.post(f"{BASE}/events", json={**STUDY, "end": "17:00"}), 422, "VALIDATION_ERROR")
    assert error["details"] == [{"field": "end", "message": "End time must be after the start time."}]
    error = assert_envelope(client.post(f"{BASE}/events", json={**STUDY, "type": "Class"}), 422, "VALIDATION_ERROR")
    assert error["details"] == [{"field": "type", "message": "Classes come from your enrollments."}]
    error = assert_envelope(client.post(f"{BASE}/events", json={**STUDY, "title": "  "}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "title"


def test_create_update_delete(client, new_student):
    login(client, new_student().email)
    created = client.post(f"{BASE}/events", json={**STUDY, "location": "  ", "note": "Chapter 4"})
    assert created.status_code == 201
    event = created.json()
    assert event["id"].startswith("ev-") and event["kind"] == "personal" and event["location"] is None
    path = f"{BASE}/events/{event['id']}"

    updated = client.patch(path, json={"title": "Study · DP", "reminderMinutes": 30}).json()
    assert updated["title"] == "Study · DP" and updated["reminderMinutes"] == 30
    error = assert_envelope(client.patch(path, json={"start": "20:00"}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "end"
    assert_envelope(client.patch(path, json={"reminderMinutes": 5000}), 422, "VALIDATION_ERROR")

    week = client.get(f"{BASE}/events?from=2026-10-05&to=2026-10-11").json()
    assert [e["title"] for day in week["days"] for e in day["events"]] == ["Study · DP"]

    assert client.delete(path).status_code == 204
    assert_envelope(client.delete(path), 404, "NOT_FOUND")


def test_not_editable_or_not_own(client, new_student):
    login(client, AMARA)
    assert_envelope(client.patch(f"{BASE}/events/cls-503-2026-10-01", json={"title": "x"}), 403, "FORBIDDEN")
    assert_envelope(client.delete(f"{BASE}/events/off-501-2026-09-28"), 403, "FORBIDDEN")
    assert_envelope(client.patch(f"{BASE}/events/ev-999999", json={"title": "x"}), 404, "NOT_FOUND")
    assert_envelope(client.patch(f"{BASE}/events/nonsense", json={"title": "x"}), 404, "NOT_FOUND")

    login(client, new_student().email)
    assert_envelope(client.delete(f"{BASE}/events/ev-1001"), 404, "NOT_FOUND")  # Amara's event


def test_suggestion_moves_on_once_planned(client, monkeypatch):
    login(client, AMARA)
    suggestion = client.get(f"{BASE}/events").json()["suggestion"]
    created = client.post(f"{BASE}/events", json={"title": suggestion["title"], "type": "Study", "date": suggestion["date"],
                                                   "start": suggestion["start"], "end": suggestion["end"]}).json()
    try:
        after = client.get(f"{BASE}/events").json()["suggestion"]
        # The proposal now has a study block, so the suggestion moves on to the next deadline (Week 6 tutorial, Oct 5).
        assert after["text"].startswith("You have a free 2-hour window on Friday evening. Blocking it for Week 6 tutorial")
        assert (after["start"], after["end"]) == ("19:30", "21:30")

        cfg = deepcopy(ai_config.DEFAULTS)
        cfg["features"]["proactiveTips"] = False
        monkeypatch.setattr(ai_config, "ai_settings", lambda db: cfg)
        assert client.get(f"{BASE}/events").json()["suggestion"] is None
    finally:
        client.delete(f"{BASE}/events/{created['id']}")


def test_calendar_feed(client):
    login(client, AMARA)
    url = client.get(f"{BASE}/calendar").json()["url"]
    assert client.get(f"{BASE}/calendar").json()["url"] == url
    assert url.startswith("http://testserver/api/v1/calendar/") and url.endswith(".ics")
    path = url.removeprefix("http://testserver")

    client.cookies.clear()  # the feed is public: no session cookie
    feed = client.get(path)
    assert feed.status_code == 200 and feed.headers["content-type"].startswith("text/calendar")
    body = feed.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "UID:cls-503-2026-10-01@acadmate\r\n" in body
    assert "DTSTART:20261001T140000Z\r\nDTEND:20261001T164500Z\r\n" in body  # 10:00-12:45 EDT
    assert "SUMMARY:Team project sync" in body and "LOCATION:Online · Dr. Sarah Smith" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))

    login(client, AMARA)
    new_url = client.post(f"{BASE}/calendar/rotate").json()["url"]
    assert new_url != url
    assert_envelope(client.get(path), 404, "NOT_FOUND")
    assert client.get(new_url.removeprefix("http://testserver")).status_code == 200

    download = client.get(f"{BASE}/calendar.ics")
    assert download.status_code == 200
    assert download.headers["content-disposition"] == 'attachment; filename="acadmate.ics"'


def test_schedule_requires_student(client, as_user):
    assert_envelope(client.get(f"{BASE}/events"), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(f"{BASE}/events"), 403, "FORBIDDEN")


def test_ics_escaping(db):
    from services.calendar import _fold, _ics_text
    assert _ics_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    folded = _fold("SUMMARY:" + "x" * 200)
    assert all(len(part.encode()) <= 75 for part in folded) and all(part.startswith(" ") for part in folded[1:])
    assert db.query(Event).count() >= 6
