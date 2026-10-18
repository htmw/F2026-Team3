"""Degree audit (spec 12): which requirement group each course counts toward, the summary tiles and the
registration alert. Used by the degree plan screen, the dashboard alert (spec 10), the term plan (services/plan.py)
and, later, the AI advisor (13) and advisor checks (21, 22)."""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from core.time import short_date, today
from models import ApprovalRequest, Course, Enrollment, PlanItem, Program, ProgramRequirement, Student, Term
from services.catalog import current_term, term_sort_key, terms_by_name

PLAN_STATUS_LABELS = {
    "planned": "Planned",
    "recommended": "Recommended",
    "needs_approval": "Needs approval",
    "pending_approval": "Pending approval",
    "approved": "Approved",
    "changes_requested": "Changes requested",
}
STATE_LABELS = {"completed": "Completed", "in_progress": "In progress"}
ALERT_WITHIN_DAYS = 45
GRADUATION_SEASON = {"May": "Spring", "Aug": "Summer", "Dec": "Fall"}


@dataclass
class Taken:
    """A course on the student's record or plan: completed, in progress, or planned (a plan item)."""
    course: Course
    state: str  # "completed" | "in_progress" | "planned"
    term_name: str
    term_start: date
    enrollment: Enrollment | None = None
    item: PlanItem | None = None

    @property
    def credits(self) -> float:
        return float(self.course.credits)

    @property
    def label(self) -> str:
        return STATE_LABELS.get(self.state) or PLAN_STATUS_LABELS[self.item.status]


@dataclass
class Group:
    requirement: ProgramRequirement
    needed: int
    taken: list[Taken] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.requirement.group_name

    def count(self, state: str) -> int:
        return sum(1 for row in self.taken if row.state == state)

    @property
    def done(self) -> int:
        return min(self.count("completed"), self.needed)

    @property
    def all_done(self) -> bool:
        return self.done >= self.needed


STATE_ORDER = {"completed": 0, "in_progress": 1, "planned": 2}


def student_courses(db: Session, student: Student) -> list[Taken]:
    """Completed (grade not F), in-progress and planned courses, one row per course: completed first, then in
    progress, then planned, each in term order and then by code."""
    terms = terms_by_name(db)
    rows: list[Taken] = []
    enrollments = (db.query(Enrollment, Course).join(Course, Enrollment.course_id == Course.course_id)
                   .filter(Enrollment.student_id == student.student_id))
    for enrollment, course in enrollments:
        if enrollment.status == "completed" and (enrollment.grade or "").upper() != "F":
            state = "completed"
        elif enrollment.status == "in_progress":
            state = "in_progress"
        else:
            continue
        rows.append(Taken(course, state, enrollment.term, term_sort_key(enrollment.term, terms), enrollment=enrollment))
    items = (db.query(PlanItem, Course, Term).join(Course, PlanItem.course_id == Course.course_id)
             .join(Term, PlanItem.term_id == Term.id).filter(PlanItem.student_id == student.student_id))
    for item, course, term in items:
        rows.append(Taken(course, "planned", term.name, term.start_date, item=item))

    rows.sort(key=lambda row: (STATE_ORDER[row.state], row.term_start, row.course.course_code))
    seen, unique = set(), []
    for row in rows:
        if row.course.course_id not in seen:
            seen.add(row.course.course_id)
            unique.append(row)
    return unique


def requirements(db: Session, student: Student) -> list[ProgramRequirement]:
    return (db.query(ProgramRequirement).filter(ProgramRequirement.program_id == student.program_id)
            .order_by(ProgramRequirement.sort, ProgramRequirement.requirement_id).all())


def assign_groups(db: Session, student: Student, courses: list[Taken] | None = None) -> list[Group]:
    """Each course counts toward one group only: the first group (requirement order) that lists it and still has room."""
    courses = student_courses(db, student) if courses is None else courses
    groups = [Group(req, req.required_courses) for req in requirements(db, student)]
    for row in courses:
        for group in groups:
            if row.course.course_id in (group.requirement.eligible_courses_ids or []) and len(group.taken) < group.needed:
                group.taken.append(row)
                break
    return groups


