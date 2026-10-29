"""Advisee risk rules (used by the advisor dashboard and badges) and the advisees list (spec 21)."""
from datetime import date, datetime, time, timedelta, timezone

from conftest import login
from core.time import local_zone, now
from models import Advisor, ApprovalRequest, Meeting, Student, User
from services import advisees
from services.advisees import RiskContext, risk_for, short_name
from test_foundation import assert_envelope


def student(sid=1):
    return Student(student_id=sid, user_id=sid, name="Test Person", program_id=1)


def ctx(**overrides):
    base = RiskContext(users={1: User(first_name="Test", name="Test Person")}, term_gpas={1: [3.6, 3.7]},
                       cumulative={1: 3.65}, last_sign_in={1: now()}, has_next_plan={1})
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def request(ok=True, kind=None, credits_after=12):
    checks = [{"ok": ok, "blocking": True, "text": "Project summary is missing"}]
    payload = {"kind": kind, "creditsAfter": credits_after} if kind else {}
    return ApprovalRequest(type="other" if kind else "form", title="Capstone form", payload=payload,
                           precheck={"ok": ok, "checks": checks})


def test_short_name():
    assert short_name("Amara Okafor") == "Amara O." and short_name("Plato") == "Plato"


def test_low_by_default():
    assert risk_for(student(), ctx()) == ("Low", None)


def test_high_rules():
    level, flag = risk_for(student(), ctx(term_gpas={1: [3.4, 2.9]}))
    assert level == "High" and flag == "Term GPA fell from 3.4 to 2.9."
    assert risk_for(student(), ctx(missed={1: 3}))[0] == "High"
    assert risk_for(student(), ctx(missed={1: 2}))[0] == "Low"
    level, flag = risk_for(student(), ctx(pending={1: [request(ok=False, kind="drop", credits_after=6)]}))
    assert level == "High" and "6 credits" in flag


def test_medium_rules():
    stale = now() - timedelta(days=30)
    assert risk_for(student(), ctx(last_sign_in={1: stale}, has_next_plan=set()))[0] == "Medium"
    assert risk_for(student(), ctx(last_sign_in={1: stale}))[0] == "Low"  # has a plan for next term
    level, flag = risk_for(student(), ctx(pending={1: [request(ok=False)]}))
    assert level == "Medium" and flag == "Capstone form: project summary is missing"
    assert risk_for(student(), ctx(cumulative={1: 2.8}, term_gpas={1: [2.8]}))[0] == "Medium"


def test_seeded_caseload(db):
    _, rows = advisees.levels(db, db.get(Advisor, 201))
    by_name = {s.name: level for s, level, _ in rows}
    assert len(rows) == 8
    assert {n for n, level in by_name.items() if level == "High"} == {"Marcus Tran", "Lina Haddad"}
    assert {n for n, level in by_name.items() if level == "Medium"} == {"Daniel Osei", "Sam Ruiz"}
    assert advisees.attention_count(db, db.get(Advisor, 201)) == 4


# --- advisees list (spec 21) ----------------------------------------------------------------------------------------

ADVISEES = "/api/v1/advisor/advisees"


def meeting_at(day, hour):
    start = datetime.combine(day, time(hour), local_zone()).astimezone(timezone.utc)
    return Meeting(starts_at=start)


def test_next_meeting_label():
    day = date(2026, 10, 1)
    assert advisees.next_meeting_label(meeting_at(day, 15), day) == "Today · 15:00"
    assert advisees.next_meeting_label(meeting_at(date(2026, 10, 5), 11), day) == "Oct 5 · 11:00"
    assert advisees.next_meeting_label(None, day) == "Not booked"


def test_status_and_graduating():
    terms = {("Fall", 2026), ("Spring", 2027)}
    assert advisees.is_graduating("December 2026", 27, 9, 36, terms)
    assert not advisees.is_graduating("December 2026", 21, 9, 36, terms)   # credits left over
    assert not advisees.is_graduating("December 2027", 27, 9, 36, terms)   # later term
    assert advisees.status_for("High", True) == "Graduating"
    assert advisees.status_for("Medium", False) == "Needs attention"
    assert advisees.status_for("Low", False) == "On track"


