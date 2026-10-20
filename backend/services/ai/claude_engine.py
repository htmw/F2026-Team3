"""Claude engine for the AI advisor (spec 13). Claude answers only from tool results: the tools are closures over
the signed-in student, so the model never chooses whose records it reads. Returns None on a refusal or an empty
answer; API errors propagate and services.ai.ask() falls back to the rules engine."""
import json
import logging

import anthropic
from anthropic import beta_tool
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

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 8

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

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    """Created once; reads ANTHROPIC_API_KEY. One retry, 60 s timeout per attempt."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=60, max_retries=1)
    return _client


def _term(db: Session, name: str | None) -> Term | None:
    return db.query(Term).filter(Term.name == name).one_or_none() if name else None


def _dump(value) -> str:
    return json.dumps(value, default=str)


def answer(db: Session, student: Student, text: str, ctx: dict, history: list) -> dict | None:
    sources_on = ctx["sources"]
    used: list[str] = []  # source labels of the tools Claude called, in call order
    proposal: dict = {}

    def note(label: str) -> None:
        if label not in used:
            used.append(label)

    @beta_tool
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

    @beta_tool
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

    @beta_tool
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

    @beta_tool
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

    @beta_tool
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

    @beta_tool
    def get_schedule(term: str) -> str:
        """Get the student's own class meetings in a term (the current term).

        Args:
            term: Term name, for example "Fall 2026".
        """
        note(f"{term} schedule")
        return _dump([{"code": entry.course.course_code, "when": when_text(entry.section),
                       "room": entry.section.room if entry.section else None}
                      for entry in current_enrollments(db, student) if entry.enrollment.term == term])

    @beta_tool
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
        proposal.update({"term": term, "rows": valid, "notes": notes.strip() or None})
        if not valid:
            return _dump({"error": f"None of those courses are offered in {term}."})
        return _dump({"shown": valid})

    tools = [get_degree_audit, search_catalog, get_course_sections, check_prerequisites]
    if sources_on["grades"]:
        tools.append(get_transcript)
    if sources_on["schedules"]:
        tools.append(get_schedule)
    tools.append(propose_plan)

    messages = [{"role": message.role, "content": message.text} for message in history]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    first_name = ctx["user"].first_name or student.name.split()[0]
    messages.append({"role": "user", "content": f"{text}\n\n(Today is {today().isoformat()}. Student first name: {first_name}.)"})

    runner = client().beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        cache_control={"type": "ephemeral"},
        system=[{"type": "text", "text": SYSTEM_PROMPT},
                {"type": "text", "text": STYLE.get(ctx["settings"]["style"], STYLE["Balanced"])}],
        tools=tools,
        messages=messages,
        max_iterations=MAX_TOOL_ROUNDS,
    )
    final, input_tokens, output_tokens, cache_read = None, 0, 0, 0
    for message in runner:
        final = message
        usage = message.usage
        input_tokens += (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0) + (usage.cache_read_input_tokens or 0)
        output_tokens += usage.output_tokens or 0
        cache_read += usage.cache_read_input_tokens or 0
    log.info("Claude answer: %s input tokens (%s from cache), %s output tokens", input_tokens, cache_read, output_tokens)

    if final is None or final.stop_reason == "refusal":
        return None
    reply_text = "".join(block.text for block in final.content if block.type == "text").strip()
    if not reply_text:
        return None

    payload = {"sources": used}
    if proposal.get("rows"):
        payload.update(planTerm=proposal["term"], plan=proposal["rows"], follow=proposal["notes"], actions=ACTIONS)
    return {"kind": "answer", "text": reply_text, "payload": payload,
            "input_tokens": input_tokens, "output_tokens": output_tokens}