def approval_course_ids(db: Session, student: Student) -> dict[int, str]:
    """Course id -> group title, for groups flagged requires_approval (the capstone)."""
    return {course_id: req.group_name for req in requirements(db, student) if req.requires_approval
            for course_id in (req.eligible_courses_ids or [])}


def has_form(db: Session, student: Student) -> bool:
    """True when a pre-approval form request (spec 22/23) is pending or approved."""
    return db.query(ApprovalRequest).filter(
        ApprovalRequest.student_id == student.student_id, ApprovalRequest.type == "form",
        ApprovalRequest.status.in_(("pending", "approved"))).first() is not None


def group_out(group: Group) -> dict:
    in_progress = group.count("in_progress")
    count = f"{group.done} of {group.needed} done" + (f" · {in_progress} in progress" if in_progress else "")
    return {
        "id": group.requirement.requirement_id,
        "title": group.title,
        "required": group.needed,
        "count": count,
        "all_done": group.all_done,
        "items": [{"code": row.course.course_code, "name": row.course.course_name, "status": row.label, "meta": row.term_name}
                  for row in group.taken],
    }


def group_progress(db: Session, student: Student) -> list[dict]:
    return [group_out(group) for group in assign_groups(db, student)]


def remaining_groups(db: Session, student: Student, through_term: Term | None = None,
                     groups: list[Group] | None = None) -> list[dict]:
    """Groups still missing courses after completed and in-progress work, plus planned courses up to and including
    through_term (none when it is None). Used by the summary tiles, the plan precheck and the AI advisor."""
    groups = assign_groups(db, student) if groups is None else groups
    out = []
    for group in groups:
        counted = sum(1 for row in group.taken if row.state != "planned"
                      or (through_term is not None and row.term_start <= through_term.start_date))
        missing = group.needed - min(counted, group.needed)
        if missing > 0:
            out.append({"id": group.requirement.requirement_id, "title": group.title, "missing": missing,
                        "needed": group.needed, "requires_approval": bool(group.requirement.requires_approval)})
    return out


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def remaining_text(remaining: list[dict]) -> str:
    """"Capstone and 1 elective": single-course groups by name first, then counts."""
    named, counted = [], []
    for group in remaining:
        if group["needed"] == 1:
            named.append(group["title"])
            continue
        noun = group["title"].lower()
        singular = noun[:-1] if noun.endswith("s") else noun
        counted.append(f"{group['missing']} {singular if group['missing'] == 1 else noun}")
    return _join(named + counted) or "Every requirement is covered"


def _pct(part: float, whole: float) -> int:
    return max(0, min(100, round(part / whole * 100))) if whole else 100


def graduation_term(db: Session, student: Student) -> Term | None:
    """The term that ends in the student's expected graduation ("May 2027" -> Spring 2027)."""
    parts = (student.expected_graduation or "").split()
    if len(parts) != 2 or parts[0][:3] not in GRADUATION_SEASON or not parts[1].isdigit():
        return None
    return db.query(Term).filter(Term.season == GRADUATION_SEASON[parts[0][:3]], Term.year == int(parts[1])).first()


def graduation_status(db: Session, student: Student, groups: list[Group], warn: bool) -> str:
    if not student.expected_graduation:
        return "Not set"
    for group in groups:
        if group.requirement.requires_approval and any(row.item and row.item.status != "approved" for row in group.taken):
            return f"Pending {group.title.lower()} approval"
    return "Needs planning" if warn else "On track"


