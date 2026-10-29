"""Advisor reports (spec 26): the caseload at a glance for one term, plus a CSV of every advisee.

Approvals, response time and meetings are counted within the term. There is no history of risk or assignments, so
advisee status, "Need attention" and "Students to check on" always use live data (the spec's simplification)."""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from core.errors import bad_request, not_found
from core.time import local_zone, today
from models import Advisor, ApprovalRequest, Meeting, Term, User
from services import audit
from services.advisees import caseload, drops_below_full_time, failed_check, last_contact
from services.catalog import current_term

TERMS_BACK = 3
WEEKS = 6
CHECK_ON_LIMIT = 6
MEETING_STATUSES = ("confirmed", "completed", "no_show")
STATUS_TONES = (("On track", "accent"), ("Needs attention", "amber"), ("Graduating", "violet"))
LEVEL_ORDER = {"High": 0, "Medium": 1, "Low": 2}
CSV_HEADER = ["student", "program", "credits_earned", "credits_required", "gpa", "status", "risk", "expected_graduation",
              "pending_requests", "last_contact", "next_meeting"]


def _at(day: date) -> datetime:
    return datetime.combine(day, time(0), local_zone()).astimezone(timezone.utc)


def _terms(db: Session) -> list[Term]:
    """The current term and up to three earlier ones, newest first."""
    current = current_term(db)
    if current is None:
        return []
    earlier = (db.query(Term).filter(Term.start_date < current.start_date)
               .order_by(Term.start_date.desc()).limit(TERMS_BACK).all())
    return [current, *earlier]


def _term(db: Session, term_id: int | None) -> Term:
    if term_id is None:
        term = current_term(db)
        if term is None:
            raise not_found("Term")
        return term
    term = db.get(Term, term_id)
    if term is None:
        raise not_found("Term")
    if term.start_date > today():
        raise bad_request("Pick the current term or an earlier one.")
    return term


def _previous(db: Session, term: Term) -> Term | None:
    return db.query(Term).filter(Term.start_date < term.start_date).order_by(Term.start_date.desc()).first()


def _window(term: Term) -> tuple[datetime, datetime]:
    return _at(term.start_date), _at(term.end_date + timedelta(days=1))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _avg_days(db: Session, advisor: Advisor, term: Term) -> float | None:
    start, end = _window(term)
    rows = (db.query(ApprovalRequest.created_at, ApprovalRequest.decided_at)
            .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.decided_at >= start,
                    ApprovalRequest.decided_at < end).all())
    if not rows:
        return None
    return round(sum((decided - created).total_seconds() for created, decided in rows) / len(rows) / 86400, 1)


def stats(db: Session, advisor: Advisor, term: Term, rows: list[dict]) -> list[dict]:
    start, end = _window(term)
    programs = {row["program"] for row in rows if row["program"]}
    approved = (db.query(ApprovalRequest)
                .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.type == "plan",
                        ApprovalRequest.status == "approved", ApprovalRequest.decided_at >= start,
                        ApprovalRequest.decided_at < end).count())
    pending = (db.query(ApprovalRequest)
               .filter(ApprovalRequest.advisor_id == advisor.advisor_id, ApprovalRequest.type == "plan",
                       ApprovalRequest.status == "pending", ApprovalRequest.created_at < end).count())

    average = _avg_days(db, advisor, term)
    previous = _previous(db, term)
    before = _avg_days(db, advisor, previous) if previous else None
    if average is None:
        response = {"value": "—", "note": "No decisions this term"}
    else:
        if before is None:
            note = "First term with decisions"
        elif average < before:
            note = f"Down from {before:g} days"
        elif average > before:
            note = f"Up from {before:g} days"
        else:
            note = "Same as last term"
        response = {"value": f"{average:g} days", "note": note}

    attention = sum(1 for row in rows if row["risk"] != "Low")
    share = round(attention / len(rows) * 100) if rows else 0
    return [
        {"label": "Advisees", "value": str(len(rows)), "note": f"Across {_plural(len(programs), 'program')}"},
        {"label": "Plans approved", "value": str(approved), "note": f"{pending} still pending" if pending else "All cleared"},
        {"label": "Avg. response time", **response},
        {"label": "Need attention", "value": str(attention), "note": f"{share}% of advisees"},
    ]


def by_status(rows: list[dict]) -> list[dict]:
    return [{"label": label, "count": sum(1 for row in rows if row["status"] == label), "tone": tone}
            for label, tone in STATUS_TONES]


