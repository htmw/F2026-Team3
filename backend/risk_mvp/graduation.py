"""Read-only credit-based graduation projections; not an awarded degree or policy."""
from datetime import date
from math import ceil, isfinite


def project(required, earned, current_credits, day, pace=9):
    """Current registered credits count only in the active Spring/Fall semester.

    Future semesters use the chosen pace. No summer study is assumed.
    """
    values = (required, earned, current_credits, pace)
    if any(not isfinite(float(v)) for v in values) or required <= 0 or min(earned, current_credits) < 0 or pace <= 0:
        raise ValueError("Valid credit totals and a positive semester load are required")
    remaining = max(0, required-earned)
    if remaining == 0:
        return "Credits complete"
    # May and December are completion months, inclusive of their last day.
    if day.month <= 5:
        year, season = day.year, 0
        active = True
    elif day.month <= 7:
        year, season = day.year, 1
        active = False
    else:
        year, season = day.year, 1
        active = True
    if active and current_credits > 0:
        remaining = max(0, remaining-current_credits)
        if remaining == 0:
            return f"{'May' if season == 0 else 'December'} {year}"
        season += 1
        year += season // 2
        season %= 2
    elif active:
        # An underway semester with no enrollment cannot supply invented credits.
        season += 1
        year += season // 2
        season %= 2
    offset = ceil(remaining/pace)-1
    index = season+offset
    return f"{'May' if index % 2 == 0 else 'December'} {year + index // 2}"


def projection(db, student):
    from core.time import today
    from models import Program
    from services.degree_audit import student_courses
    from services.catalog import current_term
    program = db.get(Program, student.program_id)
    if program is None or not program.total_required_credits:
        return {"label": None, "note": "Program credit requirement is not recorded"}
    rows = student_courses(db, student)
    earned = sum(row.credits for row in rows if row.state == "completed")
    term = current_term(db)
    doing = sum(row.credits for row in rows if row.state == "in_progress" and term and row.term_name == term.name)
    required = float(program.total_required_credits)
    label = project(required, earned, doing, today(), 9)
    earliest = project(required, earned, doing, today(), 12)
    note = "Estimate assumes successful completion of current courses and 9 credits each Spring/Fall; required courses and approvals still apply."
    if earliest != label:
        note += f" At 12 credits per semester: {earliest}."
    if label == "Credits complete":
        note = "Credit total met; degree requirements and graduation approval still need confirmation."
    return {"label": label, "note": note}


def graduation_label(db, student):
    return projection(db, student)["label"]


def graduation_note(db, student):
    return projection(db, student)["note"]
