"""Book a meeting (spec 18): staff, availability, booking, the meeting state machine and reminders.
conftest pins today to 2026-10-01 (Thu), so the bookable weeks start Sep 28 and Oct 5. Times are New York (EDT = UTC-4)."""
import threading
from datetime import datetime, timedelta, timezone

import pytest

from conftest import login
from core.errors import ApiError
from database import SessionLocal
from models import Conversation, ConversationParticipant, Meeting, Message, Student, User
from services import meetings as meetings_service
from services.reminders import send_due_reminders
from test_foundation import assert_envelope

STAFF, MEETINGS, MINE = "/api/v1/staff", "/api/v1/meetings", "/api/v1/students/me/meetings"
AMARA, SARAH, KOFI = "amara.okafor@pac.edu", "sarah.smith@pac.edu", "kofi.mensah@pac.edu"
SARAH_ID, MAYA_ID, GRAD_OFFICE_ID = 2, 11, 10
LAST_SEEDED_MEETING, LAST_SEEDED_CONVERSATION, LAST_SEEDED_MESSAGE = 1507, 1305, 1411
NEXT_WEEK = "2026-10-05"
MEETING_FIELDS = ("starts_at", "ends_at", "status", "proposed_starts_at", "advisor_notes", "reminded_at")


@pytest.fixture(autouse=True)
def restore_meetings():
    """Puts the seeded meetings and messages back: bookings post notices, which would change the messages tests."""
    with SessionLocal() as db:
        saved = {m.id: {field: getattr(m, field) for field in MEETING_FIELDS} for m in db.query(Meeting)}
        last_at = {c.id: c.last_message_at for c in db.query(Conversation).filter(Conversation.id <= LAST_SEEDED_CONVERSATION)}
    yield
    with SessionLocal() as db:
        db.query(Meeting).filter(Meeting.id > LAST_SEEDED_MEETING).delete(synchronize_session=False)
        for meeting in db.query(Meeting):
            for field, value in saved[meeting.id].items():
                setattr(meeting, field, value)
        db.query(Message).filter(Message.id > LAST_SEEDED_MESSAGE).delete(synchronize_session=False)
        db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id > LAST_SEEDED_CONVERSATION).delete(
            synchronize_session=False)
        db.query(Conversation).filter(Conversation.id > LAST_SEEDED_CONVERSATION).delete(synchronize_session=False)
        for conversation in db.query(Conversation):
            conversation.last_message_at = last_at[conversation.id]
        db.commit()


