import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from database import SessionLocal
from models import(
    User,
    Program,
    Student,
    Advisor,
    Course,
    Enrollment,
    AdvisorStudentAssignment,
    ProgramRequirement,
)
#Configuration

DRY_RUN=True

DATA_DIR=(
    Path(__file__).resolve().parents[1]
    /"data"
    /"synthetic"
)

#Helpers


def read_csv(filename):
    path = DATA_DIR / filename
    with path.open(newline="", encoding="utf-8") as file:

        return list(csv.DictReader(file))


def parse_bool(value):
    return value.strip().lower() =="true"

def parse_decimal(value):
    if value is None or value.strip() == "":
        return None
    return Decimal(value)

def parse_nullable_text(value):
    if value is None or value.strip() == "":
        return None
    return value

def parse_datetime(value):
    return datetime.fromisoformat(value)

def conflict(table, key, message):
    raise ValueError(f"Conflict in {table} for {key}: {message}")

#Import Counters
stats ={}

def initialize_stats(table_name):
    stats[table_name]={
        "inserted": 0,
        "identical_skipped": 0,
        "timestamp_skipped": 0,
    }


# Main Import
db = SessionLocal()

try:


    #1. Programs
    initialize_stats("programs")

    for row in read_csv("programs.csv"):
        program_id = int(row["program_id"])

        incoming= {
            "program_name": row["program_name"],
            "total_required_credits": Decimal(row["total_required_credits"]),
        }

        existing = db.get(Program, program_id)

        if existing:
            if(
                existing.program_name
                != incoming["program_name"]
                or Decimal(existing.total_required_credits)
                != incoming["total_required_credits"]
            ):
                conflict(
                    "programs",
                    program_id,
                    "Existing row differs from CSV"

                )

            stats["programs"]["identical_skipped"] += 1
        else:
            db.add(
                Program(
                    program_id=program_id,
                    **incoming
                )
            )

            stats["programs"]["inserted"] += 1


    db.flush()

    #2.Users

    initialize_stats("users")

    for row in read_csv("users.csv"):

        user_id = int(row["user_id"])

        incoming ={
            "name": row["name"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "is_active": parse_bool(
                row["is_active"]
            ),
        }

        existing = db.get(User, user_id)

        if existing:

            if any([
                existing.name != incoming["name"],
                existing.email != incoming["email"],
                existing.password_hash != incoming["password_hash"],
                existing.role != incoming["role"],
                existing.is_active != incoming["is_active"],
            ]):
                conflict(
                    "users",
                    user_id,
                    "existing row differs from CSV"
                )
            stats["users"]["identical_skipped"] += 1

        else:

            db.add(
                User(
                    user_id= user_id,
                    **incoming
                )
            )

            stats["users"]["inserted"] += 1


    db.flush()

    #Students

    initialize_stats("students")

    for row in read_csv("students.csv"):
        student_id = int(row["student_id"])

        incoming ={
            "user_id" : int(row["user_id"]),
            "name" : row["name"],
            "email": row["email"],
            "program_id": int(row["program_id"]),

        }

        existing = db.get(Student, student_id)

        if existing:

            if any([
                existing.user_id != incoming["user_id"],
                existing.name != incoming["name"],
                existing.email != incoming["email"],
                existing.program_id != incoming["program_id"],
            ]):

                conflict(
                    "students",
                    student_id,
                    "existing row differs from CSV"
                )
            stats["students"]["identical_skipped"] +=1
        else:

            db.add(
                Student(
                    student_id= student_id,
                    **incoming
                )
            )

            stats["students"]["inserted"] +=1
    db.flush()


    #Advisors

    initialize_stats("advisors")

    for row in read_csv("advisors.csv"):

        advisor_id = int(row["advisor_id"])
        user_id =int(row["user_id"])

        existing = db.get(Advisor, advisor_id)

        if existing:

            if existing.user_id != user_id:
                conflict(
                    "advisors",
                    advisor_id,
                    "user_id differs"
                )
            stats["advisors"]["identical_skipped"] += 1
        else:

            db.add(
                Advisor(
                    advisor_id = advisor_id,
                    user_id= user_id
                )
            )

            stats["advisors"]["inserted"] += 1
    db.flush()


    #Courses


    initialize_stats("courses")

    for row in read_csv("courses.csv"):

        course_id = int(row["course_id"])

        incoming={
            "course_code" : row["course_code"],
            "course_name": row["course_name"],
            "credits": Decimal(row["credits"]),
        }

        existing = db.get(Course, course_id)

        if existing:

            if any([
                existing.course_code != incoming["course_code"],
                existing.course_name != incoming["course_name"],
                Decimal(existing.credits) != incoming["credits"],
            ]):
                conflict(
                    "courses",
                    course_id,
                    "existing row differs from CSV"
                )
            stats["courses"]["identical_skipped"] += 1
        else:

            db.add(
                Course(
                    course_id= course_id,
                    **incoming

                )
            )

            stats["courses"]["inserted"] += 1

    db.flush()


    #Enrollments

    initialize_stats("enrollments")

    for row in read_csv("enrollments.csv"):

        enrollment_id = int(row["enrollment_id"])

        incoming ={
            "student_id": int(row["student_id"]),
            "course_id": int(row["course_id"]),
            "term": row["term"],
            "status": row["status"],
            "grade": parse_nullable_text(row["grade"]),
            "grade_points": parse_decimal(
                row["grade_points"]
            ),
        }


        existing = db.get(
            Enrollment,
            enrollment_id
        )


        if existing:
            existing_grade_points= (
                Decimal(existing.grade_points)
                if existing.grade_points is not None
                else None
            )


            if any([
                existing.student_id != incoming["student_id"],
                existing.course_id != incoming["course_id"],
                existing.term != incoming["term"],
                existing.status != incoming["status"],
                existing.grade != incoming["grade"],
                existing_grade_points != incoming["grade_points"],

            ]):
                conflict(
                    "enrollments",
                    enrollment_id,
                    "existing row differs from CSV"
                )
            stats["enrollments"]["identical_skipped"] += 1

        else:
            db.add(
                Enrollment(
                    enrollment_id=enrollment_id,
                    **incoming
                )
            )

            stats["enrollments"]["inserted"] += 1
    db.flush()


    #Advisor Assignments

    initialize_stats(
        "advisor_student_assignments"
    )

    for row in read_csv(
        "advisor_student_assignments.csv"
    ):

        student_id= int(row["student_id"])
        advisor_id = int(row["advisor_id"])

        incoming_timestamp = parse_datetime(
            row["updated_at"]
        )

        existing = db.get(
            AdvisorStudentAssignment,
            student_id
        )

        if existing:

            if existing.advisor_id != advisor_id:
                conflict(
                    "advisor_student_assignments",
                    student_id,
                    "advisor relationship differs"
                )

            if existing.updated_at == incoming_timestamp:

                stats[
                    "advisor_student_assignments"
                ]["identical_skipped"] +=1
            else:

                #approved time stamp only exception:
                # if student/advisor relationship is identical,
                # keep the existing Neon timestamp.

                stats["advisor_student_assignments"]["timestamp_skipped"] += 1
        else:

            db.add(
                AdvisorStudentAssignment(
                    student_id= student_id,
                    advisor_id= advisor_id,
                    updated_at= incoming_timestamp
                )
            )

            stats["advisor_student_assignments"]["inserted"] += 1
    db.flush()


    # Program Requirements

    initialize_stats("program_requirements")

    for row in read_csv("program_requirements.csv"):


        requirement_id = int(row["requirement_id"])

        eligible_course_ids = json.loads(
            row["eligible_course_ids"]

        )

        incoming = {
            "program_id": int(row["program_id"]),
            "group_name": row["group_name"],
            "required_credits": Decimal(row["required_credits"]),
            "eligible_course_ids": eligible_course_ids,
        }

        existing = db.get(
            ProgramRequirement,
            requirement_id
        )

        if existing:

            if any([
                existing.program_id != incoming["program_id"],
                existing.group_name != incoming["group_name"],
                Decimal(existing.required_credits) != incoming["required_credits"],
                list(existing.eligible_course_ids) != incoming["eligible_course_ids"],
            ]):
                conflict(
                    "program_requirements",
                    requirement_id,
                    "existing row differs from CSV"
                )
            stats["program_requirements"]["identical_skipped"] += 1
        else:

            db.add(
                ProgramRequirement(
                    requirement_id= requirement_id,
                    **incoming
                )
            )

            stats["program_requirements"]["inserted"] += 1

    db.flush()


    #Summary

    print("\n Synthetic dataset import summary:\n")

    for table, values in stats.items():
        print(table)


        print(
            "inserted:",
            values["inserted"]
        )

        print(
            "identical skipped:",
            values["identical_skipped"]
        )

        if values["timestamp_skipped"]:
            print(
                "timestamp-only skipped:",
                values["timestamp_skipped"]
            )


    #Commit/ Rollback


    if DRY_RUN:

        print(
            "\nDRY RUN enabled -"
            "rolling back all changes."
        )

        db.rollback()
    else:
        db.commit()

        print("\nSynthetic Dataset imported"
            "Successfully."
        )


except Exception as e:


    db.rollback()
    print("\nIMPORT FAILED")
    print(e)
    raise


finally:
    db.close()