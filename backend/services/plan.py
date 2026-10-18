"""Term plan (spec 12): the semester roadmap, adding and removing planned courses, and sending a term's plan to the
advisor (a pre-check plus an approval_requests row that spec 23's advisor queue works through). Also the
Planned tab rows of My courses (spec 11)."""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import bad_request, conflict, not_found
from core.time import short_date, today
from models import Advisor, ApprovalRequest, Course, PlanItem, Student, Term, User
from services import audit, mailer, messages
from services.approvals import advisor_for, precheck_summary
from services.catalog import current_term, next_term, offered_course_ids, prerequisites_of
from services.degree_audit import (PLAN_STATUS_LABELS, Taken, approval_course_ids, assign_groups, has_form,
                                   remaining_groups, student_courses)

MAX_TERM_CREDITS = 12
FORM_LEAD_DAYS = 14  # the pre-approval form is due two weeks before registration opens (Nov 3 -> Oct 20)
UPCOMING_TERMS = 2  # future terms shown on the roadmap even when nothing is planned in them
SENDABLE = ("planned", "recommended", "needs_approval", "changes_requested")
ROW_STATUS = {"completed": "completed", "in_progress": "current", "planned": "planned"}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _credits(rows: list[Taken]) -> str:
    total = sum(row.credits for row in rows)
    return f"{total:g} credit{'' if total == 1 else 's'}"


def form_due(term: Term) -> str | None:
    return short_date(term.registration_opens - timedelta(days=FORM_LEAD_DAYS)) if term.registration_opens else None


def _course_row(row: Taken) -> dict:
    return {
        "enrollment_id": row.item.id if row.item else row.enrollment.enrollment_id,
        "code": row.course.course_code,
        "name": row.course.course_name,
        "status": ROW_STATUS[row.state],
        "plan_status": PLAN_STATUS_LABELS[row.item.status] if row.item else None,
    }


def _notice(db: Session, student: Student, term: Term, rows: list[Taken]) -> str | None:
    """"Spring 2027 is a draft until your advisor approves it. Capstone pre-approval is due Oct 20; registration opens Nov 3."."""
    if not any(row.item and row.item.status != "approved" for row in rows):
        return None
    text = f"{term.name} is a draft until your advisor approves it."
    opens = term.registration_opens if term.registration_opens and term.registration_opens >= today() else None
    approvals = approval_course_ids(db, student)
    group = next((approvals[row.course.course_id] for row in rows if row.course.course_id in approvals), None)
    if group and opens and not has_form(db, student):
        return f"{text} {group} pre-approval is due {form_due(term)}; registration opens {short_date(opens)}."
    if opens:
        return f"{text} Registration opens {short_date(opens)}."
    return text


def get_plan(db: Session, student: Student) -> dict:
    day = today()
    current = current_term(db)
    courses = student_courses(db, student)
    by_term = defaultdict(list)
    for row in courses:
        by_term[row.term_name].append(row)

    terms = db.query(Term).order_by(Term.start_date).all()
    future = [term for term in terms if term.start_date > day]
    upcoming = {term.id for term in future[:UPCOMING_TERMS]}
    out, notice = [], None
    for term in terms:
        rows = sorted(by_term.get(term.name, []), key=lambda row: row.course.course_code)
        if current is not None and term.id == current.id:
            tag = "Current"
        elif term.end_date < day and rows:
            tag = "Done"
        elif term.start_date > day and (rows or term.id in upcoming):
            tag = "Planned"
        else:
            continue
        out.append({"name": term.name, "tag": tag, "credits": _credits(rows), "courses": [_course_row(row) for row in rows]})
        if tag == "Planned" and notice is None:
            notice = _notice(db, student, term, rows)

    groups = assign_groups(db, student, courses)
    have = {row.course.course_id for row in courses}
    upcoming_term = next_term(db)
    offered = set()
    if upcoming_term is not None:
        offered = offered_course_ids(db, upcoming_term.id)
    available = []
    for course in db.query(Course).order_by(Course.course_code):
        if course.course_id in have:
            continue
        index, group = next(((i, g) for i, g in enumerate(groups)
                             if course.course_id in (g.requirement.eligible_courses_ids or []) and len(g.taken) < g.needed),
                            (len(groups), None))
        available.append((index, {"code": course.course_code, "name": course.course_name,
                                  "type": group.title if group else "Elective", "offered": course.course_id in offered}))
    available.sort(key=lambda pair: (pair[0], pair[1]["code"]))

    return {
        "terms": out,
        "available": [row for _, row in available],
        "future_terms": [{"id": term.id, "name": term.name} for term in future],
        "notice": notice,
    }


