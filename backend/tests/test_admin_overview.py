"""Admin platform overview service (spec 30). conftest pins today to 2026-10-01 (Thursday, Fall 2026 week 6).
Counting tests look at a quiet week (QUIET) so other tests' sign-ins and the seed don't move the numbers."""
import csv
import io
import secrets
from datetime import date, datetime, time, timedelta

import pytest

from conftest import login
from core.time import local_zone, today
from database import SessionLocal
from models import (Advisor, AuditEvent, AdvisorStudentAssignment, AiFlag, AiMessage, AiThread, ApprovalRequest, Student,
                    UserSession)
from services import admin_overview as ov
from services import mailer
from test_foundation import assert_envelope

QUIET = date(2031, 3, 5)  # a Wednesday with no data
OVERVIEW, CSV = "/api/v1/admin/overview", "/api/v1/admin/overview.csv"
JORDAN = "jordan.lee@pac.edu"


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), local_zone())


@pytest.fixture
def added():
    """added(row, ...) inserts rows and deletes them (in reverse) after the test."""
    rows = []

    def add(*items):
        with SessionLocal() as db:
            for item in items:
                db.add(item)
                db.flush()
                rows.append((type(item), db.identity_key(instance=item)[1]))
            db.commit()

    yield add
    with SessionLocal() as db:
        for model, key in reversed(rows):
            row = db.get(model, key if len(key) > 1 else key[0])
            if row is not None:
                db.delete(row)
                db.flush()  # one at a time: the models have no relationships to order the deletes by
        db.commit()


def session_for(user_id: int, created: datetime) -> UserSession:
    return UserSession(user_id=user_id, token_hash=secrets.token_hex(32), created_at=created,
                       expires_at=created + timedelta(hours=2), revoked_at=created + timedelta(hours=1))


def test_helpers():
    assert ov._fmt(1284) == "1,284"
    assert ov._signed(86) == "+86" and ov._signed(-12) == "−12" and ov._signed(0) == "+0"
    assert ov._pct(1, 3) == 33 and ov._pct(1, 3, dp=1) == 33.3 and ov._pct(1, 0) is None
    assert ov.week_start(date(2026, 10, 1)) == date(2026, 9, 28)


def test_active_students(db, make_user, added):
    a, b = make_user("student"), make_user("student")
    advisor = make_user("advisor")
    added(session_for(a.user_id, at(QUIET)), session_for(a.user_id, at(QUIET, 9)),  # counted once
          session_for(b.user_id, at(QUIET - timedelta(days=40))),                    # previous window only
          session_for(advisor.user_id, at(QUIET)))                                    # not a student
    stat = ov.active_students(db, QUIET)
    assert (stat["value"], stat["tag"], stat["tone"], stat["count"]) == ("1", "+0", "teal", 1)
    later = ov.active_students(db, QUIET + timedelta(days=35))  # a's sign-in is now the previous window
    assert (later["value"], later["tag"], later["tone"]) == ("0", "−1", "amber")


def test_weekly_active(db, make_user, added):
    a, b = make_user("student"), make_user("student")
    monday = ov.week_start(QUIET)
    added(session_for(a.user_id, at(monday - timedelta(days=6))),  # last week
          session_for(a.user_id, at(monday)), session_for(b.user_id, at(QUIET)))
    data = ov.weekly_active(db, day=QUIET)
    assert [w["label"] for w in data["weeks"]] == ["Jan 27", "Feb 3", "Feb 10", "Feb 17", "Feb 24", "Mar 3"]
    assert [w["value"] for w in data["weeks"]] == [0, 0, 0, 0, 1, 2]
    assert [w["highlight"] for w in data["weeks"]] == [False] * 5 + [True]
    assert data["change"] == {"pct": 100, "direction": "up", "text": "Up 100% vs. last week"}

    week_after = ov.weekly_active(db, day=QUIET + timedelta(days=7))
    assert week_after["change"] == {"pct": 100, "direction": "down", "text": "Down 100% vs. last week"}
    assert ov.weekly_active(db, day=QUIET - timedelta(days=7))["change"]["text"] == "No activity the week before"
    assert ov._change(3, 3)["text"] == "Same as last week"


def test_ai_quality_and_questions(db, added):
    empty = ov.ai_quality(db, QUIET)
    assert [row["pct"] for row in empty] == [None, None, None]
    assert empty[0]["note"] == "From 0 student ratings this week"

    added(AiThread(id=99001, student_id=101, title="Quality test", created_at=at(QUIET), updated_at=at(QUIET)))
    added(AiMessage(id=99101, thread_id=99001, role="user", text="Q", created_at=at(QUIET)),
          AiMessage(id=99102, thread_id=99001, role="assistant", text="A1", rating=1, created_at=at(QUIET)),
          AiMessage(id=99103, thread_id=99001, role="assistant", text="A2", rating=-1, created_at=at(QUIET)),
          AiMessage(id=99104, thread_id=99001, role="assistant", text="A3", created_at=at(QUIET)),
          AiMessage(id=99105, thread_id=99001, role="assistant", kind="handoff", text="A4", created_at=at(QUIET)),
          AiFlag(student_id=101, question="Q", answer="A3", issue="Wrong", created_at=at(QUIET)))
    helpful, handed, flagged = ov.ai_quality(db, QUIET)
    assert (helpful["pct"], helpful["note"]) == (50, "From 2 student ratings this week")
    assert handed["pct"] == 25 and handed["tone"] == "violet"
    assert (flagged["pct"], flagged["note"]) == (25.0, "1 answer this week")

    assert ov.ai_questions(db, 1, QUIET) == {"value": "1", "note": "About 1 per active student"}
    assert ov.ai_questions(db, 0, QUIET)["note"] == "No active students yet"


