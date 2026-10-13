from datetime import datetime, timezone

from database import SessionLocal
from models import (
    User,
    Program,
    Student,
    Advisor,
    Course,
    Enrollment,
    AdvisorStudentAssignment,
    ProgramRequirement,
)


db = SessionLocal()

try:
    program = Program(
        program_id=1,
        program_name="MS Computer Science",
        total_required_credits=30
    )

    db.add(program)

    student_user = User(
        user_id=1,
        name="Santos Shel",
        email="santos.shel@pac.edu",
        password_hash="demo_hash_student",
        role="student",
        is_active=True
    )

    advisor_user = User(
        user_id=2,
        name="Dr. Sarah Smith",
        email="sarah.smith@pac.edu",
        password_hash="demo_hash_advisor",
        role="advisor",
        is_active=True
    )

    db.add_all([
        student_user,
        advisor_user
    ])

    db.flush()

    student = Student(
        student_id=101,
        user_id=1,
        name="Santos Shel",
        email="santos.shel@pac.edu",
        program_id=1
    )

    db.add(student)

    advisor = Advisor(
        advisor_id=201,
        user_id=2
    )

    db.add(advisor)


    course1 = Course(
        course_id=11,
        course_code="CS501",
        course_name="Programming Foundations with Java",
        credits=3
    )

    course2 = Course(
        course_id=12,
        course_code="CS510",
        course_name="Data Structures and Algorithms",
        credits=3
    )

    course3 = Course(
        course_id=13,
        course_code="CS620",
        course_name="Database Management Systems",
        credits=3
    )

    db.add_all([
        course1,
        course2,
        course3
    ])

    db.flush()

    # -------------------------------------------------
    # Enrollments
    # -------------------------------------------------

    enrollment1 = Enrollment(
        enrollment_id=301,
        student_id=101,
        course_id=11,
        term="Fall 2026",
        status="completed",
        grade="A",
        grade_points=4.0
    )

    enrollment2 = Enrollment(
        enrollment_id=302,
        student_id=101,
        course_id=12,
        term="Fall 2026",
        status="completed",
        grade="B",
        grade_points=3.0
    )

    enrollment3 = Enrollment(
        enrollment_id=303,
        student_id=101,
        course_id=13,
        term="Spring 2027",
        status="in_progress",
        grade=None,
        grade_points=None
    )

    db.add_all([
        enrollment1,
        enrollment2,
        enrollment3
    ])

    assignment = AdvisorStudentAssignment(
        student_id=101,
        advisor_id=201,
        updated_at=datetime.now(timezone.utc)
    )

    db.add(assignment)

    requirement = ProgramRequirement(
        requirement_id=401,
        program_id=1,
        group_name="Core",
        required_credits=9,
        eligible_courses_ids=[11, 12, 13]
    )

    db.add(requirement)

    db.commit()

    print("Demo data inserted successfully.")

except Exception as e:
    db.rollback()

    print("Failed to insert demo data:")
    print(e)

finally:
    db.close()