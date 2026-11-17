from sqlalchemy.orm import Session

from core.errors import not_found
from models import Program, Student
from services.degree_audit import assign_groups, student_courses


def degree_progress(db: Session, student_id: int) -> dict:
    student = db.get(Student, student_id)

    if student is None:
        raise not_found("Student")

    program = db.get(Program, student.program_id)

    if program is None:
        raise not_found("Program")

    # student_courses() already:
    # - removes failed / withdrawn enrollments
    # - ignores F grades
    # - deduplicates repeated courses
    courses = student_courses(db, student)

    # Degree progress only counts completed courses.
    completed_courses = [
        row for row in courses
        if row.state == "completed"
    ]

    # assign_groups() guarantees that one course counts
    # toward only one requirement group.
    groups = assign_groups(
        db,
        student,
        completed_courses
    )

    requirement_results = []
    total_earned = 0.0

    for group in groups:
        required_credits = float(group.requirement.required_credits)

        earned_credits = sum(
            float(row.course.credits)
            for row in group.taken
            if row.state == "completed"
        )

        # Never give more credit than the requirement actually needs.
        earned_credits = min(
            earned_credits,
            required_credits
        )

        remaining_credits = max(
            required_credits - earned_credits,
            0.0
        )

        requirement_results.append({
            "requirement_id": group.requirement.requirement_id,
            "group_name": group.requirement.group_name,
            "required_credits": required_credits,
            "earned_credits": earned_credits,
            "remaining_credits": remaining_credits,
            "is_satisfied": remaining_credits == 0,
            "eligible_course_ids": group.requirement.eligible_courses_ids or [],
        })

        total_earned += earned_credits

    required_credits = float(program.total_required_credits)

    # Never report more credits than the program requires.
    total_earned = min(
        total_earned,
        required_credits
    )

    remaining_credits = max(
        required_credits - total_earned,
        0.0
    )

    completion_rate = (
        min(total_earned / required_credits, 1.0)
        if required_credits > 0
        else 1.0
    )

    return {
        "student_id": student.student_id,
        "program_id": student.program_id,
        "required_credits": required_credits,
        "earned_credits": total_earned,
        "remaining_credits": remaining_credits,
        "completion_rate": completion_rate,
        "requirements": requirement_results,
    }