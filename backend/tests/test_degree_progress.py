"""Sprint 2 degree-progress calculation and access-control tests."""

from conftest import login

from models import (
    Course,
    Enrollment,
    Program,
    ProgramRequirement,
    Student,
)
from services.degree_progress import degree_progress


def build_degree_case(db, make_user):
    """
    Creates an isolated degree-progress test student.

    Program:
      Core      = 6 credits
      Elective  = 3 credits
      Capstone  = 3 credits
      Total     = 12 credits
    """
    user = make_user("student")

    program = Program(
        program_name=f"Degree Progress Test {user.user_id}",
        total_required_credits=12,
    )
    db.add(program)
    db.flush()

    student = Student(
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        program_id=program.program_id,
    )
    db.add(student)
    db.flush()

    core1 = Course(
        course_code=f"TCORE1-{user.user_id}",
        course_name="Test Core 1",
        credits=3,
        type="Core",
    )
    core2 = Course(
        course_code=f"TCORE2-{user.user_id}",
        course_name="Test Core 2",
        credits=3,
        type="Core",
    )
    elective = Course(
        course_code=f"TELEC-{user.user_id}",
        course_name="Test Elective",
        credits=3,
        type="Elective",
    )
    capstone = Course(
        course_code=f"TCAP-{user.user_id}",
        course_name="Test Capstone",
        credits=3,
        type="Capstone",
    )

    db.add_all([core1, core2, elective, capstone])
    db.flush()

    core = ProgramRequirement(
        program_id=program.program_id,
        group_name="Core",
        required_credits=6,
        required_courses=2,
        credits_per_course=3,
        sort=1,
        eligible_courses_ids=[core1.course_id, core2.course_id],
        requires_approval=False,
    )

    electives = ProgramRequirement(
        program_id=program.program_id,
        group_name="Electives",
        required_credits=3,
        required_courses=1,
        credits_per_course=3,
        sort=2,
        eligible_courses_ids=[elective.course_id],
        requires_approval=False,
    )

    capstone_req = ProgramRequirement(
        program_id=program.program_id,
        group_name="Capstone",
        required_credits=3,
        required_courses=1,
        credits_per_course=3,
        sort=3,
        eligible_courses_ids=[capstone.course_id],
        requires_approval=False,
    )

    db.add_all([core, electives, capstone_req])
    db.flush()

    return {
        "user": user,
        "student": student,
        "program": program,
        "core1": core1,
        "core2": core2,
        "elective": elective,
        "capstone": capstone,
    }


def add_enrollment(
    db,
    student,
    course,
    status,
    term,
    grade=None,
    grade_points=None,
):
    enrollment = Enrollment(
        student_id=student.student_id,
        course_id=course.course_id,
        term=term,
        status=status,
        grade=grade,
        grade_points=grade_points,
    )
    db.add(enrollment)
    db.flush()
    return enrollment


def test_degree_progress_normal_completed_courses(db, make_user):
    case = build_degree_case(db, make_user)

    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Fall 2025", "A", 4.0
    )
    add_enrollment(
        db, case["student"], case["core2"],
        "completed", "Spring 2026", "B", 3.0
    )
    add_enrollment(
        db, case["student"], case["elective"],
        "completed", "Fall 2026", "B+", 3.3
    )

    result = degree_progress(db, case["student"].student_id)

    assert result["required_credits"] == 12
    assert result["earned_credits"] == 9
    assert result["remaining_credits"] == 3
    assert result["completion_rate"] == 0.75

    groups = {row["group_name"]: row for row in result["requirements"]}

    assert groups["Core"]["earned_credits"] == 6
    assert groups["Core"]["is_satisfied"] is True

    assert groups["Electives"]["earned_credits"] == 3
    assert groups["Electives"]["is_satisfied"] is True

    assert groups["Capstone"]["earned_credits"] == 0
    assert groups["Capstone"]["is_satisfied"] is False

    db.rollback()


