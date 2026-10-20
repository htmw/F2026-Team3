"""CSV data import (spec 35): courses, enrollments and grades. A header row is required; bad rows are skipped and
reported by line, the rest are upserted in one transaction. Imports write the published tables directly (a data
load, not a catalog draft). GPA and credits are computed from enrollments, so dashboards update by themselves."""
import csv
import io
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import bad_request, conflict
from core.time import now
from models import Course, CourseSection, Enrollment, GradeItem, ImportJob, Integration, Student, Term, User
from services import audit, integrations
from services.academics import POINTS
from services.admin_users import MAX_IMPORT_BYTES, MAX_IMPORT_ROWS  # noqa: F401 (re-exported for the router)
from services.ai import recommend

HEADERS = {
    "courses": [["code", "name", "credits", "type", "description"]],
    "enrollments": [["student_email", "course_code", "term", "status"]],
    "grades": [["student_email", "course_code", "term", "grade", "grade_points"],
               ["student_email", "course_code", "term", "component", "weight", "score"]],
}
COURSE_TYPES = ("Foundation", "Core", "Elective", "Capstone")
STATUSES = ("in_progress", "completed", "failed", "withdrawn")  # matches the enrollment_status enum
CODE = re.compile(r"^[A-Z]{2,4} \d{3}[A-Z]?$")


class Skip(Exception):
    """A row that can't be imported; the message is the reason shown to the admin."""


def _number(raw: str, field: str, low: float, high: float, blank_ok: bool = False) -> float | None:
    if not raw:
        if blank_ok:
            return None
        raise Skip(f"Missing {field}")
    try:
        value = float(raw)
    except ValueError:
        raise Skip(f"{field.capitalize()} must be a number") from None
    if not low <= value <= high:
        raise Skip(f"{field.capitalize()} must be between {low:g} and {high:g}")
    return value


class _Lookups:
    """Students, courses and terms resolved once per file."""

    def __init__(self, db: Session):
        self.db = db
        self.courses = {course.course_code.upper(): course for course in db.query(Course)}
        self.terms = {term.name.lower(): term for term in db.query(Term)}

    def student(self, email: str) -> Student:
        if not email:
            raise Skip("Missing student_email")
        student = (self.db.query(Student).join(User, User.user_id == Student.user_id)
                   .filter(func.lower(User.email) == email.lower()).one_or_none())
        if student is None:
            raise Skip(f"No student with email {email}")
        return student

    def course(self, code: str) -> Course:
        course = self.courses.get(" ".join(code.split()).upper())
        if course is None:
            raise Skip(f"Unknown course {code}" if code else "Missing course_code")
        return course

    def term(self, name: str) -> Term:
        term = self.terms.get(" ".join(name.split()).lower())
        if term is None:
            raise Skip(f"Unknown term {name}" if name else "Missing term")
        return term

    def enrollment(self, student: Student, course: Course, term: Term) -> Enrollment | None:
        return (self.db.query(Enrollment).filter(Enrollment.student_id == student.student_id,
                                                 Enrollment.course_id == course.course_id, Enrollment.term == term.name)
                .order_by(Enrollment.enrollment_id).first())


def _course_row(db: Session, look: _Lookups, row: dict) -> bool:
    code = " ".join(row["code"].split()).upper()
    if not CODE.match(code):
        raise Skip(f'Course code "{row["code"]}" should look like "CS 612"')
    name = row["name"]
    if not name or len(name) > 200:
        raise Skip("Name must be 1 to 200 characters")
    credits = _number(row["credits"], "credits", 1, 6)
    kind = (row["type"] or "Elective").capitalize()
    if kind not in COURSE_TYPES:
        raise Skip(f'Unknown type "{row["type"]}" (use {", ".join(COURSE_TYPES)})')
    course = look.courses.get(code)
    created = course is None
    if created:
        course = Course(course_code=code)
        db.add(course)
        look.courses[code] = course
    course.course_name, course.credits, course.type = name, credits, kind
    course.description = row["description"] or course.description
    return created


def _enrollment_row(db: Session, look: _Lookups, row: dict) -> bool:
    student, course, term = look.student(row["student_email"]), look.course(row["course_code"]), look.term(row["term"])
    status = row["status"].lower()
    if status not in STATUSES:
        raise Skip(f'Unknown status "{row["status"]}" (use {", ".join(STATUSES)})')
    enrollment = look.enrollment(student, course, term)
    created = enrollment is None
    if created:
        enrollment = Enrollment(student_id=student.student_id, course_id=course.course_id, term=term.name)
        db.add(enrollment)
    enrollment.status = status
    if status == "in_progress" and enrollment.section_id is None:
        section = (db.query(CourseSection).filter(CourseSection.course_id == course.course_id,
                                                  CourseSection.term_id == term.id).order_by(CourseSection.id).first())
        enrollment.section_id = section.id if section else None
    return created


