"""Audit trail (spec 36). record() adds a row to the caller's transaction (pass `changes` as {field: [old, new]} and a
target (type, id) that link_for() knows). list_events() pages newest first by id, export_csv() writes the same
filters as CSV, and prune() drops rows older than the retention setting. Rows are never updated."""
import csv
import io
import logging
from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.errors import ApiError
from core.time import iso_z, local_midnight, local_zone, short_date, today
from models import AuditEvent, User
from services import settings

logger = logging.getLogger("acadmate.audit")

ROLE_LABELS = {"student": "Student", "advisor": "Advisor", "admin": "Admin"}


def record(db: Session, actor: User | None, action: str, summary: str, target: tuple[str, object] | None = None,
           changes: dict | None = None, ip: str | None = None, result: str = "success", error: str | None = None) -> None:
    """Never raises: an audit problem must not break the action being audited. The caller commits."""
    try:
        if not settings.get(db, "security")["ipLog"]:
            ip = None
        db.add(AuditEvent(
            actor_id=actor.user_id if actor else None,
            actor_label=actor.name if actor else "Acadmate",
            actor_role=ROLE_LABELS[actor.role] if actor else "System",
            action=action,
            summary=summary[:300],
            target_type=target[0] if target else None,
            target_id=str(target[1])[:40] if target else None,
            changes=changes,
            ip=ip,
            result=result,
            error=error[:300] if error else None,
        ))
    except Exception:
        logger.exception("Could not record audit event %s", action)


def request_ip(request) -> str | None:
    """Client IP from a Starlette request: first X-Forwarded-For hop, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host[:45] if request.client else None


# --- reading the log (spec 36) -------------------------------------------------------------------------------------

PAGE = 50
CSV_MAX = 10_000
ROLES = ("All", "Admin", "Advisor", "Student", "System")
RANGES = {"today": 0, "7d": 6, "30d": 29}  # days before today's school-time midnight
CSV_COLUMNS = ["time", "actor", "role", "action", "target", "ip", "result", "event_id"]
RETENTION = {"30 days": timedelta(days=30), "90 days": timedelta(days=90), "1 year": timedelta(days=365),
             "2 years": timedelta(days=730)}  # "Forever" (or anything else) keeps every row

# target_type -> (route, label); "{id}" is filled with the URL-encoded target id. Admin screens only.
LINKS = {
    "user": ("/admin/users?id={id}", "Open user"),
    "advisor": ("/admin/advisors?id={id}", "Open advisors"),
    "integration": ("/admin/integrations?id={id}", "Open integrations"),
    "api_key": ("/admin/integrations", "Open integrations"),
    "import": ("/admin/integrations?id=csv", "Open integrations"),
    "course": ("/admin/catalog?course={id}", "Open catalog"),
    "term": ("/admin/catalog?tab=terms", "Open catalog"),
    "program": ("/admin/catalog?tab=requirements", "Open catalog"),
    "catalog": ("/admin/catalog", "Open catalog"),
    "settings": ("/admin/settings", "Open settings"),
    "settings:ai": ("/admin/ai", "Open AI settings"),  # spec 34 stores its settings under the "ai" key
    "ai_flag": ("/admin/ai#flags", "Open AI settings"),
    "report": ("/admin", "Open overview"),
}


def when_label(at: datetime) -> str:
    """"Today 14:02", "Yesterday 17:20", "Sep 28 16:10", or "Sep 28, 2025 16:10" in an earlier year."""
    local = at.astimezone(local_zone())
    day, clock = local.date(), f"{local:%H:%M}"
    if day == today():
        return f"Today {clock}"
    if day == today() - timedelta(days=1):
        return f"Yesterday {clock}"
    return f"{short_date(day)}{'' if day.year == today().year else f', {day.year}'} {clock}"


def link_for(event: AuditEvent) -> dict | None:
    if event.target_type is None:
        return {"to": "/admin/users", "label": "Open users"} if event.action.startswith("user.") else None
    if event.target_type not in LINKS:
        return None  # student-owned targets (plan items, meetings, assignments) have no admin screen
    route, label = LINKS.get(f"{event.target_type}:{event.target_id}") or LINKS[event.target_type]
    return {"to": route.format(id=quote(event.target_id or "", safe="")), "label": label}


def _changes(changes) -> list[dict]:
    if not isinstance(changes, dict):
        return []
    out = []
    for field, value in changes.items():
        if isinstance(value, list) and len(value) == 2:
            out.append({"field": field, "from": value[0], "to": value[1]})
        else:
            out.append({"field": field, "from": None, "to": value})
    return out


def event_out(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "eventId": f"evt_{event.id}",
        "when": when_label(event.at),
        "at": iso_z(event.at),
        "who": event.actor_label,
        "role": event.actor_role,
        "action": event.summary,
        "key": event.action,
        "target": f"{event.target_type}:{event.target_id}" if event.target_type else None,
        "ip": event.ip,
        "result": "Failed" if event.result == "failed" else "Success",
        "error": event.error,
        "changes": _changes(event.changes),
        "link": link_for(event),
    }


def _query(db: Session, role: str = "All", range_: str = "30d", q: str | None = None):
    query = db.query(AuditEvent).filter(AuditEvent.at >= local_midnight() - timedelta(days=RANGES[range_]))
    if role != "All":
        query = query.filter(AuditEvent.actor_role == role)
    q = (q or "").strip()
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(AuditEvent.summary.ilike(pattern, escape="\\"),
                                 AuditEvent.actor_label.ilike(pattern, escape="\\"),
                                 AuditEvent.action.ilike(pattern, escape="\\")))
    return query


def list_events(db: Session, role: str = "All", range_: str = "30d", q: str | None = None, cursor: str | None = None,
                limit: int = PAGE) -> dict:
    """Newest first; `cursor` is the last id of the previous page, so Load more never repeats or skips a row."""
    query = _query(db, role, range_, q)
    if cursor:
        if not cursor.isdigit():
            raise ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.",
                           [{"field": "cursor", "message": "Not a valid cursor."}])
        query = query.filter(AuditEvent.id < int(cursor))
    rows = query.order_by(AuditEvent.id.desc()).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"events": [event_out(row) for row in rows], "nextCursor": str(rows[-1].id) if more else None}


def export_csv(db: Session, admin: User, role: str = "All", range_: str = "30d", q: str | None = None,
               ip: str | None = None) -> str:
    """The filtered log (at most CSV_MAX rows), audited as report.export."""
    rows = _query(db, role, range_, q).order_by(AuditEvent.id.desc()).limit(CSV_MAX).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([
            row.at.astimezone(local_zone()).strftime("%Y-%m-%d %H:%M"), row.actor_label, row.actor_role, row.summary,
            f"{row.target_type}:{row.target_id}" if row.target_type else "", row.ip or "",
            f"failed: {row.error}" if row.result == "failed" and row.error else row.result, f"evt_{row.id}",
        ])
    record(db, admin, "report.export", "Exported the audit log", ("report", "audit"),
           {"rows": len(rows), "role": role, "range": range_}, ip=ip)
    db.commit()
    return out.getvalue()


def csv_filename() -> str:
    return f"audit-{today().isoformat()}.csv"


def prune(db: Session, day: date | None = None) -> int:
    """Deletes events older than the audit retention setting (spec 37); returns how many."""
    keep = RETENTION.get(settings.get(db, "retention")["audit"])
    if keep is None:
        return 0
    cutoff = datetime.combine(day or today(), datetime.min.time(), local_zone()) - keep
    count = db.query(AuditEvent).filter(AuditEvent.at < cutoff).delete(synchronize_session=False)
    db.commit()
    return count
