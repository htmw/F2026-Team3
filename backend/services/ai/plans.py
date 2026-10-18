"""Plan blocks: course codes in text, and validation of proposed plan rows against the catalog. Both engines use
validate(), so a course that isn't offered in the term never reaches the UI. Payload keys are camelCase (the API
shape), since payloads are stored as JSON and returned as-is."""
import re

from sqlalchemy.orm import Session

from models import Course, CourseSection, Term
from services.catalog import is_offered
from services.courses import when_text

CODE = re.compile(r"\b([A-Za-z]{2,4})\s*-?\s*(\d{3})\b")


def normalize_code(raw: str) -> str | None:
    match = CODE.search(raw or "")
    return f"{match.group(1).upper()} {match.group(2)}" if match else None


def find_codes(text: str) -> list[str]:
    """Course codes mentioned in text, normalized to "CS 608", in order, without duplicates."""
    codes = []
    for letters, digits in CODE.findall(text or ""):
        code = f"{letters.upper()} {digits}"
        if code not in codes:
            codes.append(code)
    return codes


def section_in(db: Session, course: Course, term: Term) -> CourseSection | None:
    return (db.query(CourseSection).filter(CourseSection.course_id == course.course_id, CourseSection.term_id == term.id)
            .order_by(CourseSection.id).first())


def validate(db: Session, rows: list[dict] | None, term_name: str | None) -> list[dict]:
    """Keeps rows whose course exists and is offered in the term; name and meta (the first section's meeting time,
    blank when no section is scheduled yet) come from the database."""
    if not rows or not term_name:
        return []
    term = db.query(Term).filter(Term.name == term_name).one_or_none()
    if term is None:
        return []
    valid, seen = [], set()
    for row in rows:
        code = normalize_code(row.get("code", ""))
        course = db.query(Course).filter(Course.course_code == code).one_or_none() if code else None
        if course is None or code in seen or not is_offered(db, course.course_id, term.id):
            continue
        section = section_in(db, course, term)
        seen.add(code)
        valid.append({"code": code, "name": course.course_name, "meta": when_text(section),
                      "fulfills": row.get("fulfills") or "Elective", "why": row.get("why"), "onPlan": False})
    return valid