def test_flag_order():
    ready, failing = request(ok=True), request(ok=False)
    assert advisees.flag_for("High", "Term GPA fell.", [ready], False) == "Term GPA fell."
    assert advisees.flag_for("Low", None, [ready], True) == "Capstone form waiting for your approval"
    assert advisees.flag_for("Medium", "Summary missing", [failing], False) == "Summary missing"
    assert advisees.flag_for("Low", None, [], True) == "Final graduation audit due"
    assert advisees.flag_for("Low", None, [], False) is None


def test_list_needs_an_advisor(client, as_user):
    assert_envelope(client.get(ADVISEES), 401, "UNAUTHENTICATED")
    as_user("student")
    assert_envelope(client.get(ADVISEES), 403, "FORBIDDEN")
    as_user("advisor")
    assert_envelope(client.get(f"{ADVISEES}?status=Bogus"), 422, "VALIDATION_ERROR")


def test_seeded_list(client, as_user):
    as_user("advisor")
    data = client.get(ADVISEES).json()
    assert data["subtitle"] == "8 students · Computer Science graduate programs" and data["total"] == 8
    assert {t["label"]: t["count"] for t in data["tabs"]} == \
        {"All": 8, "Needs attention": 4, "On track": 3, "Graduating": 1}
    names = [r["fullName"] for r in data["rows"]]
    assert names[:4] == ["Lina Haddad", "Marcus Tran", "Daniel Osei", "Sam Ruiz"]  # High, then Medium, by last name

    rows = {r["fullName"]: r for r in data["rows"]}
    amara = rows["Amara Okafor"]
    assert (amara["name"], amara["initials"], amara["credits"], amara["requiredCredits"], amara["gpa"]) == \
        ("Amara O.", "AO", 21, 36, "3.73")
    assert (amara["status"], amara["next"], amara["graduates"]) == ("On track", "Today · 15:00", "May 2027")
    assert rows["Priya Shah"]["flag"].endswith("waiting for your approval")
    assert rows["Daniel Osei"]["flag"] == "Capstone pre-approval form: project summary is missing"
    assert rows["Marcus Tran"]["flag"].startswith("Term GPA fell from 3.4 to 2.9")
    jonah = rows["Jonah Weiss"]
    assert (jonah["status"], jonah["flag"], jonah["graduates"]) == ("Graduating", "Final graduation audit due", "Dec 2026")


def test_filters(client, as_user):
    as_user("advisor")
    data = client.get(ADVISEES, params={"q": "pri"}).json()
    assert [r["fullName"] for r in data["rows"]] == ["Priya Shah"]
    assert data["tabs"][0] == {"label": "All", "count": 8}  # counts ignore the filters
    attention = client.get(ADVISEES, params={"status": "Needs attention"}).json()["rows"]
    assert {r["status"] for r in attention} == {"Needs attention"} and len(attention) == 4
    at_risk = client.get(ADVISEES, params={"status": "At risk"}).json()["rows"]
    assert {r["fullName"] for r in at_risk} == {"Lina Haddad", "Marcus Tran"}
    assert client.get(ADVISEES, params={"status": "Graduating", "q": "zzz"}).json()["rows"] == []


def test_only_own_advisees(client):
    login(client, "daniel.kim@pac.edu")
    kim = {r["studentId"] for r in client.get(ADVISEES).json()["rows"]}
    assert kim == {104, 105, 106}
    client.cookies.clear()
    login(client, "sarah.smith@pac.edu")
    smith = {r["studentId"] for r in client.get(ADVISEES).json()["rows"]}
    assert 101 in smith and not smith & kim


def test_badge_matches_attention(client, as_user):
    as_user("advisor")
    tabs = {t["label"]: t["count"] for t in client.get(ADVISEES).json()["tabs"]}
    assert client.get("/api/v1/users/me/badges").json()["badges"]["advisees"] == tabs["Needs attention"]
