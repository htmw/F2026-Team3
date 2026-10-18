"""Deterministic answers from the student's records (always available; the Claude engine falls back to it).
Intents are matched by keywords, most specific first. Every answer lists the sources it read."""
import re
from datetime import time

from sqlalchemy.orm import Session

from core.time import DAY_NAMES as WEEKDAYS, short_date
from models import Course, CourseOffering, CourseSection, Program, Student, Term
from services.ai.context import advisor_of, catalog_label
from services.ai.plans import find_codes
from services.catalog import current_term, next_term, prerequisite_map
from services.courses import meeting_days, when_text
from services.progress import course_sets, credit_totals, requirement_status

EVENING = time(17, 0)
GRAD_MONTH = {"Spring": "May", "Summer": "August", "Fall": "December"}
NEXT_SEASON = {"Spring": ("Summer", 0), "Summer": ("Fall", 0), "Fall": ("Spring", 1)}
AUDIT = "Degree audit · updated today"
FALLBACK = ("I can answer questions about your degree progress, next term's plan, electives, prerequisites "
            "and your schedule.")
ACTIONS = [{"label": "Add to degree plan", "to": "/student/degree-plan"}, {"label": "Send to advisor", "to": "/student/messages"}]


def _reply(text: str, sources: list[str], **payload) -> dict:
    return {"kind": "answer", "text": text, "payload": {"sources": sources, **payload}}


def graduation_label(term_name: str) -> str:
    """"Spring 2027" -> "May 2027"."""
    season, year = term_name.split()
    return f"{GRAD_MONTH[season]} {year}"


def following_term(term_name: str) -> str:
    season, year = term_name.split()
    nxt, bump = NEXT_SEASON[season]
    return f"{nxt} {int(year) + bump}"


def _singular(label: str) -> str:
    return label[:-1] if label.endswith("s") else label


_prerequisites = prerequisite_map


def _offered(db: Session, term: Term) -> list[tuple[CourseSection, Course]]:
    """Sections in `term` of courses offered in it (course_offerings)."""
    return (db.query(CourseSection, Course).join(Course, CourseSection.course_id == Course.course_id)
            .join(CourseOffering, (CourseOffering.course_id == Course.course_id) & (CourseOffering.term_id == term.id))
            .filter(CourseSection.term_id == term.id).all())


def _eligible_sections(db: Session, student: Student, term: Term, group: dict, prefer_evening: bool, exclude: set[int]):
    """Sections in `term` that count for `group`, not taken yet, with prerequisites done (or in progress now)."""
    completed, in_progress = course_sets(db, student)
    prereqs = _prerequisites(db)
    have = completed | in_progress
    options = [
        (section, course) for section, course in _offered(db, term)
        if course.course_id in group["eligible_ids"] and course.course_id not in have | exclude
        and prereqs.get(course.course_id, set()) <= have
    ]
    def key(option):
        section, course = option
        late = section.start_time is not None and section.start_time >= EVENING
        return (0 if late or not prefer_evening else 1, section.start_time or time(0), course.course_code)
    return sorted(options, key=key)


def next_plan(db: Session, student: Student, ctx: dict) -> dict | None:
    """Courses offered next term that fill the remaining requirement slots, evening first if preferred."""
    term = next_term(db)
    if term is None:
        return None
    prefer_evening = ctx["prefs"].get("classTime") == "Evening"
    rows, picked, approvals, all_filled = [], set(), [], True
    for group in requirement_status(db, student):
        if group["remaining"] <= 0:
            continue
        options = _eligible_sections(db, student, term, group, prefer_evening, picked)[:group["remaining"]]
        if len(options) < group["remaining"]:
            all_filled = False
        for index, (section, course) in enumerate(options, start=1):
            picked.add(course.course_id)
            position = group["done"] + group["in_progress"] + index
            fulfills = f"{_singular(group['label'])} {position} of {group['needed']}" if group["needed"] > 1 else group["label"]
            days = meeting_days(section)
            rows.append({"code": course.course_code, "name": course.course_name, "meta": when_text(section),
                         "fulfills": fulfills, "why": None, "onPlan": False,
                         "_evening": section.start_time is not None and section.start_time >= EVENING,
                         "_order": (WEEKDAYS.index(days[0]) if days and days[0] in WEEKDAYS else 7, section.start_time or time(0))})
        if options and group["requires_approval"]:
            approvals.append(group["label"])
    rows.sort(key=lambda row: row["_order"])  # a schedule reads in weekday order
    earned, in_progress = credit_totals(db, student)
    required = float(db.get(Program, student.program_id).total_required_credits)
    return {
        "term": term,
        "rows": rows,
        "all_filled": all_filled and bool(rows),
        "evening": bool(rows) and all(row["_evening"] for row in rows),
        "approvals": approvals,
        "graduation": graduation_label(term.name) if all_filled and rows else None,
        "credits_left": max(0.0, required - earned - in_progress),
    }


