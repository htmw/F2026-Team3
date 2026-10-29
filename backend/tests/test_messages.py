"""Messages (spec 16): conversations, contacts, threads, sending, notify() and the badge. conftest pins today to 2026-10-01."""
from datetime import date, datetime, timezone

import pytest

from conftest import login
from database import SessionLocal
from models import Conversation, ConversationParticipant, Message, Student
from services import messages as messages_service
from test_foundation import assert_envelope

BASE = "/api/v1/conversations"
BADGES = "/api/v1/users/me/badges"
AMARA, SARAH = "amara.okafor@pac.edu", "sarah.smith@pac.edu"
ADVISOR_CHAT, TEAM_CHAT, KIM_CHAT, NOTICES, GRAD_OFFICE_CHAT = 1301, 1302, 1303, 1304, 1305
LAST_SEEDED_CONVERSATION, LAST_SEEDED_MESSAGE = 1309, 1417  # 1306-1309: seed_advisor_messages


@pytest.fixture
def restore_messages():
    """Tests that read or write Amara's messages put the seeded state back (the seeded database is shared)."""
    with SessionLocal() as db:
        saved = {(p.conversation_id, p.user_id): p.last_read_at for p in db.query(ConversationParticipant)
                 .filter(ConversationParticipant.conversation_id <= LAST_SEEDED_CONVERSATION)}
        last_at = {c.id: c.last_message_at for c in db.query(Conversation).filter(Conversation.id <= LAST_SEEDED_CONVERSATION)}
    yield
    with SessionLocal() as db:
        db.query(Message).filter(Message.id > LAST_SEEDED_MESSAGE).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.id > LAST_SEEDED_CONVERSATION).delete(synchronize_session=False)
        for participant in db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id <= LAST_SEEDED_CONVERSATION):
            participant.last_read_at = saved.get((participant.conversation_id, participant.user_id))
        for conversation in db.query(Conversation).filter(Conversation.id <= LAST_SEEDED_CONVERSATION):
            conversation.last_message_at = last_at[conversation.id]
        db.commit()


def test_list_matches_design(client):
    login(client, AMARA)
    rows = client.get(BASE).json()["conversations"]
    assert [row["id"] for row in rows] == [ADVISOR_CHAT, TEAM_CHAT, KIM_CHAT, NOTICES, GRAD_OFFICE_CHAT]
    advisor, team, kim, notices, grad = rows
    assert advisor == {
        "id": ADVISOR_CHAT, "kind": "direct", "name": "Dr. Sarah Smith", "initials": "SS", "role": "Faculty advisor",
        "preview": "Yes. Bring two or three ideas, and please send the capstone pre-approval form by Oct 20.",
        "time": "09:42", "lastAt": "2026-10-01T13:42:00Z", "unread": 1, "canReply": True, "bookable": True,
        "otherUserId": 2, "members": 2, "studentId": None, "team": False,
    }
    assert (team["kind"], team["name"], team["role"], team["unread"], team["members"]) == ("group", "CS 675 project team", "4 members", 2, 4)
    assert (kim["role"], kim["time"], kim["unread"]) == ("CS 608 · Algorithms & Computing Theory", "Yesterday", 0)
    assert (notices["name"], notices["initials"], notices["role"], notices["canReply"], notices["bookable"]) == (
        "Acadmate", "AI", "Notifications", False, False)
    assert (grad["name"], grad["role"], grad["time"], grad["bookable"]) == ("Graduate office", "Student services", "Sep 29", True)
    assert client.get(BADGES).json()["badges"]["messages"] == 3


def test_own_last_message_preview(client, restore_messages):
    login(client, AMARA)
    client.post(f"{BASE}/{KIM_CHAT}/messages", json={"text": "  See you Monday.  "})
    row = next(r for r in client.get(BASE).json()["conversations"] if r["id"] == KIM_CHAT)
    assert row["preview"] == "You: See you Monday."


