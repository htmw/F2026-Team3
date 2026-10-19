from fastapi import FastAPI, HTTPException
from database import SessionLocal
from models import Student,Program,Enrollment,Course

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Acadmate backend is running!"}


@app.get("/api/v1/students/{student_id}")
def get_student(student_id: int):
    db = SessionLocal()

    try:
        student = (
            db.query(Student)
            .filter(Student.student_id == student_id)
            .first()
        )

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        return {
            "student_id": student.student_id,
            "user_id": student.user_id,
            "name": student.name,
            "email": student.email,
            "program_id": student.program_id,
            "program_name": student.program.program_name if student.program else None,
            "gpa": gpa,
            "completed_credits": completed_credits,
        }

    finally:
        db.close()


@app.get("/api/v1/students/{student_id}/academic-profile")
def get_academic_profile(student_id: int):
    db = SessionLocal()

    try:
        student = (
            db.query(Student)
            .filter(Student.student_id == student_id)
            .first()
        )

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

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

        for enrollment, course in enrollments:
            enrollment_data.append({
                "enrollment_id": enrollment.enrollment_id,
                "course_id": course.course_id,
                "course_code": course.course_code,
                "course_name": course.course_name,
                "term": enrollment.term,
                "credits": float(course.credits),
                "status": enrollment.status,
                "grade": enrollment.grade,
                "grade_points": (
                    float(enrollment.grade_points)
                    if enrollment.grade_points is not None
                    else None
                )
            })

        total_quality_points =0
        total_gpa_credits=0
        completeed_credits=0

        for enrollment,course in enrollments:
            if enrollment.status == "completed" and enrollment.grade_points is not None:
                credits=float(course.credits)
                grade_points=float(enrollment.grade_points)

                total_quality_points += float(enrollment.grade_points) * float(course.credits)
                total_gpa_credits += float(course.credits)
                completeed_credits += float(course.credits)

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
                "program_name": program.program_name if program else None
            },
            "enrollments": enrollment_data
        }

    finally:
        db.close()