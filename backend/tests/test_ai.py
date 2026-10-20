"""AI advisor (spec 13). conftest pins today to 2026-10-01 (Fall 2026; next term Spring 2027).
The Claude API is never called: the key is cleared for every test, and Claude tests use a fake client or engine."""
from copy import deepcopy
from types import SimpleNamespace

import anthropic
import pytest

from conftest import login
from core.config import settings
from database import SessionLocal
from models import AiFlag, AiMessage, Student
from seed_data import PLAN_SOURCES
from services import ai
from services.ai import claude_engine, recommend
from services.ai import settings as ai_config
from services.ai.rules_engine import FALLBACK
from test_foundation import assert_envelope

BASE = "/api/v1/students/me/ai"
AMARA = "amara.okafor@pac.edu"


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)


@pytest.fixture
def ai_settings(monkeypatch):
    """Returns a mutable copy of the AI settings that ai_config.ai_settings() will serve."""
    cfg = deepcopy(ai_config.DEFAULTS)
    monkeypatch.setattr(ai_config, "ai_settings", lambda db: cfg)
    return cfg


@pytest.fixture
def new_student(make_user):
    """A signed-up student with no enrollments, preferences or AI history."""
    def create():
        user = make_user("student")
        with SessionLocal() as db:
            db.add(Student(user_id=user.user_id, name=user.name, email=user.email, program_id=1))
            db.commit()
        return user
    return create


