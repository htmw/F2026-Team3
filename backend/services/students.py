from sqlalchemy.orm import Session

from core.deps import advisor_can_see
from core.errors import not_found
from models import Advisor, Course, Enrollment, Program, Student, User
from services.academics import gpa


def ensure_can_view(db: Session, user: User, student_id: int) -> None:
    """Admins see every student; advisors only the students assigned to them."""
    if user.role == "admin":
        return
    advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one_or_none()
    if advisor is None:
        raise not_found("Advisor profile")
    advisor_can_see(db, advisor.advisor_id, student_id)


def get_student_profile(db: Session, student_id: int):
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")

    program = db.get(Program, student.program_id)

    rows = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.student_id == student_id)
        .order_by(Enrollment.enrollment_id)
        .all()
    )

    enrollments = []
    graded = []  # (credits, grade_points) of completed enrollments
    completed_credits = 0.0

    for enrollment, course in rows:
        credits = float(course.credits)
        grade_points = (
            float(enrollment.grade_points)
            if enrollment.grade_points is not None
            else None
        )

        if enrollment.status == "completed":
            completed_credits += credits
            graded.append((credits, grade_points))

        enrollments.append({
            "enrollment_id": enrollment.enrollment_id,
            "course_id": course.course_id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "term": enrollment.term,
            "credits": credits,
            "status": enrollment.status,
            "grade": enrollment.grade,
            "grade_points": grade_points,
        })

    return {
        "student": {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "program_id": student.program_id,
            "program_name": program.program_name,
            "gpa": gpa(graded),
            "completed_credits": completed_credits,
            "total_required_credits": float(program.total_required_credits),
        },
        "enrollments": enrollments,
    }