def _prerequisites(db: Session, course_id: int) -> list[Course]:
    ids = prerequisites_of(db, course_id)
    return db.query(Course).filter(Course.course_id.in_(ids)).order_by(Course.course_code).all() if ids else []


def _missing_prerequisites(db: Session, course: Course, term: Term, courses: list[Taken]) -> list[Course]:
    """Prerequisites that aren't completed, in progress, or planned in a term before `term`."""
    met = {row.course.course_id for row in courses
           if row.state != "planned" or row.term_start < term.start_date}
    return [prereq for prereq in _prerequisites(db, course.course_id) if prereq.course_id not in met]


def add_item(db: Session, student: Student, actor: User, course_code: str, term_id: int, note: str | None) -> dict:
    course = db.query(Course).filter(func.lower(Course.course_code) == course_code.strip().lower()).one_or_none()
    if course is None:
        raise not_found("Course")
    term = db.get(Term, term_id)
    if term is None:
        raise not_found("Term")
    if term.start_date <= today():
        raise bad_request(f"{term.name} has already started.")
    courses = student_courses(db, student)
    if any(row.course.course_id == course.course_id for row in courses):
        raise conflict(f"{course.course_code} is already on your record or plan.")
    missing = _missing_prerequisites(db, course, term, courses)
    if missing:
        raise bad_request(f"Take {missing[0].course_code} before {course.course_code}.")

    status = "needs_approval" if course.course_id in approval_course_ids(db, student) else "planned"
    item = PlanItem(student_id=student.student_id, course_id=course.course_id, term_id=term.id, status=status,
                    note=(note or "").strip() or None)
    db.add(item)
    db.flush()
    audit.record(db, actor, "plan.add", f"Added {course.course_code} to the {term.name} plan", target=("plan_item", item.id),
                 changes={"course": course.course_code, "term": term.name, "status": status})
    db.commit()
    return {"enrollment_id": item.id, "code": course.course_code, "name": course.course_name, "term": term.name,
            "plan_status": PLAN_STATUS_LABELS[status]}


def remove_item(db: Session, student: Student, actor: User, item_id: int) -> None:
    item = db.get(PlanItem, item_id)
    if item is None or item.student_id != student.student_id:
        raise not_found("Plan item")
    if item.status == "pending_approval":
        raise conflict("This course is waiting for your advisor. Ask them to send it back first.")
    course = db.get(Course, item.course_id)
    term = db.get(Term, item.term_id)
    audit.record(db, actor, "plan.remove", f"Removed {course.course_code} from the {term.name} plan",
                 target=("plan_item", item.id), changes={"course": course.course_code, "term": term.name})
    db.delete(item)
    db.commit()


def precheck(db: Session, student: Student, term: Term, courses: list[Taken] | None = None) -> dict:
    """Checks shown to the student after sending and to the advisor with the request. Only prerequisites block;
    the rest are warnings the advisor can still approve over (spec 22)."""
    courses = student_courses(db, student) if courses is None else courses
    rows = sorted((row for row in courses if row.state == "planned" and row.item.term_id == term.id),
                  key=lambda row: row.course.course_code)
    credits = sum(row.credits for row in rows)
    checks = []

    remaining = remaining_groups(db, student, through_term=term, groups=assign_groups(db, student, courses))
    if remaining:
        missing = sum(group["missing"] for group in remaining)
        checks.append({"ok": False, "blocking": False, "text": f"Leaves {_plural(missing, 'requirement')} for a later term"})
    else:
        checks.append({"ok": True, "blocking": False, "text": f"Covers all remaining requirements ({credits:g} credits)"})

    if credits > MAX_TERM_CREDITS:
        checks.append({"ok": False, "blocking": False,
                       "text": f"Over the {MAX_TERM_CREDITS}-credit limit — needs an overload approval"})

    failed = [(prereq, row.course) for row in rows for prereq in _missing_prerequisites(db, row.course, term, courses)]
    if failed:
        checks.extend({"ok": False, "blocking": True, "text": f"Take {prereq.course_code} before {course.course_code}"}
                      for prereq, course in failed)
    else:
        scope = (f"for {rows[0].course.course_code}" if len(rows) == 1 else
                 "for both courses" if len(rows) == 2 else f"for all {len(rows)} courses")
        checks.append({"ok": True, "blocking": False, "text": f"Prerequisites met {scope}"})

    approvals = approval_course_ids(db, student)
    group = next((approvals[row.course.course_id] for row in rows if row.course.course_id in approvals), None)
    if group:
        if has_form(db, student):
            checks.append({"ok": True, "blocking": False, "text": f"{group} pre-approval form submitted"})
        else:
            due = form_due(term)
            checks.append({"ok": False, "blocking": False,
                           "text": f"{group} pre-approval form not submitted yet" + (f" (due {due})" if due else "")})

    offered = offered_course_ids(db, term.id)
    checks.extend({"ok": False, "blocking": False, "text": f"{row.course.course_code} isn't offered in {term.name}"}
                  for row in rows if row.course.course_id not in offered)

    return precheck_summary(checks)