def _grade_row(db: Session, look: _Lookups, row: dict) -> bool:
    student, course, term = look.student(row["student_email"]), look.course(row["course_code"]), look.term(row["term"])
    enrollment = look.enrollment(student, course, term)
    if "component" in row:
        if enrollment is None:
            raise Skip(f"{student.name} isn't enrolled in {course.course_code} in {term.name}")
        label = row["component"]
        if not label or len(label) > 80:
            raise Skip("Component must be 1 to 80 characters")
        weight = _number(row["weight"], "weight", 0, 100)
        score = _number(row["score"], "score", 0, 100, blank_ok=True)
        item = db.query(GradeItem).filter(GradeItem.enrollment_id == enrollment.enrollment_id,
                                          func.lower(GradeItem.label) == label.lower()).first()
        created = item is None
        if created:
            item = GradeItem(enrollment_id=enrollment.enrollment_id, label=label, sort=99)
            db.add(item)
        item.weight, item.score = weight, score
        return created

    grade = row["grade"].upper()
    if grade not in POINTS:
        raise Skip(f'Unknown grade "{row["grade"]}"')
    points = _number(row["grade_points"], "grade_points", 0, 4, blank_ok=True)
    created = enrollment is None
    if created:
        enrollment = Enrollment(student_id=student.student_id, course_id=course.course_id, term=term.name)
        db.add(enrollment)
    enrollment.status = "failed" if grade == "F" else "completed"
    enrollment.grade = grade
    enrollment.grade_points = POINTS[grade] if points is None else points
    return created


APPLY = {"courses": _course_row, "enrollments": _enrollment_row, "grades": _grade_row}


def _parse(kind: str, text: str) -> tuple[list[str], list[tuple[int, dict]]]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in next(reader, None) or []]
    if header not in HEADERS[kind]:
        expected = " or ".join(",".join(h) for h in HEADERS[kind])
        raise bad_request(f"The first line must be the header: {expected}.")
    rows = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        cells = [cell.strip() for cell in row]
        if len(cells) > len(header):
            rows.append((reader.line_num, None))  # reported as "Too many columns"
        else:
            rows.append((reader.line_num, dict(zip(header, cells + [""] * (len(header) - len(cells))))))
    if not rows:
        raise bad_request("The file has no rows.")
    if len(rows) > MAX_IMPORT_ROWS:
        raise bad_request(f"Import at most {MAX_IMPORT_ROWS:,} rows at a time.")
    return header, rows


def run(db: Session, admin: User, kind: str, text: str, filename: str | None = None, ip: str | None = None) -> dict:
    integration = db.get(Integration, "csv")
    if integration is None or not integration.enabled:
        raise conflict("Connect CSV data import first.")
    _, rows = _parse(kind, text)
    look = _Lookups(db)
    created = updated = 0
    skipped = []
    for line, row in rows:
        if row is None:
            skipped.append({"line": line, "reason": "Too many columns"})
            continue
        try:
            with db.begin_nested():  # a row that fails half-way is rolled back on its own
                if APPLY[kind](db, look, row):
                    created += 1
                else:
                    updated += 1
        except Skip as reason:
            skipped.append({"line": line, "reason": str(reason)})

    count = created + updated
    message = f"Imported {count:,} {kind}"
    job = ImportJob(type=kind, filename=filename, body=text, created=created, updated=updated, skipped=skipped,
                    actor_id=admin.user_id)
    db.add(job)
    integration.last_sync_at, integration.last_error = now(), None
    integrations.event(db, "csv", message)
    audit.record(db, admin, "import.run", message + (f" ({len(skipped)} skipped)" if skipped else ""),
                 ("import", kind), {"created": created, "updated": updated, "skipped": len(skipped)}, ip=ip)
    db.commit()
    recommend._cache.clear()  # the dashboard recommendation may depend on what was imported
    return {"jobId": job.id, "created": created, "updated": updated, "skipped": skipped, "message": message}


def rerun_latest(db: Session, admin: User, ip: str | None = None) -> dict:
    """Sync now for the CSV integration: imports the newest file again."""
    job = db.query(ImportJob).order_by(ImportJob.created_at.desc(), ImportJob.id.desc()).first()
    if job is None:
        raise conflict("There's no import to run again yet. Upload a file first.")
    return run(db, admin, job.type, job.body, job.filename, ip=ip)
