"""Advisor reports (spec 26). conftest pins today to Thu 2026-10-01 (Fall 2026, term 4). Dr. Smith's decided requests
1701-1703 took 24, 36 and 48 hours (seed_overview)."""
import csv
import io

from database import SessionLocal
from models import Advisor, AuditEvent
from services.advisees import attention_count
from test_foundation import assert_envelope

REPORTS = "/api/v1/advisor/reports"
FALL_2026, SPRING_2026, SPRING_2027 = 4, 2, 5


def test_access(client, as_user):
    assert_envelope(client.get(REPORTS), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(REPORTS), 403, "FORBIDDEN")
    as_user("advisor")
    assert_envelope(client.get(f"{REPORTS}?term={SPRING_2027}"), 400, "BAD_REQUEST")  # a future term
    assert_envelope(client.get(f"{REPORTS}?term=999"), 404, "NOT_FOUND")


def test_current_term(client, as_user):
    as_user("advisor")
    data = client.get(REPORTS).json()
    assert (data["currentTermId"], data["termId"], data["termLabel"]) == (FALL_2026, FALL_2026, "Fall 2026")
    assert [t["label"] for t in data["terms"]] == ["Fall 2026", "Summer 2026", "Spring 2026", "Fall 2025"]

    stats = {s["label"]: s for s in data["stats"]}
    assert (stats["Advisees"]["value"], stats["Advisees"]["note"]) == ("8", "Across 1 program")
    assert (stats["Plans approved"]["value"], stats["Plans approved"]["note"]) == ("2", "3 still pending")
    assert (stats["Avg. response time"]["value"], stats["Avg. response time"]["note"]) == (
        "1.5 days", "First term with decisions")
    with SessionLocal() as db:
        attention = attention_count(db, db.get(Advisor, 201))
    assert stats["Need attention"]["value"] == str(attention)
    assert stats["Need attention"]["note"] == f"{round(attention / 8 * 100)}% of advisees"

    tabs = {t["label"]: t["count"] for t in client.get("/api/v1/advisor/advisees").json()["tabs"]}
    assert [(r["label"], r["count"], r["tone"]) for r in data["byStatus"]] == [
        ("On track", tabs["On track"], "accent"), ("Needs attention", tabs["Needs attention"], "amber"),
        ("Graduating", tabs["Graduating"], "violet")]

    assert [w["label"] for w in data["weeks"]] == ["W1", "W2", "W3", "W4", "W5", "W6"]
    assert data["weeks"][-1]["value"] >= 3  # this week: today's confirmed meetings with Jonah, Priya and Amara

    check = {row["name"]: row for row in data["checkOn"]}
    assert (check["Marcus T."]["action"], check["Marcus T."]["to"]) == ("Review request", "/advisor/approvals?id=1708")
    assert check["Marcus T."]["reason"] == "Requested a drop that ends full-time status"
    assert (check["Lina H."]["action"], check["Lina H."]["to"]) == ("Review plan", "/advisor/approvals?id=1710")
    assert (check["Daniel O."]["action"], check["Daniel O."]["to"]) == ("Review request", "/advisor/approvals?id=1707")
    assert len(data["checkOn"]) <= 6


def test_past_term(client, as_user):
    as_user("advisor")
    data = client.get(f"{REPORTS}?term={SPRING_2026}").json()
    stats = {s["label"]: s for s in data["stats"]}
    assert (stats["Avg. response time"]["value"], stats["Avg. response time"]["note"]) == ("—", "No decisions this term")
    assert (stats["Plans approved"]["value"], stats["Plans approved"]["note"]) == ("0", "All cleared")
    assert [w["label"] for w in data["weeks"]] == ["W12", "W13", "W14", "W15", "W16", "W17"]
    assert all(w["value"] == 0 for w in data["weeks"])


def test_csv_export(client, as_user):
    as_user("advisor")
    response = client.get(f"{REPORTS}.csv")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="advisor-report-fall-2026-2026-10-01.csv"'
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["student", "program", "credits_earned", "credits_required", "gpa", "status", "risk",
                       "expected_graduation", "pending_requests", "last_contact", "next_meeting"]
    assert len(rows) == 9  # 8 advisees
    amara = next(row for row in rows if row[0] == "Amara Okafor")
    assert (amara[1], amara[2], amara[3], amara[4], amara[8], amara[10]) == (
        "M.S. Computer Science", "21", "36", "3.73", "1", "Today · 15:00")
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter_by(action="report.export").order_by(AuditEvent.id.desc()).first()
        assert (event.summary, event.target_type) == ("Exported the Fall 2026 advisee report", "report")
    assert_envelope(client.get(f"{REPORTS}.csv?term={SPRING_2027}"), 400, "BAD_REQUEST")
