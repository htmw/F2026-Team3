"""Requirement progress per program group, shared by the dashboard (spec 10) and the AI advisor (spec 13).
Spec 12's degree_audit takes this over; callers keep the same fields."""
from sqlalchemy.orm import Session

from models import Course, Enrollment, ProgramRequirement, Student

CREDITS_PER_COURSE = 3


def course_sets(db: Session, student: Student) -> tuple[set[int], set[int]]:
    """(completed course ids, in-progress course ids)."""
    completed, in_progress = set(), set()
    rows = db.query(Enrollment.course_id, Enrollment.status).filter(Enrollment.student_id == student.student_id)
    for course_id, status in rows:
        if status == "completed":
            completed.add(course_id)
        elif status == "in_progress":
            in_progress.add(course_id)
    return completed, in_progress


def credit_totals(db: Session, student: Student) -> tuple[float, float]:
    """(completed credits, in-progress credits) over all of the student's enrollments."""
    earned = in_progress = 0.0
    rows = (db.query(Enrollment.status, Course.credits).join(Course, Enrollment.course_id == Course.course_id)
            .filter(Enrollment.student_id == student.student_id))
    for status, credits in rows:
        if status == "completed":
            earned += float(credits)
        elif status == "in_progress":
            in_progress += float(credits)
    return earned, in_progress


def requirement_status(db: Session, student: Student) -> list[dict]:
    """One entry per requirement group of the student's program, in requirement order."""
    completed, in_progress = course_sets(db, student)
    groups = (db.query(ProgramRequirement).filter(ProgramRequirement.program_id == student.program_id)
              .order_by(ProgramRequirement.sort, ProgramRequirement.requirement_id).all())
    status = []
    for group in groups:
        required = float(group.required_credits)
        needed = group.required_courses
        eligible = list(group.eligible_courses_ids or [])
        done = min(len(set(eligible) & completed), needed)
        doing = min(len(set(eligible) & in_progress), needed - done)
        status.append({
            "id": group.requirement_id,
            "label": group.group_name,
            "required_credits": required,
            "needed": needed,
            "done": done,
            "in_progress": doing,
            "remaining": needed - done - doing,
            "eligible_ids": eligible,
            "requires_approval": bool(group.requires_approval),
        })
    return status
