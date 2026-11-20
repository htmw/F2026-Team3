"""The AI advisor's instructions and tools, shared by the Claude and Gemini engines (spec 13). The tools are closures
over the signed-in student, so the model never chooses whose records it reads. A Toolbox also records which tools
the model called (the reply's sources) and the plan it proposed."""
import json
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.time import today
from models import Course, CourseOffering, CourseSection, Enrollment, Program, Student, Term
from services.academics import current_grade
from services.ai import plans
from services.ai.context import catalog_label
from services.ai.rules_engine import ACTIONS, AUDIT, _prerequisites
from services.catalog import term_sort_key, terms_by_name
from services.courses import current_enrollments, when_text
from services.progress import course_sets, credit_totals, requirement_status

# Frozen so the prefix caches: no dates, names or other per-request facts in here.
SYSTEM_PROMPT = """You are Acadmate, the academic advising assistant for a university graduate program.
You help one student with their degree progress, next term's plan, electives, prerequisites and schedule.

Answer only from what your tools return. Never invent courses, course codes, grades, dates, rooms or policies.
If the tools don't have the answer, say so and suggest the student ask their advisor.
When you suggest courses for a term, call propose_plan with the course codes; the app shows that plan to the student.
Plans are suggestions until the student's advisor approves them, so never say a plan is confirmed or registered.
Do not discuss visa and immigration, mental health, financial aid or grade appeals; point the student to their
advisor or the right campus office instead.
Write plain text without markdown headings or tables. Address the student directly."""

STYLE = {
    "Concise": "Keep answers to two or three sentences.",
    "Balanced": "Keep answers short: a few sentences, with a brief reason for each suggestion.",
    "Detailed": "Explain your reasoning and mention the trade-offs the student should weigh.",
}


def instructions(ctx: dict) -> list[str]:
    """The system prompt, then the reply-style line for the configured style."""
    return [SYSTEM_PROMPT, STYLE.get(ctx["settings"]["style"], STYLE["Balanced"])]


def question(ctx: dict, student: Student, text: str) -> str:
    """The student's question with today's date and their first name, which the system prompt leaves out."""
    first_name = ctx["user"].first_name or student.name.split()[0]
    return f"{text}\n\n(Today is {today().isoformat()}. Student first name: {first_name}.)"


def _term(db: Session, name: str | None) -> Term | None:
    return db.query(Term).filter(Term.name == name).one_or_none() if name else None


def _dump(value) -> str:
    return json.dumps(value, default=str)


@dataclass
class Toolbox:
    functions: list[Callable[..., str]] = field(default_factory=list)
    used: list[str] = field(default_factory=list)  # source labels of the tools the model called, in call order
    proposal: dict = field(default_factory=dict)  # filled by propose_plan

    def payload(self) -> dict:
        """The reply's sources, plus the proposed plan when the model called propose_plan."""
        payload = {"sources": self.used}
        if self.proposal.get("rows"):
            payload.update(planTerm=self.proposal["term"], plan=self.proposal["rows"], follow=self.proposal["notes"],
                           actions=ACTIONS)
        return payload


