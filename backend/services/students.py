from sqlalchemy.orm import Session

from models import Student, Program, Enrollment, Course


def get_student_profile(student_id: int, db: Session):
    student = (
        db.query(Student)
        .filter(Student.student_id == student_id)
        .first()
    )

    if student is None:
        return None

    program = (
        db.query(Program)
        .filter(Program.program_id == student.program_id)
        .first()
    )

    enrollments = (
        db.query(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.course_id)
        .filter(Enrollment.student_id == student_id)
        .all()
    )

    enrollment_data = []

    total_quality_points = 0
    total_gpa_credits = 0
    completed_credits = 0

    for enrollment, course in enrollments:
        credits = float(course.credits)

        enrollment_data.append({
            "enrollment_id": enrollment.enrollment_id,
            "course_id": course.course_id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "term": enrollment.term,
            "credits": credits,
            "status": enrollment.status,
            "grade": enrollment.grade,
            "grade_points": (
                float(enrollment.grade_points)
                if enrollment.grade_points is not None
                else None
            )
        })

        if (
            enrollment.status == "completed"
            and enrollment.grade_points is not None
        ):
            grade_points = float(enrollment.grade_points)

            total_quality_points += grade_points * credits
            total_gpa_credits += credits
            completed_credits += credits

    gpa = (
        round(total_quality_points / total_gpa_credits, 2)
        if total_gpa_credits > 0
        else None
    )

    return {
        "student": {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "program_id": student.program_id,
            "program_name": program.program_name if program else "",
            "gpa": gpa,
            "completed_credits": completed_credits,
            "total_required_credits": (
                float(program.total_required_credits)
                if program else 0
            )
        },
        "enrollments": enrollment_data
    }