def test_opening_a_thread_marks_it_read(client, restore_messages):
    login(client, AMARA)
    data = client.get(f"{BASE}/{ADVISOR_CHAT}/messages").json()
    assert data["canReply"] is True
    assert [m["text"][:10] for m in data["messages"]] == ["Hi Amara, ", "Thank you!", "Yes. Bring"]
    first, mine, _ = data["messages"]
    assert (first["from"], first["mine"], first["showName"], first["time"]) == ("Dr. Sarah Smith", False, False, "Yesterday 16:05")
    assert (mine["from"], mine["mine"]) == ("Amara Okafor", True)
    rows = {row["id"]: row for row in client.get(BASE).json()["conversations"]}
    assert rows[ADVISOR_CHAT]["unread"] == 0
    assert client.get(BADGES).json()["badges"]["messages"] == 2


def test_group_thread_shows_sender_names(client, restore_messages):
    login(client, AMARA)
    data = client.get(f"{BASE}/{TEAM_CHAT}/messages").json()
    others = [m for m in data["messages"] if not m["mine"]]
    assert all(m["showName"] for m in others) and others[0]["from"] == "Kofi Mensah"
    assert not any(m["showName"] for m in data["messages"] if m["mine"])


def test_system_conversation_is_read_only(client, restore_messages):
    login(client, AMARA)
    assert client.get(f"{BASE}/{NOTICES}/messages").json()["canReply"] is False
    error = assert_envelope(client.post(f"{BASE}/{NOTICES}/messages", json={"text": "Hello?"}), 403, "READ_ONLY")
    assert error["message"] == "Automated notifications can't be replied to."


def test_send_reply(client, restore_messages):
    login(client, AMARA)
    response = client.post(f"{BASE}/{ADVISOR_CHAT}/messages", json={"text": "I'll send it this week."})
    assert response.status_code == 201
    message = response.json()
    assert (message["from"], message["mine"], message["showName"], message["text"]) == ("Amara Okafor", True, False, "I'll send it this week.")
    login(client, SARAH)
    assert client.get(BADGES).json()["badges"]["messages"] == 4  # this reply + Marcus's 2 and Daniel's 1 (spec 25 seed)
    row = next(r for r in client.get(BASE).json()["conversations"] if r["id"] == ADVISOR_CHAT)
    assert (row["name"], row["role"], row["bookable"], row["unread"]) == ("Amara Okafor", "Advisee · M.S. Computer Science", False, 1)


def test_send_validation(client):
    login(client, AMARA)
    assert_envelope(client.post(f"{BASE}/{ADVISOR_CHAT}/messages", json={"text": "   "}), 422, "VALIDATION_ERROR")
    assert_envelope(client.post(f"{BASE}/{ADVISOR_CHAT}/messages", json={"text": "x" * 4001}), 422, "VALIDATION_ERROR")


def test_not_a_participant(client):
    login(client, SARAH)
    assert_envelope(client.get(f"{BASE}/{TEAM_CHAT}/messages"), 404, "NOT_FOUND")
    assert_envelope(client.post(f"{BASE}/{NOTICES}/messages", json={"text": "Hi"}), 404, "NOT_FOUND")


def test_search(client):
    login(client, AMARA)
    ids = [row["id"] for row in client.get(BASE, params={"q": "capstone"}).json()["conversations"]]
    assert ADVISOR_CHAT in ids and TEAM_CHAT not in ids
    assert [row["id"] for row in client.get(BASE, params={"q": "project team"}).json()["conversations"]] == [TEAM_CHAT]
    assert [row["id"] for row in client.get(BASE, params={"q": "notifications"}).json()["conversations"]] == [NOTICES]
    assert client.get(BASE, params={"q": "100%"}).json()["conversations"] == []


def test_student_contacts(client):
    login(client, AMARA)
    contacts = {c["name"]: c for c in client.get(f"{BASE}/contacts").json()["contacts"]}
    assert set(contacts) == {"Dr. Sarah Smith", "Prof. Daniel Kim", "Kofi Mensah", "Lena Fischer", "Diego Alvarez", "Graduate office"}
    assert contacts["Dr. Sarah Smith"]["title"] == "Faculty advisor"
    assert contacts["Kofi Mensah"] == {"id": 6, "name": "Kofi Mensah", "initials": "KM", "role": "student", "title": "Classmate"}
    assert [c["name"] for c in client.get(f"{BASE}/contacts", params={"q": "smi"}).json()["contacts"]] == ["Dr. Sarah Smith"]


