"""Admin platform overview (spec 30): usage, AI quality, system status and advisor workload, plus the CSV export.
Every window is built from today() in school time (never now()), so a pinned ACADMATE_TODAY can't split "today"
across two dates. Functions take an optional `day` (default today()) so tests can look at a quiet week.
System status is derived from existing data until spec 35 adds the integrations table."""
import csv
import io
from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.time import local_zone, now, short_date, today
from models import (Advisor, AdvisorStudentAssignment, AiFlag, AiMessage, ApprovalRequest, AuthToken, CalendarFeed,
                    Course, Integration, User, UserSession)
from services import audit, catalog, integrations, mailer, settings
from services.approvals import avg_decision_days
from services.catalog import current_term, next_term, term_week

ACTIVE_DAYS = 30
TREND_DAYS = 7
REPLY_DAYS = 30
OVER_CAPACITY = 0.9
MINUS = "−"


# --- helpers ------------------------------------------------------------------------------------------------------

def _local_start(day: date) -> datetime:
    """Midnight at the start of `day` in the institution's time zone."""
    return datetime.combine(day, time(0), local_zone())


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _week_window(day: date) -> tuple[datetime, datetime]:
    """Monday 00:00 of `day`'s week up to the end of `day` (school time)."""
    return _local_start(week_start(day)), _local_start(day + timedelta(days=1))


def _fmt(n: int) -> str:
    return f"{n:,}"


def _signed(n: int) -> str:
    return f"+{n:,}" if n >= 0 else f"{MINUS}{abs(n):,}"


def _pct(part: int, whole: int, dp: int = 0) -> float | int | None:
    if not whole:
        return None
    value = round(part / whole * 100, dp)
    return value if dp else int(value)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --- summary tiles --------------------------------------------------------------------------------------------------

def _active_student_ids(db: Session, start: datetime, end: datetime) -> set[int]:
    rows = (db.query(UserSession.user_id).join(User, User.user_id == UserSession.user_id)
            .filter(User.role == "student", UserSession.created_at >= start, UserSession.created_at < end)
            .distinct().all())
    return {user_id for (user_id,) in rows}


def active_students(db: Session, day: date | None = None) -> dict:
    """Students who signed in during the last 30 days; the tag compares with the 30 days before."""
    day = day or today()
    end = _local_start(day + timedelta(days=1))
    middle = end - timedelta(days=ACTIVE_DAYS)
    current = len(_active_student_ids(db, middle, end))
    previous = len(_active_student_ids(db, middle - timedelta(days=ACTIVE_DAYS), middle))
    diff = current - previous
    return {"key": "activeStudents", "label": "Active students", "value": _fmt(current), "tag": _signed(diff),
            "tone": "teal" if diff >= 0 else "amber", "note": "Signed in during the last 30 days", "count": current}


def advisors_stat(db: Session) -> dict:
    active = db.query(func.count(User.user_id)).filter(User.role == "advisor", User.is_active.is_(True)).scalar()
    invited = (db.query(func.count(func.distinct(User.user_id))).join(AuthToken, AuthToken.user_id == User.user_id)
               .filter(User.role == "advisor", User.is_active.is_(False), AuthToken.purpose == "invite",
                       AuthToken.used_at.is_(None), AuthToken.expires_at > now())
               .scalar())
    note = f"{invited} invited, not yet signed in" if invited else "All advisors signed in"
    return {"key": "advisors", "label": "Advisors", "value": _fmt(active), "tag": "Faculty", "tone": "gray",
            "note": note}


def ai_questions(db: Session, active: int, day: date | None = None) -> dict:
    """Questions students asked the AI advisor this week (`aiQuestions` in the payload)."""
    start, end = _week_window(day or today())
    n = (db.query(func.count(AiMessage.id))
         .filter(AiMessage.role == "user", AiMessage.created_at >= start, AiMessage.created_at < end).scalar())
    note = f"About {round(n / active)} per active student" if active else "No active students yet"
    return {"value": _fmt(n), "note": note}


def ai_questions_stat(db: Session, questions: dict) -> dict:
    term = current_term(db)
    return {"key": "aiQuestions", "label": "AI questions this week", "value": questions["value"],
            "tag": f"Week {term_week(term)}" if term else None, "tone": "indigo", "note": questions["note"]}