def at(day: int, hour: int, minute: int = 0) -> str:
    """An October 2026 New York time as the API's UTC string."""
    return datetime(2026, 10, day, hour + 4, minute, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def book(client, **changes):
    body = {"staffId": SARAH_ID, "startsAt": at(6, 11), "format": "In person", "topic": "Capstone topics",
            "note": "I'd like to compare two capstone ideas.", "attachPlan": True, **changes}
    return client.post(MEETINGS, json=body)


def days(client, staff_id: int, week: str = NEXT_WEEK) -> dict:
    data = client.get(f"{STAFF}/{staff_id}/availability?week={week}").json()
    return {day["dow"]: day for day in data["days"]}


def slot(day: dict, clock: str) -> dict:
    return next(s for s in day["slots"] if s["time"] == clock)


def notices(user_id: int) -> list[str]:
    with SessionLocal() as db:
        return [m.text for m in db.query(Message).join(Conversation, Conversation.id == Message.conversation_id)
                .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
                .filter(Conversation.kind == "system", ConversationParticipant.user_id == user_id).order_by(Message.id)]


def test_staff_list(client):
    login(client, AMARA)
    data = client.get(f"{STAFF}?bookable=true").json()
    assert [(s["id"], s["name"], s["role"], s["isMyAdvisor"]) for s in data["staff"]] == [
        (SARAH_ID, "Dr. Sarah Smith", "Faculty advisor", True), (MAYA_ID, "Maya Brooks", "Career services", False),
        (GRAD_OFFICE_ID, "Graduate office", "Student services", False)]
    sarah = data["staff"][0]
    assert (sarah["userId"], sarah["initials"], sarah["helps"], sarah["office"], sarah["meetingLength"],
            sarah["bookingWindowWeeks"]) == (2, "SS", "Degree plan, capstone, course approvals", "Room 4.12, Science Hall", 30, 2)
    assert data["topics"] == ["Spring 2027 plan", "Capstone topics", "Add or drop a course", "Internship or career",
                              "Something else"]
    assert data["formats"] == ["In person", "Online"] and data["firstWeek"] == "2026-09-28"


def test_availability_shape_and_lead_time(client):
    login(client, AMARA)
    data = client.get(f"{STAFF}/{SARAH_ID}/availability?week={NEXT_WEEK}").json()
    assert (data["staffId"], data["week"], data["timeZone"]) == (SARAH_ID, NEXT_WEEK, "America/New_York")
    assert [(d["date"], d["dow"], d["day"]) for d in data["days"]] == [
        ("2026-10-05", "Mon", "5"), ("2026-10-06", "Tue", "6"), ("2026-10-07", "Wed", "7"), ("2026-10-08", "Thu", "8"),
        ("2026-10-09", "Fri", "9")]
    monday = data["days"][0]
    assert len(monday["slots"]) == 16 and monday["slots"][0] == {"startsAt": "2026-10-05T13:00:00Z", "time": "09:00", "taken": True}
    assert (monday["open"], monday["free"]) == (15, "15 open")  # 09:00 is another student's meeting

    wednesday = days(client, SARAH_ID)["Wed"]
    assert [s["time"] for s in wednesday["slots"] if s["taken"]] == ["10:00", "10:30"]

    this_week = days(client, SARAH_ID, "2026-09-28")  # Mon-Wed have passed (today's slots depend on the clock)
    assert all((this_week[dow]["open"], this_week[dow]["free"]) == (0, "Full") for dow in ("Mon", "Tue", "Wed"))


def test_class_times_block_every_staff_member(client):
    """Acceptance 1: Thursday 10:00-12:45 is CS 675, so those slots are taken with everyone."""
    login(client, AMARA)
    for staff_id in (SARAH_ID, MAYA_ID):
        thursday = days(client, staff_id)["Thu"]
        taken = [s["time"] for s in thursday["slots"] if s["taken"]]
        assert taken[:6] == ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30"]
        assert "15:00" in taken  # Amara's own capstone meeting with Dr. Smith
        assert not slot(thursday, "13:00")["taken"]
    assert not slot(days(client, SARAH_ID)["Thu"], "09:30")["taken"]


def test_book_and_see_it_taken(client):
    """Acceptance 2."""
    login(client, AMARA)
    response = book(client)
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "requested"  # Dr. Smith confirms bookings herself
    assert result["summary"] == ("You asked to meet Dr. Sarah Smith on Tuesday, Oct 6 at 11:00–11:30 (in person) "
                                 "about capstone topics.")
    assert result["meeting"] == {"id": result["id"], "staffId": SARAH_ID, "title": "Capstone topics", "mon": "Oct",
                                 "day": "6", "meta": "Tue · 11:00 · In person · Dr. Sarah Smith",
                                 "startsAt": "2026-10-06T15:00:00Z", "status": "requested", "proposedStartsAt": None}
    assert slot(days(client, SARAH_ID)["Tue"], "11:00")["taken"]
    assert slot(days(client, MAYA_ID)["Tue"], "11:00")["taken"]  # Amara is busy then, whoever she'd meet
    assert notices(SARAH_ID)[-1].startswith("Amara Okafor requested a meeting: Capstone topics on Tue, Oct 6 at 11:00")
    assert notices(1)[-1].startswith("Meeting requested: Capstone topics with Dr. Sarah Smith")
    assert result["id"] in [m["id"] for m in client.get(MINE).json()["meetings"]]

    with SessionLocal() as db:
        meeting = db.get(Meeting, result["id"])
        assert (meeting.advisor_id, meeting.location, meeting.attach_plan) == (201, "Room 4.12, Science Hall", True)


def test_auto_confirm_and_online_link(client):
    login(client, AMARA)
    result = book(client, staffId=GRAD_OFFICE_ID, startsAt=at(5, 10), format="Online", topic="Something about records").json()
    assert result["status"] == "confirmed"
    assert result["summary"] == ("You're meeting Graduate office on Monday, Oct 5 at 10:00–10:30 (online) about "
                                 "“Something about records”. A confirmation is in your Messages.")
    with SessionLocal() as db:
        meeting = db.get(Meeting, result["id"])
        assert meeting.video_url == f"https://meet.example.edu/{meeting.id}" and meeting.location is None
    assert notices(GRAD_OFFICE_ID)[-1].startswith("Amara Okafor booked a meeting")


def test_same_slot_twice_is_409(client):
    """Acceptance 3 (sequential): the second student gets SLOT_TAKEN."""
    login(client, AMARA)
    assert book(client, startsAt=at(6, 13)).status_code == 201
    login(client, KOFI)
    error = assert_envelope(book(client, startsAt=at(6, 13)), 409, "SLOT_TAKEN")
    assert error["message"] == "That time was just taken. Pick another."


def test_concurrent_bookings_one_wins():
    """Acceptance 3 (concurrent): two sessions book the same slot at once; the staff row lock lets one through."""
    barrier, results = threading.Barrier(2), []
    start = datetime.fromisoformat(at(7, 14).replace("Z", "+00:00"))

    def attempt(user_id: int):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            student = db.query(Student).filter(Student.user_id == user_id).one()
            barrier.wait()
            try:
                meetings_service.book(db, student, user, {"staff_id": SARAH_ID, "starts_at": start, "format": "Online",
                                                          "topic": "Capstone topics", "note": None, "attach_plan": False})
                results.append("booked")
            except ApiError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=attempt, args=(user_id,)) for user_id in (6, 7)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(results) == ["SLOT_TAKEN", "booked"]


