"""Advisor messages (spec 25): Dr. Smith's inbox (seed_advisor_messages), advisee rows and the advising team group."""
from conftest import login
from database import SessionLocal
from models import ConversationParticipant, User
from test_foundation import assert_envelope
from test_messages import restore_messages  # noqa: F401 (fixture)

CONVERSATIONS = "/api/v1/conversations"
AMARA_CHAT, MARCUS_CHAT, DANIEL_CHAT, TEAM_CHAT, SMITH_NOTICES = 1301, 1306, 1307, 1308, 1309
SARAH = "sarah.smith@pac.edu"


def badge(client) -> int:
    return client.get("/api/v1/users/me/badges").json()["badges"]["messages"]


def test_inbox(client, restore_messages):  # noqa: F811
    login(client, SARAH)
    rows = {row["id"]: row for row in client.get(CONVERSATIONS).json()["conversations"]}
    assert set(rows) == {AMARA_CHAT, MARCUS_CHAT, DANIEL_CHAT, TEAM_CHAT, SMITH_NOTICES}
    marcus, team, notices = rows[MARCUS_CHAT], rows[TEAM_CHAT], rows[SMITH_NOTICES]
    assert (marcus["name"], marcus["role"], marcus["unread"], marcus["studentId"], marcus["team"]) == (
        "Marcus Tran", "Advisee · M.S. Computer Science", 2, 108, False)
    assert (rows[DANIEL_CHAT]["unread"], rows[AMARA_CHAT]["unread"], rows[AMARA_CHAT]["studentId"]) == (1, 0, 101)
    assert (team["name"], team["role"], team["team"], team["studentId"], team["unread"]) == (
        "Computer Science advising team", "2 advisors", True, None, 0)
    assert (notices["name"], notices["role"], notices["canReply"]) == ("Acadmate", "Notifications", False)

    assert badge(client) == 3
    client.get(f"{CONVERSATIONS}/{MARCUS_CHAT}/messages")
    assert badge(client) == 1


def test_quick_reply_and_to_param(client, restore_messages):  # noqa: F811
    login(client, SARAH)
    sent = client.post(f"{CONVERSATIONS}/{DANIEL_CHAT}/messages", json={"text": "Approved. Thanks!"})
    assert sent.status_code == 201
    first = client.get(CONVERSATIONS).json()["conversations"][0]
    assert (first["id"], first["preview"]) == (DANIEL_CHAT, "You: Approved. Thanks!")

    # /advisor/messages?to=1 reuses Amara's thread.
    assert client.post(CONVERSATIONS, json={"recipientIds": [1]}).json() == {"id": AMARA_CHAT}


def test_team_conversation(client, as_user, restore_messages):  # noqa: F811
    login(client, SARAH)
    assert client.post(f"{CONVERSATIONS}/team").json() == {"id": TEAM_CHAT}
    assert client.post(f"{CONVERSATIONS}/team").json() == {"id": TEAM_CHAT}  # always the same group

    with SessionLocal() as db:
        db.get(User, 9).is_active = False  # Prof. Kim leaves
        db.commit()
    try:
        client.post(f"{CONVERSATIONS}/team")
        with SessionLocal() as db:
            members = {p.user_id for p in db.query(ConversationParticipant).filter_by(conversation_id=TEAM_CHAT)}
        assert members == {2}
    finally:
        with SessionLocal() as db:
            db.get(User, 9).is_active = True
            db.commit()
        client.post(f"{CONVERSATIONS}/team")  # re-adds him

    with SessionLocal() as db:
        assert {p.user_id for p in db.query(ConversationParticipant).filter_by(conversation_id=TEAM_CHAT)} == {2, 9}

    for role in ("student", "admin"):
        as_user(role)
        assert_envelope(client.post(f"{CONVERSATIONS}/team"), 403, "FORBIDDEN")