def test_workload(db, make_user, added):
    advisor_user = make_user("advisor")
    students = [make_user("student") for _ in range(2)]
    added(Advisor(advisor_id=99201, user_id=advisor_user.user_id, capacity=3))
    added(*[Student(student_id=99300 + i, user_id=u.user_id, name=u.name, email=u.email, program_id=1)
            for i, u in enumerate(students)])
    added(AdvisorStudentAssignment(student_id=99300, advisor_id=99201),
          AdvisorStudentAssignment(student_id=99301, advisor_id=99201),
          ApprovalRequest(student_id=99300, advisor_id=99201, type="plan", title="Pending plan"),
          ApprovalRequest(student_id=99301, advisor_id=99201, type="plan", title="Decided plan", status="approved",
                          created_at=at(today() - timedelta(days=3)),
                          decided_at=at(today() - timedelta(days=3)) + timedelta(hours=36)))

    row = next(r for r in ov.workload(db) if r["advisorId"] == 99201)
    assert row == {"advisorId": 99201, "userId": advisor_user.user_id, "name": advisor_user.name, "advisees": 2,
                   "capacity": 3, "waiting": 1, "avgReply": "1.5 days", "loadPct": 67, "load": "OK"}

    with SessionLocal() as session:
        session.get(Advisor, 99201).capacity = 2
        session.commit()
    row = next(r for r in ov.workload(db) if r["advisorId"] == 99201)
    assert (row["load"], row["loadPct"]) == ("Over", 100)
    sarah = next(r for r in ov.workload(db) if r["advisorId"] == 201)
    assert sarah["capacity"] == 45 and sarah["load"] == "OK"


def test_summary_tiles(db):
    advisors = ov.advisors_stat(db)
    assert advisors["note"] == "1 invited, not yet signed in"  # Priya Natarajan (user 5)
    plans = ov.plans_waiting(db)
    assert plans["key"] == "plansWaiting" and plans["note"] == "Spring registration opens Nov 3"
    assert ov.subtitle(db) == "Pace University · Fall 2026 · Week 6"
    stat = ov.ai_questions_stat(db, {"value": "3", "note": "x"})
    assert (stat["tag"], stat["tone"]) == ("Week 6", "indigo")


def test_systems(db):
    rows = {row["key"]: row for row in ov.systems(db)}
    assert list(rows) == ["csv", "catalog", "ics", "mail"]
    assert rows["csv"]["status"] == "Healthy"  # seeded import today 06:00 (spec 35 tests may import later today)
    assert rows["csv"]["detail"].startswith("Grades and enrollments · last import today ")
    assert rows["catalog"]["detail"].startswith("2026–27 catalog · ") and rows["catalog"]["status"] == "Healthy"
    assert rows["ics"]["detail"].endswith("subscribed")
    assert rows["mail"]["status"] == "Healthy"


def test_overview_and_csv(db):
    data = ov.overview(db)
    assert list(data) == ["subtitle", "stats", "weeklyActive", "aiQuestions", "aiQuality", "systems", "advisors"]
    assert [s["key"] for s in data["stats"]] == ["activeStudents", "advisors", "aiQuestions", "plansWaiting"]
    assert "count" not in data["stats"][0]
    assert data["stats"][2]["value"] == data["aiQuestions"]["value"]

    rows = list(csv.reader(io.StringIO(ov.overview_csv(data))))
    titles = [r[0] for r in rows if len(r) == 1]
    assert titles == ["Summary", "Weekly active students", "AI advisor quality", "System status", "Advisor workload"]
    assert rows[0] == ["Acadmate platform overview", data["subtitle"]]
    assert ov.csv_filename() == "acadmate-overview-2026-10-01.csv"


# --- HTTP ---------------------------------------------------------------------------------------------------------

