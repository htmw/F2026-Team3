"""User preferences (spec 17 owns the settings screen and PATCH endpoint). get() returns stored JSON merged over the
defaults, so callers always see every key."""
from copy import deepcopy

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from core.errors import ApiError
from core.time import today
from models import Student, Term, User, UserPreference
from services import audit

DEFAULTS = {
    "notify": {"deadlines": True, "messages": True, "suggestions": True, "weeklySummary": False, "sms": False},
    "reminderTiming": "2 days before",
    "ai": {"useGrades": True, "useSchedule": True, "dashboardSuggestions": True, "shareWithAdvisor": False},
    "aiStyle": "Concise",
    "targetGraduation": None,
    "classTime": None,  # "Evening" / "Daytime": used by the AI advisor's plan suggestions
}
# Spec 27 gives staff their own settings screen; until then staff share the student defaults plus the booking switch
# that meetings read (spec 18: auto-confirm bookings instead of leaving them requested).
STAFF_DEFAULTS = {**DEFAULTS, "bookings": {"autoConfirm": False}}
DEFAULTS_BY_ROLE = {"student": DEFAULTS, "advisor": STAFF_DEFAULTS, "admin": STAFF_DEFAULTS}

GRADUATION_OPTIONS = 6
GRADUATION_MONTHS = {"Fall": "December", "Spring": "May", "Summer": "August"}


def _merge(base: dict, extra: dict) -> dict:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def get(db: Session, user: User) -> dict:
    row = db.get(UserPreference, user.user_id)
    return _merge(deepcopy(DEFAULTS_BY_ROLE[user.role]), row.data if row and row.data else {})


def graduation_options(db: Session) -> list[str]:
    """Graduation labels for the next terms that haven't ended: "December 2026", "May 2027", ..."""
    terms = db.query(Term).filter(Term.end_date >= today()).order_by(Term.start_date).limit(GRADUATION_OPTIONS).all()
    return [f"{GRADUATION_MONTHS[term.season]} {term.year}" for term in terms]


def update(db: Session, user: User, patch: dict) -> dict:
    """Deep-merges a validated (partial) preferences object over the stored one. A student's target graduation
    also becomes their expected graduation."""
    current = get(db, user)
    target = patch.get("targetGraduation")
    if target is not None and target != current["targetGraduation"] and target not in graduation_options(db):
        raise ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.",
                       [{"field": "targetGraduation", "message": "Choose one of the listed graduation dates."}])
    merged = _merge(deepcopy(current), patch)

    row = db.get(UserPreference, user.user_id)
    if row is None:
        db.add(UserPreference(user_id=user.user_id, data=merged))
    else:
        row.data = merged
        flag_modified(row, "data")
    if user.role == "student" and merged["targetGraduation"] != current["targetGraduation"]:
        student = db.query(Student).filter(Student.user_id == user.user_id).one_or_none()
        if student is not None and merged["targetGraduation"]:
            student.expected_graduation = merged["targetGraduation"]
    audit.record(db, user, "prefs.update", f"{user.name} updated their settings", target=("user", user.user_id))
    db.commit()
    return merged