def meetings_per_week(db: Session, advisor: Advisor, term: Term) -> list[dict]:
    """Meetings that took place (or are booked) in each of the last 6 weeks of the term up to today."""
    first_monday = term.start_date - timedelta(days=term.start_date.weekday())
    last_day = min(today(), term.end_date)
    last_monday = last_day - timedelta(days=last_day.weekday())
    mondays = [last_monday - timedelta(weeks=n) for n in range(WEEKS - 1, -1, -1)]
    mondays = [monday for monday in mondays if monday >= first_monday]
    counts = {monday: 0 for monday in mondays}
    if mondays:
        rows = (db.query(Meeting.starts_at)
                .filter(Meeting.staff_user_id == advisor.user_id, Meeting.status.in_(MEETING_STATUSES),
                        Meeting.starts_at >= _at(mondays[0]), Meeting.starts_at < _at(last_monday + timedelta(days=7))))
        for starts_at, in rows:
            day = starts_at.astimezone(local_zone()).date()
            counts[day - timedelta(days=day.weekday())] += 1
    return [{"label": f"W{(monday - first_monday).days // 7 + 1}", "value": counts[monday]} for monday in mondays]


def _short_title(title: str) -> str:
    return title.split(" · ")[0]


def check_on(rows: list[dict], ctx, limit: int = CHECK_ON_LIMIT) -> list[dict]:
    """One line per advisee who needs something: a drop below full time, a request that failed its pre-check, any
    other risk, then the final graduation audit."""
    out = []
    for row in sorted(rows, key=lambda r: (LEVEL_ORDER[r["risk"]], r["_sort"])):
        pending = ctx.pending.get(row["studentId"], [])
        drop = next((r for r in pending if drops_below_full_time(r)), None)
        failing = next((r for r in pending if failed_check(r)), None)
        if drop is not None:
            reason, action, to = ("Requested a drop that ends full-time status", "Review request",
                                  f"/advisor/approvals?id={drop.id}")
        elif failing is not None:
            check = failed_check(failing)
            reason = f"{_short_title(failing.title)}: {check[0].lower() + check[1:]}"
            action = "Review plan" if failing.type == "plan" else "Review request"
            to = f"/advisor/approvals?id={failing.id}"
        elif row["risk"] != "Low" and row["_riskFlag"]:
            reason, action, to = row["_riskFlag"], "Message", f"/advisor/messages?to={row['userId']}"
        elif row["status"] == "Graduating":
            reason, action, to = "Final graduation audit due", "View advisee", f"/advisor/advisees/{row['studentId']}"
        else:
            continue
        out.append({"studentId": row["studentId"], "name": row["name"], "reason": reason, "action": action, "to": to})
    return out[:limit]


def report(db: Session, advisor: Advisor, term_id: int | None = None) -> dict:
    term = _term(db, term_id)
    current = current_term(db)
    rows, ctx = caseload(db, advisor)
    return {
        "terms": [{"id": t.id, "label": t.name} for t in _terms(db)],
        "currentTermId": current.id if current else term.id,
        "termId": term.id,
        "termLabel": term.name,
        "stats": stats(db, advisor, term, rows),
        "byStatus": by_status(rows),
        "weeks": meetings_per_week(db, advisor, term),
        "checkOn": check_on(rows, ctx),
    }


def export_csv(db: Session, advisor: Advisor, term_id: int | None = None) -> tuple[str, str]:
    """(csv text, file name): one row per advisee. Audited as report.export; the caller commits."""
    term = _term(db, term_id)
    rows, ctx = caseload(db, advisor)
    contacts = last_contact(db, advisor, [row["_student"] for row in rows])
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in sorted(rows, key=lambda r: r["_sort"]):
        student = row["_student"]
        contact = contacts.get(student.student_id)
        writer.writerow([student.name, row["program"] or "", f"{row['credits']:g}", f"{row['requiredCredits']:g}",
                         "" if row["gpa"] == "—" else row["gpa"], row["status"], row["risk"],
                         student.expected_graduation or "", len(ctx.pending.get(student.student_id, [])),
                         contact.isoformat() if contact else "", row["next"]])
    actor = db.get(User, advisor.user_id)
    audit.record(db, actor, "report.export", f"Exported the {term.name} advisee report", ("report", "advisor"))
    filename = f"advisor-report-{term.name.lower().replace(' ', '-')}-{today().isoformat()}.csv"
    return buffer.getvalue(), filename