def ask(client, text, thread_id=None):
    if thread_id:
        response = client.post(f"{BASE}/threads/{thread_id}/messages", json={"text": text})
        assert response.status_code == 200, response.text
        return response.json()["reply"]
    response = client.post(f"{BASE}/threads", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()["messages"][1]


def test_context(client, new_student):
    login(client, AMARA)
    data = client.get(f"{BASE}/context").json()
    assert data["enabled"] is True and data["engine"] == "Rules" and data["dailyLimit"] == 25
    assert data["program"] == "M.S. Computer Science"
    assert data["progress"] == "21 credits earned · 9 in progress"
    assert data["goal"] == "Graduate May 2027" and data["preferences"] == ["Evening classes"]
    assert data["sources"] == ["Degree audit", "Grades", "Course catalog", "Schedule"]
    assert data["advisor"] == {"id": 201, "name": "Dr. Sarah Smith"}
    assert data["nextMeeting"] == {"date": "2026-10-01", "time": "15:00"} and data["retention"] == "1 year" and len(data["prompts"]) == 3

    login(client, new_student().email)
    fresh = client.get(f"{BASE}/context").json()
    assert fresh["remainingToday"] == 25 and fresh["preferences"] == [] and fresh["advisor"] is None


def test_context_engine_claude_needs_key(client, monkeypatch):
    login(client, AMARA)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    assert client.get(f"{BASE}/context").json()["engine"] == "Claude"


def test_seeded_threads(client):
    login(client, AMARA)
    threads = client.get(f"{BASE}/threads").json()["threads"]
    assert [thread["title"] for thread in threads][:4] == [
        "Plan my Spring 2027 semester", "Can I take CS 608 and CS 675 together?",
        "Internship credit options", "Capstone topic ideas"]
    detail = client.get(f"{BASE}/threads/701").json()
    assert len(detail["messages"]) == 4
    answer = detail["messages"][1]
    assert answer["planTerm"] == "Spring 2027" and [row["code"] for row in answer["plan"]] == ["CS 691", "CS 680"]
    assert answer["sources"] == PLAN_SOURCES and answer["plan"][0]["onPlan"] is False


def test_plan_and_what_if(client):
    login(client, AMARA)
    response = client.post(f"{BASE}/threads", json={"text": "Plan my Spring 2027 semester. I prefer evening classes."})
    assert response.status_code == 201
    data = response.json()
    assert data["thread"]["title"] == "Plan my Spring 2027 semester. I prefer evening classes."
    question, reply = data["messages"]
    assert question["role"] == "user" and reply["role"] == "assistant" and reply["kind"] == "answer"
    assert reply["text"] == "Here's a plan that finishes your degree in May 2027 with every class in the evening:"
    assert reply["planTerm"] == "Spring 2027"
    assert [(row["code"], row["meta"], row["fulfills"]) for row in reply["plan"]] == [
        ("CS 691", "Mon 18:10–20:55", "Capstone"), ("CS 680", "Wed 18:10–20:55", "Elective 5 of 5")]
    assert reply["follow"] == ("Before you can register, your advisor must sign your capstone pre-approval form. "
                               "Spring registration opens Nov 3.")
    assert reply["sources"] == PLAN_SOURCES
    assert [action["label"] for action in reply["actions"]] == ["Add to degree plan", "Send to advisor"]

    what_if = ask(client, "What happens if I take only one course in Spring?", data["thread"]["id"])
    assert what_if["text"] == ("Taking only one course in Spring would move your last elective to Summer 2027, so you "
                               "would graduate in August instead of May. Summer electives run less often, so check "
                               "what's offered before choosing this path.")


def test_other_intents(client):
    login(client, AMARA)
    conflict = ask(client, "Can I take CS 608 and CS 675 together?")
    assert conflict["text"].startswith("Yes. CS 608 meets Mon 18:10–20:55 and CS 675 meets Thu 10:00–12:45")
    assert ask(client, "What are the prerequisites for CS 691?")["text"] == \
        "Yes. You meet the prerequisites for CS 691 Capstone Project."
    assert ask(client, "Can I take CS 680?")["text"] == \
        "Yes. You meet the prerequisites for CS 680 Machine Learning once you finish CS 675 this term."
    electives = ask(client, "Compare my elective options")
    assert [row["code"] for row in electives["plan"]] == ["CS 680", "CS 665"]  # evening first
    on_track = ask(client, "Am I on track to graduate?")
    assert on_track["text"].startswith("You have 21 of 36 credits, with 9 in progress.")
    assert "capstone still needs your advisor's pre-approval" in on_track["text"]
    assert "Hi Dr. Sarah Smith" in ask(client, "Draft an email to my advisor")["text"]
    assert ask(client, "Hello there")["text"] == FALLBACK


def test_blocked_topic_never_calls_engine(client, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(claude_engine, "answer", lambda *args: calls.append(args))
    login(client, AMARA)
    reply = ask(client, "Can you help me with my visa paperwork?")
    assert reply["kind"] == "handoff" and reply["text"].startswith("I can't help with visa and immigration.")
    assert reply["actions"] == [{"label": "Book a meeting", "to": "/student/book-meeting"}]
    assert calls == []


def test_daily_limit_and_disabled(client, new_student, ai_settings):
    login(client, new_student().email)
    ai_settings["dailyLimit"] = 2
    ask(client, "Am I on track?")
    ask(client, "Plan my next term")
    assert_envelope(client.post(f"{BASE}/threads", json={"text": "One more?"}), 429, "DAILY_LIMIT")
    assert client.get(f"{BASE}/context").json()["remainingToday"] == 0

    ai_settings["features"]["advisor"] = False
    assert_envelope(client.post(f"{BASE}/threads", json={"text": "Hi"}), 403, "AI_DISABLED")
    assert client.get(f"{BASE}/context").json()["enabled"] is False


def test_validation(client):
    login(client, AMARA)
    assert_envelope(client.post(f"{BASE}/threads", json={"text": "   "}), 422, "VALIDATION_ERROR")
    assert_envelope(client.post(f"{BASE}/threads", json={"text": "x" * 1001}), 422, "VALIDATION_ERROR")


def test_rating_and_flag(client, db):
    login(client, AMARA)
    reply = ask(client, "Plan my Spring semester")
    rating = f"{BASE}/messages/{reply['id']}/rating"
    assert client.post(rating, json={"helpful": True}).status_code == 204
    thread = client.get(f"{BASE}/threads").json()["threads"][0]
    stored = client.get(f"{BASE}/threads/{thread['id']}").json()["messages"][1]
    assert stored["rating"] == 1
    assert client.post(rating, json={"helpful": None}).status_code == 204
    assert client.get(f"{BASE}/threads/{thread['id']}").json()["messages"][1]["rating"] is None
    assert_envelope(client.post(f"{BASE}/messages/801/rating", json={"helpful": True}), 400, "BAD_REQUEST")

    flag = client.post(f"{BASE}/messages/{reply['id']}/flag", json={"issue": "CS 680 isn't offered at night."})
    assert flag.status_code == 201
    row = db.get(AiFlag, flag.json()["id"])
    assert row.status == "Open" and row.source == "student" and row.question == "Plan my Spring semester"
    assert_envelope(client.post(f"{BASE}/messages/{reply['id']}/flag", json={"issue": "Again"}), 409, "CONFLICT")


def test_ownership_and_delete(client, db, new_student):
    login(client, AMARA)
    reply = ask(client, "Am I on track?")
    thread_id = client.get(f"{BASE}/threads").json()["threads"][0]["id"]
    flag_id = client.post(f"{BASE}/messages/{reply['id']}/flag", json={"issue": "Wrong"}).json()["id"]

    login(client, new_student().email)
    assert_envelope(client.get(f"{BASE}/threads/{thread_id}"), 404, "NOT_FOUND")
    assert_envelope(client.delete(f"{BASE}/threads/{thread_id}"), 404, "NOT_FOUND")
    assert_envelope(client.post(f"{BASE}/messages/{reply['id']}/rating", json={"helpful": True}), 404, "NOT_FOUND")
    ask(client, "Hello")
    assert client.delete(f"{BASE}/threads").status_code == 204
    assert client.get(f"{BASE}/threads").json()["threads"] == []

    login(client, AMARA)
    assert client.delete(f"{BASE}/threads/{thread_id}").status_code == 204
    assert_envelope(client.get(f"{BASE}/threads/{thread_id}"), 404, "NOT_FOUND")
    assert db.query(AiMessage).filter(AiMessage.thread_id == thread_id).count() == 0
    flag = db.get(AiFlag, flag_id)
    assert flag.message_id is None and flag.answer == reply["text"]


def test_claude_reply_is_validated(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    def fake(db_, student, text, ctx, history):
        return {"kind": "answer", "text": "Here's what I suggest.", "input_tokens": 120, "output_tokens": 40,
                "payload": {"planTerm": "Spring 2027", "sources": ["Course catalog 2026–27"],
                            "plan": [{"code": "CS 999", "fulfills": "Elective"}, {"code": "cs691", "fulfills": "Capstone"}]}}
    monkeypatch.setattr(claude_engine, "answer", fake)
    login(client, AMARA)
    reply = ask(client, "Plan my Spring 2027 semester")
    assert reply["text"] == "Here's what I suggest."
    assert [row["code"] for row in reply["plan"]] == ["CS 691"]  # unknown CS 999 dropped
    stored = db.get(AiMessage, reply["id"])
    assert stored.engine == "Claude" and stored.input_tokens == 120 and stored.output_tokens == 40


def test_claude_failures_fall_back_to_rules(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    login(client, AMARA)

    def broken(*args):
        raise RuntimeError("API unavailable")
    monkeypatch.setattr(claude_engine, "answer", broken)
    reply = ask(client, "Hello")
    assert reply["text"] == FALLBACK and db.get(AiMessage, reply["id"]).engine == "Rules"

    def slow(*args):
        raise anthropic.APITimeoutError.__new__(anthropic.APITimeoutError)
    monkeypatch.setattr(claude_engine, "answer", slow)
    assert ask(client, "Hello")["text"] == f"{FALLBACK}\n\n{ai.SLOW_NOTE}"

    monkeypatch.setattr(claude_engine, "answer", lambda *args: None)  # refusal
    assert ask(client, "Hello")["text"] == FALLBACK


def test_claude_engine_tools(client, db, monkeypatch):
    """Runs claude_engine.answer() against a fake client: checks the request and that the plan comes from propose_plan."""
    seen = {}

    def tool_runner(**kwargs):
        seen.update(kwargs)
        tools = {tool.to_dict()["name"]: tool for tool in kwargs["tools"]}
        tools["get_degree_audit"].call({})
        tools["propose_plan"].call({"term": "Spring 2027", "course_codes": ["CS 691", "CS 680", "CS 999"],
                                    "notes": "Your capstone needs pre-approval."})
        usage = SimpleNamespace(input_tokens=50, output_tokens=20, cache_creation_input_tokens=0, cache_read_input_tokens=30)
        yield SimpleNamespace(stop_reason="end_turn", usage=usage,
                              content=[SimpleNamespace(type="text", text="Take CS 691 and CS 680 in Spring.")])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(tool_runner=tool_runner)))
    monkeypatch.setattr(claude_engine, "client", lambda: fake)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    login(client, AMARA)
    reply = ask(client, "Plan my Spring 2027 semester")

    assert seen["model"] == "claude-opus-5-5" and seen["thinking"] == {"type": "adaptive"}
    assert seen["fallbacks"] == "default" and seen["betas"] == ["server-side-fallback-2026-07-01"]
    assert seen["cache_control"] == {"type": "ephemeral"}
    assert [tool.to_dict()["name"] for tool in seen["tools"]] == [
        "get_degree_audit", "search_catalog", "get_course_sections", "check_prerequisites",
        "get_transcript", "get_schedule", "propose_plan"]
    assert seen["messages"][-1]["content"].startswith("Plan my Spring 2027 semester\n\n(Today is 2026-10-01.")
    assert reply["text"] == "Take CS 691 and CS 680 in Spring."
    assert [(row["code"], row["fulfills"]) for row in reply["plan"]] == [("CS 691", "Capstone"), ("CS 680", "Electives")]
    assert reply["follow"] == "Your capstone needs pre-approval."
    assert reply["sources"] == ["Degree audit · updated today", "Spring 2027 schedule"]
    assert db.get(AiMessage, reply["id"]).input_tokens == 80


def test_dashboard_recommendation(client):
    recommend._cache.clear()
    login(client, AMARA)
    recommendation = client.get("/api/v1/students/me/dashboard").json()["recommendation"]
    assert recommendation["title"] == "Spring 2027 recommendation"
    assert recommendation["text"].startswith("After this semester you will have 6 credits left. Taking CS 691 Capstone "
                                             "Project and CS 680 Machine Learning in Spring 2027 would finish your degree in May 2027.")
