"""Next-term recommendation for the dashboard (spec 10): the rules engine's plan, condensed. The plan is cached per
student per day; the on/off checks (admin features, the student's settings) run on every call so a switch applies at once."""
from sqlalchemy.orm import Session

from core.time import today
from models import Student
from services.ai import context, rules_engine

_cache: dict[tuple[int, object], dict | None] = {}


def next_term_recommendation(db: Session, student: Student) -> dict | None:
    ctx = context.build(db, student)
    features = ctx["settings"]["features"]
    if not (features["advisor"] and features["proactiveTips"] and features["planSuggestions"]):
        return None
    if not (ctx["prefs"]["ai"]["dashboardSuggestions"] and ctx["sources"]["audits"] and ctx["sources"]["catalog"]):
        return None
    key = (student.student_id, today())
    if key not in _cache:
        _cache[key] = _build(db, student, ctx)
    return _cache[key]


def _build(db: Session, student: Student, ctx: dict) -> dict | None:
    plan = rules_engine.next_plan(db, student, ctx)
    if plan is None or not plan["rows"]:
        return None
    term = plan["term"]
    codes = " and ".join(f"{row['code']} {row['name']}" for row in plan["rows"])
    text = f"After this semester you will have {plan['credits_left']:g} credits left. Taking {codes} in {term.name} "
    text += f"would finish your degree in {plan['graduation']}." if plan["all_filled"] else "keeps you on track."
    if plan["approvals"]:
        text += f" Your {plan['approvals'][0].lower()} needs your advisor's pre-approval first."
    return {"title": f"{term.name} recommendation", "text": text}