def stats(db: Session, student: Student, courses: list[Taken], groups: list[Group]) -> list[dict]:
    program = db.get(Program, student.program_id)
    required = float(program.total_required_credits)
    earned = sum(row.credits for row in courses if row.state == "completed")
    in_progress = [row for row in courses if row.state == "in_progress"]
    doing = sum(row.credits for row in in_progress)
    planned = sum(row.credits for row in courses if row.state == "planned")
    left = max(0.0, required - earned - doing)
    total_courses = sum(group.needed for group in groups)
    completed_courses = sum(group.done for group in groups)
    warn = left > planned

    term = current_term(db)
    season = term.season if term else "term"
    doing_note = (f"{len(in_progress)} course{'' if len(in_progress) == 1 else 's'} this {season}"
                  if in_progress else "Nothing in progress")

    start = db.get(Term, student.start_term_id) if student.start_term_id else None
    finish = graduation_term(db, student)
    grad_pct = None
    if start and finish and finish.end_date > start.start_date:
        grad_pct = _pct((today() - start.start_date).days, (finish.end_date - start.start_date).days)

    return [
        {"label": "Credits earned", "value": f"{earned:g} / {required:g}", "pct": _pct(earned, required), "warn": False,
         "color": None, "note": f"{completed_courses} of {total_courses} courses complete"},
        {"label": "In progress", "value": f"{doing:g}", "pct": _pct(doing, required), "warn": False,
         "color": "violet", "note": doing_note},
        {"label": "Left after this term", "value": f"{left:g}", "pct": _pct(left, required), "warn": warn,
         "color": "amber", "note": remaining_text(remaining_groups(db, student, groups=groups))},
        {"label": "Expected graduation", "value": student.expected_graduation or "—", "pct": grad_pct, "warn": False,
         "color": None, "note": graduation_status(db, student, groups, warn)},
    ]


def upcoming_registration(db: Session) -> Term | None:
    """The next term whose registration opens today or later."""
    return (db.query(Term).filter(Term.registration_opens.isnot(None), Term.registration_opens >= today())
            .order_by(Term.registration_opens).first())


def alert(db: Session, student: Student, groups: list[Group] | None = None) -> str | None:
    """A required group that isn't ready for registration opening within 45 days, else None."""
    term = upcoming_registration(db)
    if term is None or (term.registration_opens - today()).days > ALERT_WITHIN_DAYS:
        return None
    groups = assign_groups(db, student) if groups is None else groups
    opens = short_date(term.registration_opens)
    form = None
    for group in groups:
        if group.all_done:
            continue
        if group.requirement.requires_approval:
            form = has_form(db, student) if form is None else form
            if not form:
                return f"{group.title} registration opens {opens}. Pre-approval form is still missing."
        if group.count("in_progress") == 0 and group.count("planned") == 0:
            return f"{group.title} registration opens {opens}. Nothing is planned for it yet."
    return None


def catalog_year(term: Term | None) -> str | None:
    """Academic year of the start term: Fall 2025 -> "2025–26", Spring 2026 -> "2025–26"."""
    if term is None:
        return None
    first = term.year if term.season == "Fall" else term.year - 1
    return f"{first}–{(first + 1) % 100:02d}"


def degree_audit(db: Session, student: Student) -> dict:
    program = db.get(Program, student.program_id)
    courses = student_courses(db, student)
    groups = assign_groups(db, student, courses)
    tiles = stats(db, student, courses, groups)
    year = catalog_year(db.get(Term, student.start_term_id) if student.start_term_id else None)
    subtitle = [program.program_name]
    if year:
        subtitle.append(f"catalog year {year}")
    if student.expected_graduation:
        subtitle.append(f"expected graduation {student.expected_graduation}")
    total = sum(group.needed for group in groups)
    return {
        "subtitle": " · ".join(subtitle),
        "requirements_subtitle": f"{program.program_name} · {total} courses · {float(program.total_required_credits):g} credits",
        "graduation": {"label": student.expected_graduation or "—", "status": tiles[3]["note"]},
        "stats": tiles,
        "groups": [group_out(group) for group in groups],
        "alert": alert(db, student, groups),
    }