def submit_term(db: Session, student: Student, actor: User, term_id: int) -> dict:
    term = db.get(Term, term_id)
    if term is None:
        raise not_found("Term")
    pending = db.query(ApprovalRequest).filter(
        ApprovalRequest.student_id == student.student_id, ApprovalRequest.type == "plan",
        ApprovalRequest.term_id == term.id, ApprovalRequest.status == "pending").first()
    if pending is not None:
        raise conflict(f"Your {term.name} plan is already waiting for your advisor.")
    items = (db.query(PlanItem, Course).join(Course, PlanItem.course_id == Course.course_id)
             .filter(PlanItem.student_id == student.student_id, PlanItem.term_id == term.id, PlanItem.status.in_(SENDABLE))
             .order_by(Course.course_code).all())
    if not items:
        raise bad_request(f"{term.name} has no planned courses to send.")

    result = precheck(db, student, term)
    for item, _ in items:
        item.status = "pending_approval"
    advisor_id = advisor_for(db, student)
    title = f"{term.name} plan · {' + '.join(course.course_name for _, course in items)}"
    request = ApprovalRequest(student_id=student.student_id, advisor_id=advisor_id, type="plan",
                              title=title[:200], term_id=term.id, payload={"planItemIds": [item.id for item, _ in items]},
                              precheck=result)
    db.add(request)
    db.flush()
    audit.record(db, actor, "plan.submit", f"Sent the {term.name} plan to the advisor", target=("approval_request", request.id),
                 changes={"planItemIds": [item.id for item, _ in items], "ok": result["ok"]})
    messages.notify(db, student.user_id, f"Your {term.name} plan is waiting for advisor approval.")
    db.commit()

    # Spec 25 replaces this with a "New plan to review" system message in the advisor's inbox.
    advisor = db.get(Advisor, advisor_id) if advisor_id else None
    advisor_user = db.get(User, advisor.user_id) if advisor else None
    if advisor_user is not None:
        mailer.send(advisor_user.email, "New plan to review", f"{student.name} sent their {term.name} plan: {title}.")
    return {"precheck": result, "request_id": request.id}


def planned_courses(db: Session, student: Student) -> list[dict]:
    """Planned rows for the My courses Planned tab (spec 11)."""
    courses = student_courses(db, student)
    fulfills = {row.course.course_id: group.title for group in assign_groups(db, student, courses) for row in group.taken}
    return [
        {"enrollment_id": row.item.id, "course_id": row.course.course_id, "code": row.course.course_code,
         "name": row.course.course_name, "term": row.term_name, "credits": row.credits, "status": row.label,
         "fulfills": fulfills.get(row.course.course_id), "why": row.item.note}
        for row in courses if row.state == "planned"
    ]


def registration_notice(db: Session, student: Student) -> str | None:
    """"Spring 2027 registration opens Nov 3." for the soonest planned term whose registration hasn't opened yet."""
    term = (db.query(Term).join(PlanItem, PlanItem.term_id == Term.id)
            .filter(PlanItem.student_id == student.student_id, Term.registration_opens.isnot(None),
                    Term.registration_opens >= today())
            .order_by(Term.registration_opens).first())
    return f"{term.name} registration opens {short_date(term.registration_opens)}." if term else None