def build(db: Session, student: Student, ctx: dict) -> Toolbox:
    """The tools this student's question may use: grades and schedule only when those sources are on."""
    box = Toolbox()
    sources_on = ctx["sources"]

    def note(label: str) -> None:
        if label not in box.used:
            box.used.append(label)

    def get_degree_audit() -> str:
        """Get the student's degree progress: credits earned and in progress, expected graduation, and for each
        requirement group how many courses are done, in progress and still remaining."""
        note(AUDIT)
        earned, in_progress = credit_totals(db, student)
        program = db.get(Program, student.program_id)
        groups = [{key: group[key] for key in ("label", "needed", "done", "in_progress", "remaining", "requires_approval")}
                  for group in requirement_status(db, student)]
        return _dump({"program": program.program_name, "requiredCredits": float(program.total_required_credits),
                      "creditsEarned": earned, "creditsInProgress": in_progress,
                      "expectedGraduation": student.expected_graduation, "requirementGroups": groups})

    def search_catalog(query: str, term: str | None = None) -> str:
        """Search the course catalog by course code or words in the course name.

        Args:
            query: A course code such as "CS 680" or words from a course name such as "machine learning".
            term: Optional term name such as "Spring 2027"; only courses offered that term are returned.
        """
        note(catalog_label(db))
        code = plans.normalize_code(query)
        rows = db.query(Course).filter(or_(Course.course_code == code, Course.course_name.ilike(f"%{query.strip()}%"))).all()
        offered = {}
        for offering, term_row in db.query(CourseOffering, Term).join(Term, CourseOffering.term_id == Term.id):
            offered.setdefault(offering.course_id, []).append(term_row.name)
        prereqs = _prerequisites(db)
        codes = {course.course_id: course.course_code for course in db.query(Course)}
        result = [{"code": course.course_code, "name": course.course_name, "credits": float(course.credits),
                   "offeredIn": sorted(set(offered.get(course.course_id, []))),
                   "prerequisites": sorted(codes[i] for i in prereqs.get(course.course_id, set()))}
                  for course in rows if term is None or term in offered.get(course.course_id, [])]
        return _dump(result[:20])

    def get_course_sections(code: str, term: str) -> str:
        """Get the sections (days, times, room, instructor) of one course in one term.

        Args:
            code: Course code, for example "CS 691".
            term: Term name, for example "Spring 2027".
        """
        term_row = _term(db, term)
        note(f"{term} schedule" if term_row else catalog_label(db))
        course = db.query(Course).filter(Course.course_code == plans.normalize_code(code)).one_or_none()
        if course is None or term_row is None:
            return _dump({"error": "Unknown course or term."})
        sections = db.query(CourseSection).filter(CourseSection.course_id == course.course_id,
                                                  CourseSection.term_id == term_row.id)
        return _dump([{"when": when_text(s), "room": s.room, "instructor": s.instructor_name} for s in sections])

    def check_prerequisites(code: str) -> str:
        """Check whether the student has completed (or is taking now) the prerequisites of a course.

        Args:
            code: Course code, for example "CS 680".
        """
        note(catalog_label(db))
        course = db.query(Course).filter(Course.course_code == plans.normalize_code(code)).one_or_none()
        if course is None:
            return _dump({"error": "Unknown course."})
        completed, in_progress = course_sets(db, student)
        needed = _prerequisites(db).get(course.course_id, set())
        codes = {c.course_id: c.course_code for c in db.query(Course).filter(Course.course_id.in_(needed))} if needed else {}
        return _dump({"course": course.course_code, "prerequisites": sorted(codes.values()),
                      "completed": sorted(codes[i] for i in needed & completed),
                      "inProgress": sorted(codes[i] for i in needed & in_progress),
                      "missing": sorted(codes[i] for i in needed - completed - in_progress)})

    def get_transcript() -> str:
        """Get the student's completed courses with final grades, and current courses with grades so far."""
        note("Grades")
        terms = terms_by_name(db)
        rows = (db.query(Enrollment, Course).join(Course, Enrollment.course_id == Course.course_id)
                .filter(Enrollment.student_id == student.student_id, Enrollment.status == "completed").all())
        rows.sort(key=lambda row: term_sort_key(row[0].term, terms))
        completed = [{"code": c.course_code, "name": c.course_name, "term": e.term, "grade": e.grade} for e, c in rows]
        current = [{"code": entry.course.course_code, "name": entry.course.course_name,
                    "gradeSoFar": current_grade(entry.items)} for entry in current_enrollments(db, student)]
        return _dump({"completed": completed, "current": current})

    def get_schedule(term: str) -> str:
        """Get the student's own class meetings in a term (the current term).

        Args:
            term: Term name, for example "Fall 2026".
        """
        note(f"{term} schedule")
        return _dump([{"code": entry.course.course_code, "when": when_text(entry.section),
                       "room": entry.section.room if entry.section else None}
                      for entry in current_enrollments(db, student) if entry.enrollment.term == term])

    def propose_plan(term: str, course_codes: list[str], notes: str = "") -> str:
        """Show the student a proposed set of courses for a term. Only courses offered that term are kept.

        Args:
            term: Term name, for example "Spring 2027".
            course_codes: Course codes to propose, for example ["CS 691", "CS 680"].
            notes: One or two sentences the student should know before registering (approvals, deadlines).
        """
        groups = requirement_status(db, student)
        rows = []
        for raw in course_codes:
            code = plans.normalize_code(raw)
            course = db.query(Course).filter(Course.course_code == code).one_or_none() if code else None
            group = next((g for g in groups if course and course.course_id in g["eligible_ids"]), None)
            rows.append({"code": code or raw, "fulfills": group["label"] if group else "Elective"})
        valid = plans.validate(db, rows, term)
        note(f"{term} schedule")
        box.proposal.update({"term": term, "rows": valid, "notes": notes.strip() or None})
        if not valid:
            return _dump({"error": f"None of those courses are offered in {term}."})
        return _dump({"shown": valid})

    box.functions = [get_degree_audit, search_catalog, get_course_sections, check_prerequisites]
    if sources_on["grades"]:
        box.functions.append(get_transcript)
    if sources_on["schedules"]:
        box.functions.append(get_schedule)
    box.functions.append(propose_plan)
    return box