def plans_waiting(db: Session, day: date | None = None) -> dict:
    """Pending approval requests (every type); "Rising" when the last 7 days added more than they decided."""
    day = day or today()
    waiting = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.status == "pending").scalar()
    since = _local_start(day + timedelta(days=1)) - timedelta(days=TREND_DAYS)
    created = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.created_at >= since).scalar()
    decided = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.decided_at >= since).scalar()
    rising = created > decided
    upcoming = next_term(db)
    note = None
    if upcoming is not None and upcoming.registration_opens and upcoming.registration_opens >= day:
        note = f"{upcoming.name.split()[0]} registration opens {short_date(upcoming.registration_opens)}"
    return {"key": "plansWaiting", "label": "Plans awaiting approval", "value": _fmt(waiting),
            "tag": "Rising" if rising else "Steady", "tone": "amber" if rising else "gray", "note": note}


# --- weekly active students ------------------------------------------------------------------------------------------

def _change(last: int, prev: int) -> dict:
    if prev == 0:
        return {"pct": None, "direction": "up" if last > 0 else "flat", "text": "No activity the week before"}
    pct = round((last - prev) / prev * 100)
    if pct == 0:
        return {"pct": 0, "direction": "flat", "text": "Same as last week"}
    direction = "up" if pct > 0 else "down"
    return {"pct": abs(pct), "direction": direction, "text": f"{direction.title()} {abs(pct)}% vs. last week"}


