"""Institution-wide settings (spec 37), stored in system_settings as key -> JSON and merged over DEFAULTS. get() is
what every feature reads; get_all() / update() serve the admin settings screen. The "ai" key belongs to
services/ai/settings.py (spec 34)."""
import logging
from copy import deepcopy
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.config import settings as env
from core.errors import ApiError
from core.time import DEFAULT_ZONE, set_zone
from models import SystemSetting, Term, User

logger = logging.getLogger("acadmate.settings")

DEFAULTS = {
    "institution": {
        "name": "Pace University",
        "domain": "pac.edu",
        "supportEmail": "acadmate-help@pac.edu",
        "currentTermId": None,  # None: the term that contains today (services/catalog.current_term)
        "timeZone": "Eastern",
        "selfSignup": True,
    },
    "security": {"google": True, "mfa": True, "ipLog": True, "timeout": "2 hours"},
    "retention": {"ai": "1 year", "audit": "1 year"},
    "branding": {"accent": "#0F766E"},
}
KEYS = tuple(DEFAULTS)

TIMEOUTS = {"30 min": timedelta(minutes=30), "2 hours": timedelta(hours=2), "8 hours": timedelta(hours=8)}
ZONES = {"Eastern": "America/New_York", "Central": "America/Chicago", "Pacific": "America/Los_Angeles"}
AI_RETENTION = ("30 days", "1 year", "Until graduation")
AUDIT_RETENTION = ("90 days", "1 year", "2 years")
ACCENTS = ("#0F766E", "#1D4ED8", "#7C3AED", "#B45309")


def _stored(db: Session, key: str) -> dict:
    row = db.get(SystemSetting, key)
    return row.value if row is not None and isinstance(row.value, dict) else {}


def get(db: Session, key: str) -> dict:
    """The stored values for `key` laid over the defaults (unknown stored fields are dropped)."""
    merged = deepcopy(DEFAULTS[key])
    merged.update({k: v for k, v in _stored(db, key).items() if k in merged})
    return merged


def session_timeout(db: Session) -> timedelta:
    """Idle timeout for sessions without "Keep me signed in"."""
    return TIMEOUTS.get(get(db, "security")["timeout"], TIMEOUTS["2 hours"])


def time_zone(db: Session) -> ZoneInfo:
    return ZoneInfo(ZONES.get(get(db, "institution")["timeZone"], DEFAULT_ZONE))


def apply_time_zone(db: Session) -> None:
    """Points core.time at the saved time zone (startup, after a change, in scripts)."""
    set_zone(time_zone(db).key)


def retention_label(db: Session) -> str:
    """"1 year" -> "1 year", "Until graduation" -> "until graduation" (for sentences)."""
    return get(db, "retention")["ai"].lower()


def _terms(db: Session, current: Term | None) -> list[dict]:
    """The previous, current and next term by start date."""
    terms = db.query(Term).order_by(Term.start_date).all()
    if not terms:
        return []
    index = next((i for i, term in enumerate(terms) if current is not None and term.id == current.id), 0)
    return [{"id": term.id, "name": term.name} for term in terms[max(0, index - 1):index + 2]]


def get_all(db: Session) -> dict:
    """The GET /admin/settings shape."""
    from services import catalog  # catalog reads the current-term override from here

    institution = get(db, "institution")
    current = catalog.current_term(db)
    institution["currentTermId"] = current.id if current else None
    institution["terms"] = _terms(db, current)
    return {**{key: get(db, key) for key in KEYS if key != "institution"}, "institution": institution,
            "demoMode": env.DEMO_MODE}


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def update(db: Session, admin: User, patch: dict, ip: str | None = None) -> dict:
    """`patch` is any subset of {section: {field: value}} (already validated by the schema). Writes the sections
    that changed and audits them as one settings.update event."""
    from services import audit, catalog

    changes: dict[str, list] = {}
    for key in KEYS:
        section = {k: v for k, v in (patch.get(key) or {}).items() if k in DEFAULTS[key]}
        if not section:
            continue
        if key == "institution" and "currentTermId" in section:
            term = db.get(Term, section["currentTermId"])
            if term is None:
                raise _validation("currentTermId", "Choose one of the listed terms.")
            # The term that contains today is stored as "follow the calendar", so the next term starts on its own.
            by_date = catalog.term_by_date(db)
            section["currentTermId"] = None if by_date is not None and by_date.id == term.id else term.id
        before = get(db, key)
        after = {**before, **section}
        diff = {f"{key}.{field}": [before[field], after[field]] for field in after if before[field] != after[field]}
        if not diff:
            continue
        changes.update(diff)
        stored = {field: value for field, value in after.items() if value != DEFAULTS[key][field]}
        row = db.get(SystemSetting, key)
        if row is None:
            db.add(SystemSetting(key=key, value=stored, updated_by=admin.user_id))
        else:
            row.value, row.updated_by = stored, admin.user_id
    if changes:
        audit.record(db, admin, "settings.update", f"Updated settings: {', '.join(changes)}",
                     ("settings", "institution"), changes, ip=ip)
        db.commit()
        apply_time_zone(db)
    return get_all(db)
