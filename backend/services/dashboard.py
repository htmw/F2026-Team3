"""Student dashboard payload (spec 10). Each section is built independently: if one fails it is logged and
the section falls back to its empty value, so a single broken feature never blanks the whole dashboard.
Sections owned by features that aren't built yet return their empty value (see build_dashboard)."""
import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from core.time import DAY_NAMES, day_label, today
from models import Course, Enrollment, Program, StudySession, Student, User
from services.academics import current_grade, gpa, points_for
from services.auth import user_payload
from services.catalog import current_term, next_term, term_sort_key, term_week, terms_by_name
from services.calendar import events_for_day
from services.assignments import on_time_rate, upcoming_tasks
from services.courses import current_enrollments
from services.degree_audit import alert as degree_alert
from services.ai.recommend import next_term_recommendation
from services.progress import CREDITS_PER_COURSE, requirement_status

log = logging.getLogger(__name__)

WARN_WITHIN_DAYS = 45


def build_dashboard(db: Session, student: Student) -> dict:
    goal = float(student.study_goal_hours or 20)  # read up front: the fallbacks must not touch the database
    sections = {
        "student": (student_header, lambda: {"first_name": "", "initials": "", "term_label": ""}),
        "gpa": (gpa_summary, lambda: {"cumulative": None, "change": None, "status": "No grades yet", "trend": []}),
        "stats": (stats, list),
        "requirements": (requirements_summary, list),
        "study_hours": (study_hours, lambda: {"total": 0, "goal": goal, "days": []}),
        "today": (today_events, lambda: {"label": day_label(today()), "events": []}),
        "courses": (current_courses, list),
        "recommendation": (next_term_recommendation, lambda: None),  # AI advisor (spec 13)
        "alert": (degree_alert, lambda: None),  # degree audit (spec 12)
        "tasks": (upcoming_tasks, list),  # assignments (spec 15)
    }
    payload = {}
    for key, (build, empty) in sections.items():
        try:
            with db.begin_nested():  # a failed query only rolls back this section
                payload[key] = build(db, student)
        except Exception:
            log.exception("Dashboard section %r failed for student %s", key, student.student_id)
            payload[key] = empty()
    return payload




def _enrollments(db: Session, student: Student):
    return (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.student_id == student.student_id)
        .all()
    )






def student_header(db: Session, student: Student) -> dict:
    user = user_payload(db.get(User, student.user_id))
    program = db.get(Program, student.program_id)
    term = current_term(db)
    if term is None:
        label = program.program_name
    else:
        label = f"{term.name} · Week {term_week(term)} · {program.program_name}"
    return {"first_name": user["first_name"], "initials": user["initials"], "term_label": label}




def gpa_status(value: float | None) -> str:
    if value is None:
        return "No grades yet"
    if value >= 3.0:
        return "On track"
    if value >= 2.0:
        return "Watch"
    return "At risk"


def gpa_summary(db: Session, student: Student) -> dict:
    terms = terms_by_name(db)
    by_term = defaultdict(list)  # term name -> [(credits, grade_points)] of completed, graded enrollments
    for enrollment, course in _enrollments(db, student):
        if enrollment.status == "completed" and enrollment.grade_points is not None:
            by_term[enrollment.term].append((course.credits, enrollment.grade_points))

    ordered = sorted(by_term, key=lambda name: term_sort_key(name, terms))
    all_rows = [row for name in ordered for row in by_term[name]]
    cumulative = gpa(all_rows)
    change = None
    if len(ordered) >= 2:
        before = gpa([row for name in ordered[:-1] for row in by_term[name]])
        change = round(cumulative - before, 2)

    trend = [{"term": name, "gpa": gpa(by_term[name])} for name in ordered]

    current = current_enrollments(db, student)
    current_gpa = gpa((entry.course.credits, points_for(current_grade(entry.items))) for entry in current)
    if current_gpa is not None:
        trend.append({"term": current[0].enrollment.term, "gpa": current_gpa, "current": True})

    return {"cumulative": cumulative, "change": change, "status": gpa_status(cumulative), "trend": trend}


def _on_time_stat(db: Session, student: Student) -> dict:
    pct, on_time, total = on_time_rate(db, student)
    if pct is None:
        return {"key": "onTime", "label": "On-time submission", "value": "—", "pill": "No data", "tone": "gray",
                "pct": None, "warn": False, "note": "No assignments due yet"}
    pill, tone = ("Good", "teal") if pct >= 90 else ("Fair", "amber") if pct >= 75 else ("Low", "pink")
    return {"key": "onTime", "label": "On-time submission", "value": f"{pct}%", "pill": pill, "tone": tone, "pct": pct,
            "warn": pct < 75, "note": f"{on_time} of {total} submitted on time"}


