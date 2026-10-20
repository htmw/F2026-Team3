"""AI advisor settings (spec 34), stored in system_settings['ai'] and merged over DEFAULTS. Callers use
`ai_config.ai_settings(db)` through the module so tests can patch it."""
from copy import deepcopy

from sqlalchemy.orm import Session

from core.config import settings as env
from core.errors import ApiError
from models import SystemSetting, User
from services import audit

DEFAULTS = {
    "features": {"advisor": True, "planSuggestions": True, "gradeInsights": True, "proactiveTips": True},
    "sources": {"catalog": True, "audits": True, "grades": True, "schedules": True},
    "style": "Balanced",  # Concise / Balanced / Detailed
    "blockedTopics": ["Visa and immigration", "Mental health", "Financial aid", "Grade appeals"],
    "engine": "Claude",  # Claude / Rules
    "dailyLimit": 25,
}
GROUPS = ("features", "sources")  # merged per key; every other setting is replaced whole
KEY = "ai"


def _dedupe(topics: list[str]) -> list[str]:
    """Case-insensitive, keeping the first spelling and the order."""
    seen, out = set(), []
    for topic in topics:
        if topic.lower() not in seen:
            seen.add(topic.lower())
            out.append(topic)
    return out


def merge(base: dict, patch: dict | None) -> dict:
    """`patch` (any subset of the settings, camelCase) laid over `base`; unknown keys are ignored."""
    merged = deepcopy(base)
    for key, value in (patch or {}).items():
        if key not in DEFAULTS or value is None:
            continue
        if key in GROUPS:
            merged[key].update({k: v for k, v in value.items() if k in DEFAULTS[key] and v is not None})
        elif key == "blockedTopics":
            merged[key] = _dedupe(value)
        else:
            merged[key] = value
    return merged


def ai_settings(db: Session) -> dict:
    row = db.get(SystemSetting, KEY)
    return merge(DEFAULTS, row.value if row else None)


def claude_available() -> bool:
    return bool(env.ANTHROPIC_API_KEY)


def public(db: Session) -> dict:
    """The GET /admin/ai/settings shape."""
    return {**ai_settings(db), "claudeAvailable": claude_available()}


def _flat(cfg: dict) -> dict:
    flat = {}
    for key, value in cfg.items():
        if key in GROUPS:
            flat.update({f"{key}.{k}": v for k, v in value.items()})
        else:
            flat[key] = value
    return flat


def update(db: Session, admin: User, patch: dict, ip: str | None = None) -> dict:
    if patch.get("engine") == "Claude" and not claude_available():
        raise ApiError(400, "CLAUDE_UNAVAILABLE", "Claude isn't configured on this server.")
    current = ai_settings(db)
    new = merge(current, patch)
    before, after = _flat(current), _flat(new)
    changes = {key: [before[key], after[key]] for key in after if before[key] != after[key]}
    if changes:
        row = db.get(SystemSetting, KEY)
        if row is None:
            db.add(SystemSetting(key=KEY, value=new, updated_by=admin.user_id))
        else:
            row.value, row.updated_by = new, admin.user_id
        audit.record(db, admin, "ai.settings", f"Updated AI settings: {', '.join(changes)}", ("settings", KEY), changes, ip=ip)
        db.commit()
    return public(db)
