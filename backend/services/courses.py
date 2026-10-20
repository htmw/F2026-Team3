"""My courses (spec 11): current courses with sections and grade items, weekly timetable, completed courses,
and per-course grade breakdowns. Also the source of "current courses" for the dashboard (spec 10)."""
from collections import defaultdict
from datetime import time
from typing import NamedTuple

from sqlalchemy.orm import Session

from core.errors import bad_request, forbidden, not_found
from core.time import DAY_NAMES, short_date, today
from models import Course, CourseSection, Enrollment, GradeItem, Student, User
from services.academics import current_grade, gpa, letter_for, next_letter_up, weighted_score
from services import plan
from services.catalog import current_term, term_sort_key, terms_by_name
from services.students import ensure_can_view

COURSE_TONES = ("teal", "indigo", "amber", "pink")
WEEKDAYS = DAY_NAMES[:5]
EXAM_WORDS = ("midterm", "exam", "final")
INSIGHT_EXAM_WITHIN_DAYS = 21
INSIGHT_LOW_SCORE = 88
INSIGHT_AHEAD_SCORE = 94


class CurrentCourse(NamedTuple):
    enrollment: Enrollment
    course: Course
    section: CourseSection | None
    items: list[GradeItem]
    tone: str


def course_tone(index: int) -> str:
    return COURSE_TONES[index % len(COURSE_TONES)]


def current_enrollments(db: Session, student: Student) -> list[CurrentCourse]:
    """In-progress enrollments of the current term, ordered by course code, with section, grade items and chip tone."""
    term = current_term(db)
    if term is None:
        return []
    rows = (
        db.query(Enrollment, Course, CourseSection)
        .join(Course, Enrollment.course_id == Course.course_id)
        .outerjoin(CourseSection, Enrollment.section_id == CourseSection.id)
        .filter(Enrollment.student_id == student.student_id, Enrollment.status == "in_progress", Enrollment.term == term.name)
        .order_by(Course.course_code)
        .all()
    )
    items = defaultdict(list)
    ids = [enrollment.enrollment_id for enrollment, _, _ in rows]
    if ids:
        for item in db.query(GradeItem).filter(GradeItem.enrollment_id.in_(ids)).order_by(GradeItem.sort, GradeItem.id):
            items[item.enrollment_id].append(item)
    return [CurrentCourse(enrollment, course, section, items[enrollment.enrollment_id], course_tone(index))
            for index, (enrollment, course, section) in enumerate(rows)]


def meeting_days(section: CourseSection | None) -> list[str]:
    if section is None or not section.meeting_days:
        return []
    return [day.strip() for day in section.meeting_days.split(",") if day.strip()]


def when_text(section: CourseSection | None) -> str:
    """"Thu 10:00–12:45" (days joined with "/")."""
    if section is None or section.start_time is None:
        return ""
    days = "/".join(meeting_days(section))
    span = section.start_time.strftime("%H:%M")
    if section.end_time is not None:
        span += "–" + section.end_time.strftime("%H:%M")
    return f"{days} {span}".strip()


def _clock(value: time) -> tuple[str, str]:
    hour = value.hour % 12 or 12
    text = f"{hour}:{value.minute:02d}" if value.minute else str(hour)
    return text, "am" if value.hour < 12 else "pm"


def office_text(section: CourseSection | None) -> str | None:
    """Office hours display text: section.office_hours, else built from day and times ("Wed 2–3 pm")."""
    if section is None:
        return None
    if section.office_hours:
        return section.office_hours
    if not (section.office_day and section.office_start and section.office_end):
        return None
    start, start_suffix = _clock(section.office_start)
    end, end_suffix = _clock(section.office_end)
    span = f"{start}–{end} {end_suffix}" if start_suffix == end_suffix else f"{start} {start_suffix}–{end} {end_suffix}"
    return f"{section.office_day} {span}"


def _is_exam(item: GradeItem) -> bool:
    return any(word in item.label.lower() for word in EXAM_WORDS)


def _pending(items: list[GradeItem]) -> list[GradeItem]:
    """Ungraded items due today or later, soonest first."""
    day = today()
    pending = [item for item in items if item.score is None and item.due_date is not None and item.due_date >= day]
    return sorted(pending, key=lambda item: item.due_date)


def next_item(items: list[GradeItem]) -> str | None:
    """"Midterm · Oct 19". Spec 15 adds the course's assignments as a source."""
    pending = _pending(items)
    return f"{pending[0].label} · {short_date(pending[0].due_date)}" if pending else None


def upcoming(items: list[GradeItem], limit: int = 2) -> list[dict]:
    return [
        {
            "date": item.due_date.isoformat(),
            "mon": short_date(item.due_date).split()[0],
            "day": str(item.due_date.day),
            "title": item.label,
            "meta": f"{float(item.weight):g}% of grade" if float(item.weight) > 0 else "Not graded separately",
        }
        for item in _pending(items)[:limit]
    ]


def _article(letter: str) -> str:
    return "an" if letter[:1] in ("A", "F") else "a"


def insight(current: CurrentCourse) -> str | None:
    """Rule-based tip, first match wins. Spec 15 adds the "assignment due in ≤ 2 days with no draft" rule first.
    Callers skip it when the AI setting features.gradeInsights is off (spec 34)."""
    graded = [item for item in current.items if item.score is not None]
    if not graded:
        return None
    lowest = min(graded, key=lambda item: float(item.score))
    exams = [item for item in _pending(current.items)
             if _is_exam(item) and (item.due_date - today()).days <= INSIGHT_EXAM_WITHIN_DAYS]
    if float(lowest.score) < INSIGHT_LOW_SCORE and exams:
        exam = exams[0]
        target = next_letter_up(current_grade(current.items))
        return (f"{lowest.label} are your lowest component this term. Two office-hour visits before the "
                f"{short_date(exam.due_date)} {exam.label.lower()} could lift this toward {_article(target)} {target}.")
    if all(float(item.score) >= INSIGHT_AHEAD_SCORE for item in graded):
        return f"You are ahead of pace in {current.course.course_code}. Keep your current study rhythm."
    return None


