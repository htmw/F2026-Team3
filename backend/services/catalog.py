"""Published catalog reads shared by the student features (specs 10–18): terms, offerings, prerequisites and the
catalog year. The admin editor (spec 33, drafts and publish) lives in services/admin_catalog.py."""
from datetime import date

from sqlalchemy.orm import Session

from core.time import today
from models import CourseOffering, CoursePrerequisite, Program, Term
from services import settings


def current_term(db: Session) -> Term | None:
    """The term an admin picked in Settings (spec 37), else the term that contains today."""
    chosen = settings.get(db, "institution")["currentTermId"]
    term = db.get(Term, chosen) if chosen is not None else None
    return term or term_by_date(db)


def term_by_date(db: Session) -> Term | None:
    """The term that contains today, else the latest term that has started."""
    day = today()
    term = db.query(Term).filter(Term.start_date <= day, Term.end_date >= day).first()
    if term is None:
        term = db.query(Term).filter(Term.start_date <= day).order_by(Term.start_date.desc()).first()
    return term


def next_term(db: Session) -> Term | None:
    current = current_term(db)
    query = db.query(Term)
    if current is not None:
        query = query.filter(Term.start_date > current.end_date)
    else:
        query = query.filter(Term.start_date > today())
    return query.order_by(Term.start_date).first()


def term_week(term: Term) -> int:
    """Teaching week of today within `term`, counted from its start date (week 1 at the latest)."""
    return max(1, (today() - term.start_date).days // 7 + 1)


def terms_by_name(db: Session) -> dict[str, Term]:
    """Maps Enrollment.term strings to their Term rows (for chronological ordering)."""
    return {term.name: term for term in db.query(Term).all()}


SEASON_MONTH = {"Spring": 1, "Summer": 5, "Fall": 8}


def term_sort_key(name: str, terms: dict[str, Term]) -> date:
    """Chronological key for an Enrollment.term string: the term's start date, else parsed from "Season YYYY"."""
    term = terms.get(name)
    if term is not None:
        return term.start_date
    parts = name.split()
    if len(parts) == 2 and parts[0] in SEASON_MONTH and parts[1].isdigit():
        return date(int(parts[1]), SEASON_MONTH[parts[0]], 1)
    return date.max


def offered_course_ids(db: Session, term_id: int) -> set[int]:
    """Courses offered in a term (course_offerings). Acadmate only suggests offered courses."""
    return {course_id for (course_id,) in db.query(CourseOffering.course_id).filter(CourseOffering.term_id == term_id)}


def is_offered(db: Session, course_id: int, term_id: int) -> bool:
    return db.get(CourseOffering, (course_id, term_id)) is not None


def prerequisite_map(db: Session) -> dict[int, set[int]]:
    """course_id -> the course ids it requires."""
    required: dict[int, set[int]] = {}
    for row in db.query(CoursePrerequisite):
        required.setdefault(row.course_id, set()).add(row.prerequisite_id)
    return required


def prerequisites_of(db: Session, course_id: int) -> set[int]:
    return {prereq for (prereq,) in db.query(CoursePrerequisite.prerequisite_id).filter(CoursePrerequisite.course_id == course_id)}


def catalog_year(db: Session) -> str:
    """The published catalog year ("2026–27"), from the first program."""
    program = db.query(Program).order_by(Program.program_id).first()
    if program is not None and program.catalog_year:
        return program.catalog_year
    term = current_term(db)
    start = (term.year if term.season == "Fall" else term.year - 1) if term else today().year
    return f"{start}–{(start + 1) % 100:02d}"
