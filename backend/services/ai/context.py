"""What the AI advisor may use for a student: effective data sources, engine, and the context panel payload."""
from sqlalchemy.orm import Session

from models import Advisor, AdvisorStudentAssignment, Program, Student, User
from services import preferences
from services import settings as institution
from services.ai import quota
from services.ai import settings as ai_config
from services import catalog
from services.progress import credit_totals

PROMPTS = ["Compare my elective options", "What if I fail a course?", "Draft an email to my advisor"]
SOURCE_NAMES = {"audits": "Degree audit", "grades": "Grades", "catalog": "Course catalog", "schedules": "Schedule"}


def effective_sources(db: Session, student: Student, cfg: dict, prefs: dict) -> dict[str, bool]:
    """A source is on when the admin allows it AND the student hasn't turned it off (grades, schedule)."""
    allowed = dict(cfg["sources"])
    allowed["grades"] = allowed["grades"] and prefs["ai"]["useGrades"]
    allowed["schedules"] = allowed["schedules"] and prefs["ai"]["useSchedule"]
    return allowed


def engine_name(cfg: dict) -> str:
    """"Claude" only when the setting asks for it and an API key is configured."""
    return "Claude" if cfg["engine"] == "Claude" and ai_config.claude_available() else "Rules"


def catalog_label(db: Session) -> str:
    """"Course catalog 2026–27", the published catalog year (spec 33)."""
    return f"Course catalog {catalog.catalog_year(db)}"


def advisor_of(db: Session, student: Student) -> dict | None:
    link = db.get(AdvisorStudentAssignment, student.student_id)
    if link is None:
        return None
    advisor = db.get(Advisor, link.advisor_id)
    user = db.get(User, advisor.user_id) if advisor else None
    return {"id": advisor.advisor_id, "name": user.name} if user else None


def build(db: Session, student: Student, cfg: dict | None = None) -> dict:
    """Everything an engine needs about the student's AI settings, computed once per question. `cfg` overrides the
    stored settings (the admin test box)."""
    cfg = ai_config.ai_settings(db) if cfg is None else cfg
    user = db.get(User, student.user_id)
    prefs = preferences.get(db, user)
    return {"settings": cfg, "prefs": prefs, "sources": effective_sources(db, student, cfg, prefs),
            "engine": engine_name(cfg), "user": user}


def student_context(db: Session, student: Student) -> dict:
    from services import meetings  # imported here: meetings → calendar → services.ai would be circular at import time
    ctx = build(db, student)
    cfg, prefs = ctx["settings"], ctx["prefs"]
    program = db.get(Program, student.program_id)
    earned, in_progress = credit_totals(db, student)
    target = prefs.get("targetGraduation") or student.expected_graduation
    return {
        "enabled": cfg["features"]["advisor"],
        "engine": ctx["engine"],
        "daily_limit": cfg["dailyLimit"],
        "remaining_today": quota.remaining_today(db, student, cfg["dailyLimit"]),
        "prompts": PROMPTS,
        "program": program.program_name,
        "progress": f"{earned:g} credits earned · {in_progress:g} in progress",
        "goal": f"Graduate {target}" if target else "Not set",
        "preferences": [f"{prefs['classTime']} classes"] if prefs.get("classTime") else [],
        "sources": [name for key, name in SOURCE_NAMES.items() if ctx["sources"].get(key)],
        "advisor": advisor_of(db, student),
        "next_meeting": meetings.next_meeting(db, student),
        "retention": institution.get(db, "retention")["ai"],
    }