def _approval_note(plan: dict) -> str | None:
    if not plan["approvals"]:
        return None
    term = plan["term"]
    note = f"Before you can register, your advisor must sign your {plan['approvals'][0].lower()} pre-approval form."
    if term.registration_opens:
        note += f" {term.season} registration opens {short_date(term.registration_opens)}."
    return note


def _plan_sources(db: Session, term: Term) -> list[str]:
    return [AUDIT, catalog_label(db), f"{term.name} schedule"]


def plan_answer(db: Session, student: Student, ctx: dict) -> dict:
    if not ctx["settings"]["features"]["planSuggestions"]:
        return _reply("Course plan suggestions are turned off for your school. Your advisor can help you plan.", [])
    if not (ctx["sources"]["audits"] and ctx["sources"]["catalog"]):
        return _reply("I can't suggest a plan because your degree audit or the course catalog is turned off as a data source.", [])
    plan = next_plan(db, student, ctx)
    if plan is None:
        return _reply("The next term's courses aren't published yet. Your advisor can help you plan ahead.", [AUDIT])
    term = plan["term"]
    sources = _plan_sources(db, term)
    if not plan["rows"]:
        return _reply(f"I couldn't find {term.name} courses that fit what you still need. Your advisor can help you plan.", sources)
    if plan["all_filled"]:
        text = f"Here's a plan that finishes your degree in {plan['graduation']}"
        text += " with every class in the evening:" if plan["evening"] else ":"
    else:
        text = f"Here are {term.name} courses that count toward what you still need:"
    rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in plan["rows"]]
    return _reply(text, sources, planTerm=term.name, plan=rows, follow=_approval_note(plan), actions=ACTIONS)


def on_track_answer(db: Session, student: Student, ctx: dict) -> dict:
    if not ctx["sources"]["audits"]:
        return _reply("I can't check your progress because your degree audit is turned off as a data source.", [])
    earned, in_progress = credit_totals(db, student)
    required = float(db.get(Program, student.program_id).total_required_credits)
    left = max(0.0, required - earned - in_progress)
    text = f"You have {earned:g} of {required:g} credits, with {in_progress:g} in progress. "
    text += f"After this term you'll need {left:g} more credits"
    text += f", which fits your expected graduation in {student.expected_graduation}." if student.expected_graduation else "."
    blockers = [group["label"].lower() for group in requirement_status(db, student)
                if group["requires_approval"] and group["done"] == 0 and group["in_progress"] == 0]
    if blockers:
        text += f" Your {blockers[0]} still needs your advisor's pre-approval before you can register."
    return _reply(text, [AUDIT])


def what_if_answer(db: Session, student: Student, ctx: dict, text: str) -> dict:
    if not ctx["sources"]["audits"]:
        return _reply("I can't check your progress because your degree audit is turned off as a data source.", [])
    plan = next_plan(db, student, ctx)
    if plan is None or not plan["rows"] or not plan["graduation"]:
        return _reply("Moving a course to a later term would push your graduation back by one term. Your advisor can "
                      "check the exact options with you.", [AUDIT])
    term, last = plan["term"], plan["rows"][-1]
    later = following_term(term.name)
    kind = last["fulfills"].split(" ")[0].lower()
    lead = "If you had to retake a course" if "fail" in text else f"Taking only one course in {term.season}"
    answer = (f"{lead} would move your last {kind} to {later}, so you would graduate in "
              f"{GRAD_MONTH[later.split()[0]]} instead of {GRAD_MONTH[term.season]}.")
    if later.startswith("Summer"):
        answer += " Summer electives run less often, so check what's offered before choosing this path."
    return _reply(answer, [AUDIT, catalog_label(db)])


def electives_answer(db: Session, student: Student, ctx: dict) -> dict:
    if not ctx["sources"]["catalog"]:
        return _reply("I can't look up electives because the course catalog is turned off as a data source.", [])
    term = next_term(db)
    group = next((g for g in requirement_status(db, student) if g["label"].lower().startswith("elective")), None)
    if term is None or group is None:
        return _reply("I couldn't find upcoming electives for your program.", [catalog_label(db)])
    prefer_evening = ctx["prefs"].get("classTime") == "Evening"
    options = _eligible_sections(db, student, term, group, prefer_evening, set())
    sources = [AUDIT, catalog_label(db), f"{term.name} schedule"]
    if not options:
        return _reply(f"No electives you still need are offered in {term.name}.", sources)
    rows = [{"code": course.course_code, "name": course.course_name, "meta": when_text(section), "fulfills": "Elective",
             "why": f"Offered {term.name} · {when_text(section)}", "onPlan": False} for section, course in options]
    return _reply(f"These electives are offered in {term.name} and count toward your degree:", sources,
                  planTerm=term.name, plan=rows, actions=ACTIONS)


