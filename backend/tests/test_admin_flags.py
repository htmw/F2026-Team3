"""Admin flagged AI answers (/admin/ai/flags, specs 30 and 34) plus the overview helpers from spec 30 Phase 0.
conftest pins today to 2026-10-01."""
from datetime import datetime, time, timedelta

import pytest

from conftest import login
from core.time import local_zone, today
from database import SessionLocal
from models import AiFlag, AuditEvent, Term
from services import mailer
from services.catalog import term_week
from test_foundation import assert_envelope

FLAGS = "/api/v1/admin/ai/flags"
JORDAN = "jordan.lee@pac.edu"


@pytest.fixture
def flag_id():
    """A throwaway open flag on Amara's account, created yesterday; removed afterwards."""
    with SessionLocal() as db:
        flag = AiFlag(student_id=101, question="Can I take CS 691 without the prerequisite?", answer="Yes.",
                      issue="CS 691 needs CS 620 first.", source="student", status="Open",
                      created_at=datetime.combine(today() - timedelta(days=1), time(12), local_zone()))  # yesterday noon
        db.add(flag)
        db.commit()
        made = flag.id
    yield made
    with SessionLocal() as db:
        db.query(AuditEvent).filter(AuditEvent.target_type == "ai_flag", AuditEvent.target_id == str(made)).delete()
        db.query(AiFlag).filter(AiFlag.id == made).delete()
        db.commit()


def test_flags_need_an_admin(client, as_user):
    assert_envelope(client.get(FLAGS), 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        assert_envelope(client.get(FLAGS), 403, "FORBIDDEN")


def test_list_open_flags(client, flag_id):
    login(client, JORDAN)
    body = client.get(FLAGS).json()
    row = next(f for f in body["flags"] if f["id"] == flag_id)
    assert row == {"id": flag_id, "q": "Can I take CS 691 without the prerequisite?", "why": "CS 691 needs CS 620 first.",
                   "answer": "Yes.", "when": "Yesterday", "student": "Amara O.", "source": "Reported by student",
                   "status": "Open"}
    assert all(f["status"] == "Open" for f in body["flags"])
    assert body["counts"]["open"] == len(body["flags"])
    with SessionLocal() as db:
        created = [db.get(AiFlag, f["id"]).created_at for f in body["flags"]]
    assert created == sorted(created, reverse=True)


def test_resolve_and_reopen(client, flag_id):
    login(client, JORDAN)
    before = client.get(FLAGS).json()["counts"]

    resolved = client.post(f"{FLAGS}/{flag_id}/resolve", json={"resolution": "Dismissed", "note": "Advice was fine"})
    assert resolved.status_code == 200 and resolved.json()["flag"]["status"] == "Dismissed"
    assert flag_id not in [f["id"] for f in client.get(FLAGS).json()["flags"]]
    counts = client.get(f"{FLAGS}?status=Dismissed").json()["counts"]
    assert counts["open"] == before["open"] - 1 and counts["dismissed"] == before["dismissed"] + 1
    assert_envelope(client.post(f"{FLAGS}/{flag_id}/resolve", json={"resolution": "Resolved"}), 409, "CONFLICT")

    with SessionLocal() as db:
        flag = db.get(AiFlag, flag_id)
        assert flag.resolved_by == 3 and flag.resolved_at is not None
        event = db.query(AuditEvent).filter(AuditEvent.action == "ai.flag.resolve",
                                            AuditEvent.target_id == str(flag_id)).one()
        assert event.changes == {"status": ["Open", "Dismissed"], "note": "Advice was fine"}

    reopened = client.post(f"{FLAGS}/{flag_id}/reopen")
    assert reopened.status_code == 200 and reopened.json()["flag"]["status"] == "Open"
    assert_envelope(client.post(f"{FLAGS}/{flag_id}/reopen"), 409, "CONFLICT")
    with SessionLocal() as db:
        assert db.get(AiFlag, flag_id).resolved_by is None


def test_flag_validation_and_unknown(client):
    login(client, JORDAN)
    assert_envelope(client.post(f"{FLAGS}/901/resolve", json={"resolution": "Fixed"}), 422, "VALIDATION_ERROR")
    assert_envelope(client.get(f"{FLAGS}?status=Closed"), 422, "VALIDATION_ERROR")
    assert_envelope(client.post(f"{FLAGS}/999999/reopen"), 404, "NOT_FOUND")


def test_all_lists_every_status(client, flag_id):
    login(client, JORDAN)
    client.post(f"{FLAGS}/{flag_id}/resolve", json={"resolution": "Resolved"})
    statuses = {f["id"]: f["status"] for f in client.get(f"{FLAGS}?status=All").json()["flags"]}
    assert statuses[flag_id] == "Resolved" and statuses[901] == "Open"


def test_term_week(db):
    assert term_week(db.query(Term).filter(Term.name == "Fall 2026").one()) == 6  # Aug 24 → Oct 1
    assert term_week(db.query(Term).filter(Term.name == "Spring 2027").one()) == 1  # not started yet


def test_mailer_health():
    assert mailer.health()[0] == "Healthy"
    mailer.record_failure()
    try:
        assert mailer.health() == ("Degraded", "Delays of up to 15 minutes")
    finally:
        mailer._failures.clear()
