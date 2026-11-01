import csv
from pathlib import Path

DATA_DIR = Path("data") / "synthetic"


def read_csv(filename):
    path = DATA_DIR / filename

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows, fieldnames):
    path = DATA_DIR / filename

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# 1. PROGRAM
# ============================================================

programs = read_csv("programs.csv")

for row in programs:
    row["program_id"] = "2"
    row["program_name"] = "MS Computer Science (Synthetic)"

write_csv(
    "programs.csv",
    programs,
    [
        "program_id",
        "program_name",
        "total_required_credits",
    ],
)


# ============================================================
# 2. USERS
# Remove legacy Santos and duplicate Sarah rows.
# ============================================================

users = read_csv("users.csv")

users = [
    row
    for row in users
    if int(row["user_id"]) not in {1, 2}
]

write_csv(
    "users.csv",
    users,
    [
        "user_id",
        "name",
        "email",
        "password_hash",
        "role",
        "is_active",
    ],
)


# ============================================================
# 3. STUDENTS
# Remove legacy student 101 (Santos).
# Move all synthetic students to program 2.
# ============================================================

students = read_csv("students.csv")

students = [
    row
    for row in students
    if int(row["student_id"]) != 101
]

for row in students:
    row["program_id"] = "2"

write_csv(
    "students.csv",
    students,
    [
        "student_id",
        "user_id",
        "name",
        "email",
        "program_id",
    ],
)


# ============================================================
# 4. COURSES
# Current main already owns IDs 11, 12 and 13.
# Synthetic requirements can reuse those current courses.
# ============================================================

courses = read_csv("courses.csv")

courses = [
    row
    for row in courses
    if int(row["course_id"]) not in {11, 12, 13}
]

write_csv(
    "courses.csv",
    courses,
    [
        "course_id",
        "course_code",
        "course_name",
        "credits",
    ],
)


# ============================================================
# 5. ENROLLMENTS
# Remove all old Santos/student-101 enrollments.
# ============================================================

enrollments = read_csv("enrollments.csv")

enrollments = [
    row
    for row in enrollments
    if int(row["student_id"]) != 101
]

write_csv(
    "enrollments.csv",
    enrollments,
    [
        "enrollment_id",
        "student_id",
        "course_id",
        "term",
        "status",
        "grade",
        "grade_points",
    ],
)


# ============================================================
# 6. ADVISOR ASSIGNMENTS
# Remove Santos assignment.
# Sarah advisor 201 remains valid and may advise synthetic students.
# ============================================================

assignments = read_csv(
    "advisor_student_assignments.csv"
)

assignments = [
    row
    for row in assignments
    if int(row["student_id"]) != 101
]

write_csv(
    "advisor_student_assignments.csv",
    assignments,
    [
        "student_id",
        "advisor_id",
        "updated_at",
    ],
)


# ============================================================
# 7. PROGRAM REQUIREMENTS
# Move to program 2 and avoid IDs 401-404.
# ============================================================

requirements = read_csv(
    "program_requirements.csv"
)

new_requirement_ids = [
    10400,
    10401,
    10402,
]

if len(requirements) != len(new_requirement_ids):
    raise ValueError(
        "Expected exactly 3 synthetic program requirements."
    )

for index, row in enumerate(requirements):
    row["requirement_id"] = str(
        new_requirement_ids[index]
    )

    row["program_id"] = "2"

write_csv(
    "program_requirements.csv",
    requirements,
    [
        "requirement_id",
        "program_id",
        "group_name",
        "required_credits",
        "eligible_course_ids",
    ],
)


print("Synthetic dataset updated successfully.")
print()
print("Current seeded data was preserved.")
print("Synthetic program ID: 2")
print("Legacy Santos records removed.")
print("Existing advisor 201 reused.")
print("Existing courses 11, 12 and 13 reused.")