def test_advisor_and_admin_contacts(client):
    login(client, SARAH)
    names = {c["name"] for c in client.get(f"{BASE}/contacts").json()["contacts"]}
    assert {"Amara Okafor", "Prof. Daniel Kim", "Jordan Lee", "Graduate office"} <= names
    assert "Kofi Mensah" not in names and "Dr. Sarah Smith" not in names and "Sam Rivera" not in names
    login(client, "jordan.lee@pac.edu")
    names = {c["name"] for c in client.get(f"{BASE}/contacts").json()["contacts"]}
    assert "Kofi Mensah" in names and "Sam Rivera" not in names  # deactivated users are never contacts


def test_new_message_to_advisor_reuses_conversation(client, restore_messages):
    login(client, AMARA)
    response = client.post(BASE, json={"recipientIds": [2], "text": "One more question about the form."})
    assert response.status_code == 201 and response.json() == {"id": ADVISOR_CHAT}
    rows = client.get(BASE).json()["conversations"]
    assert (rows[0]["id"], rows[0]["preview"]) == (ADVISOR_CHAT, "You: One more question about the form.")


def test_start_direct_and_group(client, restore_messages):
    login(client, AMARA)
    direct = client.post(BASE, json={"recipientIds": [6]}).json()["id"]
    assert direct > LAST_SEEDED_CONVERSATION
    assert client.post(BASE, json={"recipientIds": [6, 6]}).json()["id"] == direct
    row = next(r for r in client.get(BASE).json()["conversations"] if r["id"] == direct)
    assert (row["kind"], row["name"], row["role"], row["preview"], row["time"]) == ("direct", "Kofi Mensah", "Classmate", None, None)

    group = client.post(BASE, json={"recipientIds": [7, 8], "text": "Study session?"}).json()["id"]
    row = next(r for r in client.get(BASE).json()["conversations"] if r["id"] == group)
    assert (row["kind"], row["name"], row["role"], row["unread"]) == ("group", "Group", "3 members", 0)
    login(client, "lena.fischer@pac.edu")
    row = next(r for r in client.get(BASE).json()["conversations"] if r["id"] == group)
    assert row["unread"] == 1


def test_start_with_non_contact_is_forbidden(client, make_user):
    stranger = make_user("student")
    login(client, AMARA)
    assert_envelope(client.post(BASE, json={"recipientIds": [stranger.user_id]}), 403, "FORBIDDEN")
    assert_envelope(client.post(BASE, json={"recipientIds": [4]}), 403, "FORBIDDEN")  # deactivated
    assert_envelope(client.post(BASE, json={"recipientIds": [3]}), 403, "FORBIDDEN")  # admin without is_support
    assert_envelope(client.post(BASE, json={"recipientIds": []}), 422, "VALIDATION_ERROR")
    assert_envelope(client.post(BASE, json={"recipientIds": list(range(1, 32))}), 422, "VALIDATION_ERROR")


def test_requires_sign_in(client):
    assert_envelope(client.get(BASE), 401, "UNAUTHENTICATED")


def test_notify_creates_then_reuses_system_conversation(client, make_user):
    user = make_user("student")
    with SessionLocal() as db:
        db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
        messages_service.notify(db, user.user_id, "Welcome to Acadmate.")
        messages_service.notify(db, user.user_id, "Your plan is waiting for advisor approval.")
        db.commit()
        systems = (db.query(Conversation).join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
                   .filter(ConversationParticipant.user_id == user.user_id).all())
        assert [c.kind for c in systems] == ["system"]
    login(client, user.email)
    rows = client.get(BASE).json()["conversations"]
    assert [(r["name"], r["unread"], r["preview"]) for r in rows] == [("Acadmate", 2, "Your plan is waiting for advisor approval.")]
    assert client.get(BADGES).json()["badges"]["messages"] == 2


def test_time_labels():
    day = date(2026, 10, 1)
    assert messages_service.format_time(datetime(2026, 10, 1, 13, 42, tzinfo=timezone.utc), day) == "09:42"
    assert messages_service.format_time(datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc), day) == "Yesterday"  # 23:00 local
    assert messages_service.format_time(datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc), day) == "Sep 29"
    assert messages_service.message_time(datetime(2026, 9, 30, 20, 5, tzinfo=timezone.utc), day) == "Yesterday 16:05"
    assert messages_service.message_time(datetime(2026, 9, 29, 14, 0, tzinfo=timezone.utc), day) == "Sep 29 10:00"