def weekly_active(db: Session, weeks: int = 6, day: date | None = None) -> dict:
    """Distinct students with a sign-in in each of the last `weeks` weeks (Monday to Sunday, school time)."""
    day = day or today()
    mondays = [week_start(day) - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    rows = (db.query(UserSession.user_id, UserSession.created_at).join(User, User.user_id == UserSession.user_id)
            .filter(User.role == "student", UserSession.created_at >= _local_start(mondays[0]),
                    UserSession.created_at < _local_start(day + timedelta(days=1)))
            .all())
    seen = {(user_id, week_start(created.astimezone(local_zone()).date())) for user_id, created in rows}
    per_week = Counter(monday for _, monday in seen)
    out = [{"label": short_date(monday), "value": per_week.get(monday, 0), "highlight": i == weeks - 1}
           for i, monday in enumerate(mondays)]
    last, prev = out[-1]["value"], (out[-2]["value"] if weeks > 1 else 0)
    return {"weeks": out, "change": _change(last, prev)}


# --- AI advisor quality ----------------------------------------------------------------------------------------------

def ai_quality(db: Session, day: date | None = None) -> list[dict]:
    """This week's answers: rated helpful, handed to an advisor, flagged as wrong (1 dp)."""
    start, end = _week_window(day or today())
    answers = db.query(AiMessage).filter(AiMessage.role == "assistant", AiMessage.created_at >= start,
                                         AiMessage.created_at < end)
    total = answers.count()
    rated = answers.filter(AiMessage.rating.isnot(None)).count()
    helpful = answers.filter(AiMessage.rating == 1).count()
    handoffs = answers.filter(AiMessage.kind == "handoff").count()
    flagged = (db.query(func.count(AiFlag.id))
               .filter(AiFlag.created_at >= start, AiFlag.created_at < end).scalar())
    return [
        {"label": "Rated helpful", "pct": _pct(helpful, rated), "tone": "accent",
         "note": f"From {_fmt(rated)} student {'rating' if rated == 1 else 'ratings'} this week"},
        {"label": "Handed to an advisor", "pct": _pct(handoffs, total), "tone": "violet",
         "note": "Questions Acadmate routed to a human"},
        {"label": "Flagged as wrong", "pct": _pct(flagged, total, dp=1), "tone": "pink",
         "note": f"{_plural(flagged, 'answer')} this week"},
    ]


# --- system status (stand-in until spec 35) --------------------------------------------------------------------------

def _csv_status(db: Session) -> dict:
    row = db.get(Integration, "csv")
    if row is None or not row.enabled or row.last_sync_at is None:
        return {"key": "csv", "name": "CSV data import", "detail": "Grades and enrollments · no imports yet", "status": "Off"}
    return {"key": "csv", "name": "CSV data import", "status": "Healthy",
            "detail": f"Grades and enrollments · last import {integrations.when_label(row.last_sync_at).lower()}"}


def systems(db: Session) -> list[dict]:
    courses = db.query(func.count(Course.course_id)).scalar()
    feeds = db.query(func.count(CalendarFeed.student_id)).scalar()
    year = catalog.catalog_year(db)
    mail_status, mail_detail = mailer.health()
    return [
        _csv_status(db),
        {"key": "catalog", "name": "Course catalog import", "detail": f"{year} catalog · "
         f"{_plural(courses, 'course')}", "status": "Healthy" if courses else "Off"},
        {"key": "ics", "name": "Calendar feeds (.ics)", "detail": f"{_plural(feeds, 'student')} subscribed",
         "status": "Healthy"},
        {"key": "mail", "name": "Email notifications", "detail": mail_detail, "status": mail_status},
    ]


# --- advisor workload ------------------------------------------------------------------------------------------------

def workload(db: Session, day: date | None = None) -> list[dict]:
    """Per active advisor: advisees vs. capacity, pending requests and the average decision time (last 30 days)."""
    day = day or today()
    advisors = (db.query(Advisor, User).join(User, User.user_id == Advisor.user_id)
                .filter(User.is_active.is_(True)).order_by(User.name).all())
    advisees = dict(db.query(AdvisorStudentAssignment.advisor_id, func.count(AdvisorStudentAssignment.student_id))
                    .group_by(AdvisorStudentAssignment.advisor_id).all())
    waiting = dict(db.query(ApprovalRequest.advisor_id, func.count(ApprovalRequest.id))
                   .filter(ApprovalRequest.status == "pending").group_by(ApprovalRequest.advisor_id).all())
    since = _local_start(day + timedelta(days=1)) - timedelta(days=REPLY_DAYS)
    replies = avg_decision_days(db, since)
    rows = []
    for advisor, user in advisors:
        count, capacity = advisees.get(advisor.advisor_id, 0), advisor.capacity
        reply = replies.get(advisor.advisor_id)
        rows.append({
            "advisorId": advisor.advisor_id,
            "userId": user.user_id,
            "name": user.name,
            "advisees": count,
            "capacity": capacity,
            "waiting": waiting.get(advisor.advisor_id, 0),
            "avgReply": f"{reply:.1f} days" if reply is not None else "—",
            "loadPct": min(100, round(count / capacity * 100)) if capacity else 100,
            "load": "Over" if count > OVER_CAPACITY * capacity else "OK",
        })
    return rows


# --- composition and export ------------------------------------------------------------------------------------------

def subtitle(db: Session) -> str:
    institution = settings.get(db, "institution")["name"]
    term = current_term(db)
    return f"{institution} · {term.name} · Week {term_week(term)}" if term else institution


def overview(db: Session) -> dict:
    active = active_students(db)
    questions = ai_questions(db, active.pop("count"))
    return {
        "subtitle": subtitle(db),
        "stats": [active, advisors_stat(db), ai_questions_stat(db, questions), plans_waiting(db)],
        "weeklyActive": weekly_active(db),
        "aiQuestions": questions,
        "aiQuality": ai_quality(db),
        "systems": systems(db),
        "advisors": workload(db),
    }


def overview_csv(data: dict) -> str:
    """One section per block: a title row, a header row, the rows and a blank line."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")

    def section(title: str, header: list[str], rows: list[list]) -> None:
        writer.writerow([title])
        writer.writerow(header)
        writer.writerows(rows)
        writer.writerow([])

    writer.writerow(["Acadmate platform overview", data["subtitle"]])
    writer.writerow([])
    section("Summary", ["Metric", "Value", "Change", "Note"],
            [[s["label"], s["value"], s["tag"] or "", s["note"] or ""] for s in data["stats"]])
    weekly = data["weeklyActive"]
    section("Weekly active students", ["Week of", "Students"],
            [[w["label"], w["value"]] for w in weekly["weeks"]] + [["Change", weekly["change"]["text"]]])
    section("AI advisor quality", ["Measure", "Percent", "Note"],
            [[q["label"], "" if q["pct"] is None else q["pct"], q["note"]] for q in data["aiQuality"]])
    section("System status", ["System", "Status", "Detail"],
            [[s["name"], s["status"], s["detail"]] for s in data["systems"]])
    section("Advisor workload", ["Advisor", "Advisees", "Capacity", "Waiting", "Avg. reply", "Load"],
            [[a["name"], a["advisees"], a["capacity"], a["waiting"], a["avgReply"], a["load"]]
             for a in data["advisors"]])
    return out.getvalue()


def export_csv(db: Session, admin: User | None, ip: str | None = None, key_name: str | None = None) -> str:
    """The CSV report, audited as report.export (spec 36). `key_name` when an API key asked for it (spec 35)."""
    body = overview_csv(overview(db))
    summary = "Exported the platform overview" + (f" with the API key {key_name}" if key_name else "")
    audit.record(db, admin, "report.export", summary, ("report", "overview"), ip=ip)
    db.commit()
    return body


def csv_filename() -> str:
    return f"acadmate-overview-{today().isoformat()}.csv"