def test_overview_needs_an_admin(client, as_user):
    for path in (OVERVIEW, CSV):
        assert_envelope(client.get(path), 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for path in (OVERVIEW, CSV):
            assert_envelope(client.get(path), 403, "FORBIDDEN")


def test_overview_endpoint(client):
    login(client, JORDAN)
    response = client.get(OVERVIEW)
    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["subtitle", "stats", "weeklyActive", "aiQuestions", "aiQuality", "systems", "advisors"]
    assert body["subtitle"] == "Pace University · Fall 2026 · Week 6"
    assert "count" not in body["stats"][0]
    assert set(body["advisors"][0]) == {"advisorId", "userId", "name", "advisees", "capacity", "waiting", "avgReply",
                                        "loadPct", "load"}
    weeks = body["weeklyActive"]["weeks"]
    assert len(weeks) == 6 and [w["highlight"] for w in weeks] == [False] * 5 + [True]
    handed = body["aiQuality"][1]["pct"]
    assert handed is None or isinstance(handed, int)


def test_overview_shows_mail_degraded(client):
    login(client, JORDAN)
    mailer.record_failure()
    try:
        mail = next(s for s in client.get(OVERVIEW).json()["systems"] if s["key"] == "mail")
        assert mail == {"key": "mail", "name": "Email notifications", "detail": "Delays of up to 15 minutes",
                        "status": "Degraded"}
    finally:
        mailer._failures.clear()


def test_overview_csv_endpoint(client, db):
    login(client, JORDAN)
    response = client.get(CSV)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="acadmate-overview-2026-10-01.csv"' in response.headers["content-disposition"]
    assert response.text.startswith("Acadmate platform overview")
    event = (db.query(AuditEvent).filter(AuditEvent.action == "report.export", AuditEvent.actor_id == 3)
             .order_by(AuditEvent.id.desc()).first())
    assert event is not None and event.target_id == "overview"
    db.delete(event)
    db.commit()


def test_seeded_overview(db):
    """seed_overview gives every block real data (the current week also counts other tests' sign-ins)."""
    weeks = ov.weekly_active(db)["weeks"]
    assert [w["value"] for w in weeks[:5]] == [2, 3, 3, 4, 4] and weeks[5]["value"] >= 5
    rows = {r["advisorId"]: r for r in ov.workload(db)}
    assert (rows[203]["advisees"], rows[203]["capacity"], rows[203]["waiting"], rows[203]["load"]) == (3, 2, 2, "Over")
    assert (rows[201]["capacity"], rows[201]["waiting"], rows[201]["avgReply"], rows[201]["load"]) == (45, 5, "1.5 days", "OK")  # requests 1706-1708 (seed_advisees), Amara's 1709 and Lina's 1710 (seed_student_record)
    helpful, handed, flagged = ov.ai_quality(db)
    assert helpful["pct"] is not None and handed["pct"] is not None and flagged["pct"] is not None
    plans = ov.plans_waiting(db)
    assert int(plans["value"]) >= 2 and plans["tag"] == "Rising"


# --- Phase 5 gaps ---------------------------------------------------------------------------------------------------

def test_real_sign_in_counts(client, db, make_user):
    def figures():
        db.expire_all()
        return ov.active_students(db)["count"], ov.weekly_active(db)["weeks"][-1]["value"]

    before = figures()
    assert login(client, make_user("student").email).status_code == 200
    assert figures() == (before[0] + 1, before[1] + 1)
    assert login(client, make_user("advisor").email).status_code == 200
    assert figures() == (before[0] + 1, before[1] + 1)  # only students count


def test_week_buckets_follow_school_time_across_dst(db, make_user, added):
    """DST ends Sun Nov 1 2026: 23:30 that night is 04:30Z on Monday, but it still belongs to the Oct 26 week."""
    a, b = make_user("student"), make_user("student")
    added(session_for(a.user_id, datetime(2026, 11, 1, 23, 30, tzinfo=local_zone())),
          session_for(b.user_id, datetime(2026, 11, 2, 0, 30, tzinfo=local_zone())))
    weeks = {w["label"]: w["value"] for w in ov.weekly_active(db, day=date(2026, 11, 4))["weeks"]}
    assert (weeks["Oct 26"], weeks["Nov 2"]) == (1, 1)  # no other sign-ins in these weeks


def test_every_approval_type_counts(db, added):
    before = int(ov.plans_waiting(db)["value"])
    added(ApprovalRequest(student_id=106, advisor_id=203, type="form", title="Capstone pre-approval"))
    db.expire_all()
    assert int(ov.plans_waiting(db)["value"]) == before + 1


def test_csv_round_trip(db):
    data = ov.overview(db)
    data["aiQuality"][0] = {**data["aiQuality"][0], "pct": None}
    rows = list(csv.reader(io.StringIO(ov.overview_csv(data))))
    start = rows.index(["Advisor workload"])
    assert rows[start + 1] == ["Advisor", "Advisees", "Capacity", "Waiting", "Avg. reply", "Load"]
    workload = rows[start + 2:start + 2 + len(data["advisors"])]
    assert [r[0] for r in workload] == [a["name"] for a in data["advisors"]]
    assert next(r for r in workload if r[0] == "Prof. Daniel Kim")[-1] == "Over"
    quality = rows[rows.index(["AI advisor quality"]) + 2]
    assert quality[0] == "Rated helpful" and quality[1] == ""


def test_overview_without_a_current_term(client, db, monkeypatch):
    monkeypatch.setattr(ov, "current_term", lambda db: None)
    assert ov.subtitle(db) == "Pace University"
    assert ov.ai_questions_stat(db, {"value": "1", "note": "x"})["tag"] is None
    login(client, JORDAN)
    body = client.get(OVERVIEW).json()
    assert body["subtitle"] == "Pace University" and body["stats"][2]["tag"] is None