def _credits_stat(earned: float, in_progress: float, required: float) -> dict:
    pct = round(earned / required * 100) if required else 0
    left = max(0, required - earned - in_progress)
    return {"key": "credits", "label": "Credits earned", "value": f"{earned:g} / {required:g}", "pill": f"{pct}%",
            "tone": "indigo", "pct": pct, "warn": False, "note": f"{in_progress:g} in progress · {left:g} left after this term"}


def _attendance_stat(current) -> dict:
    held = sum(entry.enrollment.sessions_held for entry in current)
    absences = sum(entry.enrollment.absences for entry in current)
    if held <= 0:
        return {"key": "attendance", "label": "Attendance", "value": "—", "pill": "No data", "tone": "gray",
                "pct": None, "warn": False, "note": "No classes recorded yet"}
    pct = round((1 - absences / held) * 100)
    pill, tone = ("Great", "teal") if pct >= 95 else ("Good", "teal") if pct >= 85 else ("Low", "pink")
    return {"key": "attendance", "label": "Attendance", "value": f"{pct}%", "pill": pill, "tone": tone, "pct": pct,
            "warn": pct < 85, "note": f"{absences} absence{'' if absences == 1 else 's'} this term"}


def stats(db: Session, student: Student) -> list[dict]:
    program = db.get(Program, student.program_id)
    required = float(program.total_required_credits)
    current = current_enrollments(db, student)
    earned = sum(float(course.credits) for enrollment, course in _enrollments(db, student) if enrollment.status == "completed")
    in_progress = sum(float(entry.course.credits) for entry in current)
    credits = _credits_stat(earned, in_progress, required)
    remaining = max(0, required - earned)

    return [
        _on_time_stat(db, student),
        credits,
        _attendance_stat(current),
        # Spec 23 (approvals) adds "Confirmed" / "Pending capstone approval".
        {"key": "graduation", "label": "Expected graduation", "value": student.expected_graduation or "—",
         "pill": "Planned", "tone": "indigo", "pct": credits["pct"], "warn": False,
         "note": f"{remaining:g} credits to go"},
    ]


def requirements_summary(db: Session, student: Student) -> list[dict]:
    """Per requirement group: courses done / in progress. Spec 12's degree_audit replaces this."""
    upcoming = next_term(db)
    registration_soon = (
        upcoming is not None and upcoming.registration_opens is not None
        and (upcoming.registration_opens - today()).days <= WARN_WITHIN_DAYS
    )
    rows = []
    for group in requirement_status(db, student):
        done, doing, required = group["done"], group["in_progress"], group["required_credits"]
        count = f"{done} done · {doing} in progress" if doing else f"{done} of {group['needed']}"
        pct = min(100, round(done * CREDITS_PER_COURSE / required * 100)) if required else 100
        rows.append({"label": group["label"], "count": count, "pct": pct,
                     "warn": done == 0 and doing == 0 and registration_soon})
    return rows


def study_hours(db: Session, student: Student) -> dict:
    day = today()
    monday = day - timedelta(days=day.weekday())
    hours = defaultdict(float)
    sessions = db.query(StudySession).filter(
        StudySession.student_id == student.student_id,
        StudySession.day >= monday,
        StudySession.day <= monday + timedelta(days=6),
    )
    for session in sessions:
        hours[session.day] += float(session.hours)

    days = []
    for offset, name in enumerate(DAY_NAMES):
        current = monday + timedelta(days=offset)
        days.append({"day": name, "hours": round(hours[current], 1), "today": current == day})
    return {"total": round(sum(hours.values()), 1), "goal": float(student.study_goal_hours), "days": days}


def today_events(db: Session, student: Student) -> dict:
    """Today's classes, personal events and meetings, from the schedule (spec 14)."""
    day = today()
    return {"label": day_label(day), "events": events_for_day(db, student, day)}


def current_courses(db: Session, student: Student) -> list[dict]:
    return [
        {
            "code": entry.course.course_code,
            "name": entry.course.course_name,
            "prof": (entry.section.instructor_name if entry.section else None) or "",
            "pct": entry.enrollment.progress_pct,
            "grade": current_grade(entry.items),
            "tone": entry.tone,
        }
        for entry in current_enrollments(db, student)
    ]