def course_card(current: CurrentCourse, insights: bool = True) -> dict:
    enrollment, course, section = current.enrollment, current.course, current.section
    credits = float(course.credits)
    return {
        "course_id": course.course_id,
        "enrollment_id": enrollment.enrollment_id,
        "code": course.course_code,
        "name": course.course_name,
        "credits": f"{credits:g} credit{'' if credits == 1 else 's'}",
        "prof": (section.instructor_name if section else None) or "",
        "when": when_text(section),
        "room": f"Room {section.room}" if section and section.room else "",
        "office": office_text(section),
        "site_url": section.site_url if section else None,
        "pct": enrollment.progress_pct,
        "grade": current_grade(current.items),
        "tone": current.tone,
        "next": next_item(current.items),
        "insight": insight(current) if insights else None,
        "upcoming": upcoming(current.items),
    }


def week_grid(current: list[CurrentCourse]) -> list[dict]:
    """Mon–Fri class meetings, plus one office-hours slot for the course with the soonest exam."""
    days = {name: [] for name in WEEKDAYS}
    for entry in current:
        section = entry.section
        if section is None or section.start_time is None:
            continue
        for day in meeting_days(section):
            if day in days:
                days[day].append({"time": section.start_time.strftime("%H:%M"), "code": entry.course.course_code,
                                  "room": f"Room {section.room}" if section.room else "", "tone": entry.tone, "kind": "class"})

    exams = [(item.due_date, entry) for entry in current for item in _pending(entry.items) if _is_exam(item)]
    if exams:
        _, entry = min(exams, key=lambda pair: (pair[0], pair[1].course.course_code))
        section = entry.section
        if section and section.office_day in days and section.office_start:
            days[section.office_day].append({"time": section.office_start.strftime("%H:%M"), "code": entry.course.course_code,
                                             "room": "Office hrs", "tone": "gray", "kind": "office"})

    return [{"day": name, "items": sorted(items, key=lambda item: item["time"])} for name, items in days.items()]


def completed(db: Session, student: Student) -> list[dict]:
    """Completed enrollments, newest term first."""
    terms = terms_by_name(db)
    rows = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.student_id == student.student_id, Enrollment.status == "completed")
        .all()
    )
    rows.sort(key=lambda row: row[1].course_code)
    rows.sort(key=lambda row: term_sort_key(row[0].term, terms), reverse=True)  # stable: codes stay A→Z within a term
    return [
        {"course_id": course.course_id, "code": course.course_code, "name": course.course_name,
         "term": enrollment.term, "credits": float(course.credits), "grade": enrollment.grade or "—",
         "grade_points": enrollment.grade_points}
        for enrollment, course in rows
    ]


def subtitle(term_name: str | None, current: list[CurrentCourse]) -> str:
    if term_name is None:
        return "No current term"
    count = len(current)
    credits = sum(float(entry.course.credits) for entry in current)
    return f"{term_name} · {count} course{'' if count == 1 else 's'} · {credits:g} credits in progress"


def my_courses(db: Session, student: Student) -> dict:
    from services.ai import settings as ai_config  # imported here: services.ai imports this module
    insights = ai_config.ai_settings(db)["features"]["gradeInsights"]
    term = current_term(db)
    current = current_enrollments(db, student)
    done = completed(db, student)
    planned = plan.planned_courses(db, student)
    return {
        "subtitle": subtitle(term.name if term else None, current),
        "add_drop_url": None,  # spec 37: registrar link from institution settings
        "counts": {"current": len(current), "completed": len(done), "planned": len(planned)},
        "current": [course_card(entry, insights) for entry in current],
        "week": week_grid(current),
        "completed": done,
        "completed_summary": {
            "credits": sum(row["credits"] for row in done),
            "gpa": gpa((row["credits"], row["grade_points"]) for row in done),
        },
        "planned_notice": plan.registration_notice(db, student),
        "planned": planned,
    }


def _grade_display(item: GradeItem) -> str:
    if item.score is not None:
        return f"{float(item.score):g}%"
    if item.status_text:
        return item.status_text
    if item.due_date is not None:
        return short_date(item.due_date)
    return "—"


def grades_for(db: Session, user: User, course_id: int, student_id: int | None = None) -> dict:
    """A student sees courses they take this term; an advisor (assigned) or admin passes studentId."""
    if db.get(Course, course_id) is None:
        raise not_found("Course")
    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user.user_id).one_or_none()
        if student is None:
            raise not_found("Student profile")
    else:
        if student_id is None:
            raise bad_request("Choose a student (studentId) to see their grades.")
        ensure_can_view(db, user, student_id)
        student = db.get(Student, student_id)
        if student is None:
            raise not_found("Student")

    entry = next((entry for entry in current_enrollments(db, student) if entry.course.course_id == course_id), None)
    if entry is None:
        if user.role == "student":
            raise forbidden("You aren't enrolled in this course this term.")
        raise not_found("Enrollment")

    parts = [
        {"label": item.label, "weight": float(item.weight),
         "score": float(item.score) if item.score is not None else None, "display": _grade_display(item)}
        for item in entry.items
        if float(item.weight) > 0  # zero-weight checkpoints are deadlines, not grade components
    ]
    score = weighted_score(entry.items)
    return {"parts": parts, "weighted_score": score, "letter": letter_for(score) if score is not None else None}