def test_cancel_frees_the_slot(client):
    """Acceptance 4."""
    login(client, AMARA)
    meeting_id = book(client, startsAt=at(9, 11)).json()["id"]
    response = client.post(f"{MEETINGS}/{meeting_id}/cancel")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert meeting_id not in [m["id"] for m in client.get(MINE).json()["meetings"]]
    assert not slot(days(client, SARAH_ID)["Fri"], "11:00")["taken"]
    assert notices(SARAH_ID)[-1].startswith("Amara Okafor cancelled Capstone topics on Fri, Oct 9 at 11:00")
    assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/cancel"), 409, "CONFLICT")


def test_propose_then_accept(client):
    """Acceptance 5: the advisor proposes a new time; the student sees it and accepts."""
    login(client, SARAH)
    proposed = client.post(f"{MEETINGS}/1502/propose", json={"startsAt": at(9, 11)})
    assert proposed.status_code == 200 and proposed.json()["status"] == "proposed"
    assert notices(1)[-1].startswith("Dr. Sarah Smith proposed a new time for Capstone topics: Fri, Oct 9 at 11:00")

    login(client, AMARA)
    row = next(m for m in client.get(MINE).json()["meetings"] if m["id"] == 1502)
    assert (row["status"], row["proposedStartsAt"]) == ("proposed", "2026-10-09T15:00:00Z")
    assert slot(days(client, SARAH_ID)["Fri"], "11:00")["taken"]  # held while the proposal is open

    accepted = client.post(f"{MEETINGS}/1502/accept").json()
    assert (accepted["status"], accepted["startsAt"], accepted["proposedStartsAt"], accepted["day"]) == (
        "confirmed", "2026-10-09T15:00:00Z", None, "9")
    assert not slot(days(client, SARAH_ID)["Thu"], "15:00")["taken"]  # the old time is free again


def test_advisor_accept_decline_and_rules(client):
    login(client, AMARA)
    meeting_id = book(client, startsAt=at(6, 14)).json()["id"]
    assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/accept"), 409, "CONFLICT")  # students accept only proposals
    assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/decline"), 409, "CONFLICT")

    login(client, SARAH)
    assert client.post(f"{MEETINGS}/{meeting_id}/accept").json()["status"] == "confirmed"
    assert notices(1)[-1] == "Dr. Sarah Smith confirmed your meeting on Tue, Oct 6 at 14:00 (Capstone topics)."
    assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/complete"), 409, "CONFLICT")  # it hasn't started yet
    error = assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/propose", json={}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "startsAt"
    assert_envelope(client.post(f"{MEETINGS}/{meeting_id}/propose", json={"startsAt": at(5, 9)}), 409, "SLOT_TAKEN")

    login(client, AMARA)
    other = book(client, startsAt=at(6, 15)).json()["id"]
    login(client, SARAH)
    declined = client.post(f"{MEETINGS}/{other}/decline", json={"note": "I'm at a conference that afternoon."})
    assert declined.json()["status"] == "cancelled"
    assert "I'm at a conference that afternoon." in notices(1)[-1]