def _course(db: Session, code: str) -> Course | None:
    return db.query(Course).filter(Course.course_code == code).one_or_none()


def prerequisite_answer(db: Session, student: Student, ctx: dict, codes: list[str]) -> dict:
    course = _course(db, codes[0])
    sources = [catalog_label(db)]
    if course is None:
        return _reply(f"I couldn't find {codes[0]} in the course catalog.", sources)
    needed = _prerequisites(db).get(course.course_id, set())
    if not needed:
        return _reply(f"{course.course_code} {course.course_name} has no prerequisites.", sources)
    completed, in_progress = course_sets(db, student)
    names = {c.course_id: c.course_code for c in db.query(Course).filter(Course.course_id.in_(needed))}
    missing = sorted(names[i] for i in needed - completed - in_progress)
    sources.append(AUDIT)
    if missing:
        return _reply(f"You still need {' and '.join(missing)} before you can take {course.course_code}.", sources)
    pending = sorted(names[i] for i in needed & in_progress)
    text = f"Yes. You meet the prerequisites for {course.course_code} {course.course_name}"
    text += f" once you finish {' and '.join(pending)} this term." if pending else "."
    return _reply(text, sources)


def _section_for(db: Session, course: Course, terms: list[Term]):
    for term in terms:
        section = (db.query(CourseSection).filter(CourseSection.course_id == course.course_id, CourseSection.term_id == term.id)
                   .first())
        if section is not None:
            return section, term
    return None, None


def conflict_answer(db: Session, student: Student, ctx: dict, codes: list[str]) -> dict:
    terms = [term for term in (current_term(db), next_term(db)) if term is not None]
    first, second = _course(db, codes[0]), _course(db, codes[1])
    if first is None or second is None:
        missing = codes[0] if first is None else codes[1]
        return _reply(f"I couldn't find {missing} in the course catalog.", [catalog_label(db)])
    a, term_a = _section_for(db, first, terms)
    b, term_b = _section_for(db, second, terms)
    if a is None or b is None or term_a.id != term_b.id:
        return _reply(f"{first.course_code} and {second.course_code} aren't offered in the same term, so they can't clash.",
                      [catalog_label(db)])
    sources = [f"{term_a.name} schedule"]
    shared = set(meeting_days(a)) & set(meeting_days(b))
    overlap = shared and a.start_time and b.start_time and a.end_time and b.end_time \
        and a.start_time < b.end_time and b.start_time < a.end_time
    if overlap:
        return _reply(f"No. {first.course_code} ({when_text(a)}) and {second.course_code} ({when_text(b)}) overlap, so you "
                      "can't take both sections.", sources)
    return _reply(f"Yes. {first.course_code} meets {when_text(a)} and {second.course_code} meets {when_text(b)}, so they "
                  "don't overlap.", sources)


def email_answer(db: Session, student: Student, ctx: dict) -> dict:
    advisor = advisor_of(db, student)
    earned, in_progress = credit_totals(db, student)
    term = next_term(db)
    first = ctx["user"].first_name or student.name.split()[0]
    body = (f"Hi {advisor['name'] if advisor else 'there'},\n\n"
            f"I have {earned:g} credits completed and {in_progress:g} in progress. Could we meet to review my "
            f"{term.name if term else 'next term'} plan and anything I need approved before registration?\n\n"
            f"Thanks,\n{first}")
    return _reply(f"Here's a draft you can send:\n\n{body}", [AUDIT],
                  actions=[{"label": "Send to advisor", "to": "/student/messages"}])


def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def answer(db: Session, student: Student, text: str, ctx: dict) -> dict:
    lowered = text.lower()
    codes = find_codes(text)
    if _has(lowered, "email"):
        return email_answer(db, student, ctx)
    if _has(lowered, "fail", "drop", "only one", "retake"):
        return what_if_answer(db, student, ctx, lowered)
    if len(codes) >= 2 and _has(lowered, "together", "conflict", "clash", "same time"):
        return conflict_answer(db, student, ctx, codes)
    if codes and _has(lowered, "prereq", "prerequisite", "prerequisites", "can i take", "eligible"):
        return prerequisite_answer(db, student, ctx, codes)
    if _has(lowered, "elective", "electives"):
        return electives_answer(db, student, ctx)
    if _has(lowered, "plan", "spring", "summer", "fall", "next semester", "next term", "schedule"):
        return plan_answer(db, student, ctx)
    if _has(lowered, "on track", "graduate", "graduation", "progress", "credits"):
        return on_track_answer(db, student, ctx)
    return _reply(FALLBACK, [])