def test_failed_withdrawn_and_in_progress_do_not_count(db, make_user):
    case = build_degree_case(db, make_user)

    add_enrollment(
        db, case["student"], case["core1"],
        "failed", "Fall 2025", "F", 0.0
    )
    add_enrollment(
        db, case["student"], case["core2"],
        "withdrawn", "Spring 2026"
    )
    add_enrollment(
        db, case["student"], case["capstone"],
        "in_progress", "Spring 2027"
    )

    result = degree_progress(db, case["student"].student_id)

    assert result["earned_credits"] == 0
    assert result["remaining_credits"] == 12
    assert result["completion_rate"] == 0

    for requirement in result["requirements"]:
        assert requirement["earned_credits"] == 0
        assert requirement["is_satisfied"] is False

    db.rollback()


def test_failed_then_successful_repeat_counts(db, make_user):
    case = build_degree_case(db, make_user)

    add_enrollment(
        db, case["student"], case["core1"],
        "failed", "Fall 2025", "F", 0.0
    )
    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Spring 2026", "B", 3.0
    )

    result = degree_progress(db, case["student"].student_id)

    core = next(
        row
        for row in result["requirements"]
        if row["group_name"] == "Core"
    )

    assert core["earned_credits"] == 3
    assert result["earned_credits"] == 3

    db.rollback()


def test_repeated_completed_course_counts_only_once(db, make_user):
    case = build_degree_case(db, make_user)

    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Fall 2025", "B", 3.0
    )
    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Fall 2026", "A", 4.0
    )

    result = degree_progress(db, case["student"].student_id)

    core = next(
        row
        for row in result["requirements"]
        if row["group_name"] == "Core"
    )

    assert core["earned_credits"] == 3
    assert result["earned_credits"] == 3

    db.rollback()


def test_course_cannot_count_toward_two_groups(db, make_user):
    case = build_degree_case(db, make_user)

    # Make Core 1 eligible for Electives too.
    elective_requirement = (
        db.query(ProgramRequirement)
        .filter(
            ProgramRequirement.program_id == case["program"].program_id,
            ProgramRequirement.group_name == "Electives",
        )
        .one()
    )

    elective_requirement.eligible_courses_ids = [
        case["core1"].course_id,
        case["elective"].course_id,
    ]

    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Fall 2025", "A", 4.0
    )

    db.flush()

    result = degree_progress(db, case["student"].student_id)

    groups = {row["group_name"]: row for row in result["requirements"]}

    assert groups["Core"]["earned_credits"] == 3
    assert groups["Electives"]["earned_credits"] == 0
    assert result["earned_credits"] == 3

    db.rollback()


def test_completion_rate_never_exceeds_one(db, make_user):
    case = build_degree_case(db, make_user)

    add_enrollment(
        db, case["student"], case["core1"],
        "completed", "Fall 2025", "A", 4.0
    )
    add_enrollment(
        db, case["student"], case["core2"],
        "completed", "Spring 2026", "A", 4.0
    )
    add_enrollment(
        db, case["student"], case["elective"],
        "completed", "Fall 2026", "A", 4.0
    )
    add_enrollment(
        db, case["student"], case["capstone"],
        "completed", "Spring 2027", "A", 4.0
    )

    result = degree_progress(db, case["student"].student_id)

    assert result["earned_credits"] == 12
    assert result["remaining_credits"] == 0
    assert result["completion_rate"] == 1.0

    db.rollback()


def test_student_can_view_own_degree_progress(client):
    login(client, "amara.okafor@pac.edu")

    response = client.get("/api/v1/students/me/degree-progress")

    assert response.status_code == 200

    data = response.json()

    assert data["studentId"] == 101
    assert data["requiredCredits"] > 0
    assert 0 <= data["completionRate"] <= 1


def test_student_cannot_view_another_student_degree_progress(client):
    login(client, "amara.okafor@pac.edu")

    response = client.get("/api/v1/students/102/degree-progress")

    assert response.status_code == 403


def test_admin_can_view_student_degree_progress(client, as_user):
    as_user("admin")

    response = client.get("/api/v1/students/101/degree-progress")

    assert response.status_code == 200
    assert response.json()["studentId"] == 101