def test_booking_errors(client, as_user):
    login(client, AMARA)
    assert_envelope(client.get(f"{STAFF}/{SARAH_ID}/availability?week=2026-10-12"), 400, "BAD_REQUEST")  # past the window
    assert_envelope(client.get(f"{STAFF}/{SARAH_ID}/availability?week=2026-09-21"), 400, "BAD_REQUEST")
    assert_envelope(client.get(f"{STAFF}/{SARAH_ID}/availability?week=2026-10-06"), 400, "BAD_REQUEST")  # not a Monday
    assert_envelope(client.get(f"{STAFF}/3/availability?week={NEXT_WEEK}"), 404, "NOT_FOUND")  # not bookable
    assert_envelope(client.get(f"{STAFF}/9999/availability?week={NEXT_WEEK}"), 404, "NOT_FOUND")

    assert_envelope(book(client, startsAt=at(5, 9)), 409, "SLOT_TAKEN")  # another student's meeting
    assert_envelope(book(client, startsAt=at(8, 10)), 409, "SLOT_TAKEN")  # CS 675
    assert_envelope(book(client, startsAt=at(6, 11, 15)), 400, "BAD_REQUEST")  # not a slot
    assert_envelope(book(client, startsAt=at(13, 11)), 400, "BAD_REQUEST")  # outside the window
    assert_envelope(book(client, staffId=9999), 404, "NOT_FOUND")
    assert_envelope(book(client, startsAt="2026-09-01T14:00:00Z"), 422, "VALIDATION_ERROR")
    assert_envelope(book(client, startsAt="2026-10-06T11:00:00"), 422, "VALIDATION_ERROR")  # no time zone
    assert_envelope(book(client, topic="x" * 81), 422, "VALIDATION_ERROR")
    assert_envelope(book(client, topic="   "), 422, "VALIDATION_ERROR")
    assert_envelope(book(client, format="Phone"), 422, "VALIDATION_ERROR")
    assert_envelope(book(client, note="x" * 501), 422, "VALIDATION_ERROR")

    assert_envelope(client.post(f"{MEETINGS}/1501/accept"), 409, "CONFLICT")  # already confirmed
    assert_envelope(client.post(f"{MEETINGS}/1501/reschedule"), 422, "VALIDATION_ERROR")  # unknown action
    login(client, KOFI)
    assert_envelope(client.post(f"{MEETINGS}/1501/cancel"), 404, "NOT_FOUND")  # not his meeting
    assert_envelope(client.post(f"{MEETINGS}/999999/cancel"), 404, "NOT_FOUND")

    client.cookies.clear()
    assert_envelope(client.get(STAFF), 401, "UNAUTHENTICATED")
    as_user("advisor")
    assert_envelope(client.get(STAFF), 403, "FORBIDDEN")


def test_upcoming_meetings(client):
    login(client, AMARA)
    rows = client.get(MINE).json()["meetings"]
    assert [(m["id"], m["title"], m["mon"], m["day"], m["meta"], m["status"]) for m in rows] == [
        (1501, "Advising check-in", "Oct", "1", "Today · 15:00 · Online · Dr. Sarah Smith", "confirmed"),
        (1502, "Capstone topics", "Oct", "8", "Thu · 15:00 · In person · Dr. Sarah Smith", "requested"),
    ]  # the completed meeting in September isn't listed


def test_messages_link_preselects_staff(client):
    """The Messages "Schedule meeting" link passes otherUserId, which is the staff id here."""
    login(client, AMARA)
    rows = {row["id"]: row for row in client.get("/api/v1/conversations").json()["conversations"]}
    staff_ids = {s["id"] for s in client.get(STAFF).json()["staff"]}
    assert rows[1301]["bookable"] and rows[1301]["otherUserId"] in staff_ids
    assert not rows[1303]["bookable"]  # Prof. Kim teaches CS 608 but doesn't take bookings


def test_day_before_reminders(db):
    starts = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)  # tomorrow 11:00
    db.add(Meeting(student_id=102, advisor_id=201, staff_user_id=SARAH_ID, starts_at=starts,
                   ends_at=starts + timedelta(minutes=30), format="online", topic="Add or drop a course",
                   status="confirmed"))
    db.commit()
    assert send_due_reminders(db) == 1
    assert send_due_reminders(db) == 0
    assert notices(6)[-1] == "Reminder: Add or drop a course with Dr. Sarah Smith tomorrow at 11:00."
    assert notices(SARAH_ID)[-1] == "Reminder: Add or drop a course with Kofi Mensah tomorrow at 11:00."
