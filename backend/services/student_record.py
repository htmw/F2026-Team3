"""The advisor's view of one advisee (spec 22): summary stats, the plan review, degree progress, meetings, private
notes and shared activity. Decisions go through services/approvals (spec 23's core)."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from core.deps import advisor_can_see
from core.errors import ApiError, forbidden, not_found
from core.time import local_zone, now, short_date, today
from models import (MEETING_ACTIVE, Advisor, AdvisorNote, AdvisorStudentAssignment, AiThread, ApprovalRequest,
                    Assignment, AssignmentSubmission, AuditEvent, Course, CourseSection, Meeting, PlanItem, Program,
                    Student, Term, User)
from services import audit, preferences
from services.advisees import initials, short_name
from services.ai.threads import list_threads
from services.assignments import on_time_rate
from services.catalog import current_term, next_term
from services.dashboard import gpa_status, gpa_summary
from services.degree_audit import assign_groups, group_out, student_courses
from services.meetings import FORMAT_LABELS

UNDO_WINDOW = timedelta(minutes=10)
PAST_MEETINGS = 2
ACTIVITY_LIMIT = 8
SHARED_ACTIONS = ("meeting.book", "assignment.submit")
REVIEW_LABELS = {"pending": "Waiting for you", "approved": "Approved", "changes_requested": "Changes requested"}


def _student(db: Session, advisor: Advisor, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    advisor_can_see(db, advisor.advisor_id, student_id)
    return student


def _first_name(db: Session, student: Student) -> str:
    user = db.get(User, student.user_id)
    return (user.preferred_name or user.first_name) if user and (user.preferred_name or user.first_name) \
        else student.name.split()[0]


def _local_date(value) -> date:
    return value.astimezone(local_zone()).date()


def _term_on(db: Session, day: date) -> Term | None:
    """The term running on `day`, else the next one to start."""
    return (db.query(Term).filter(Term.end_date >= day).order_by(Term.start_date).first())


def header(db: Session, student: Student) -> dict:
    program = db.get(Program, student.program_id)
    link = db.get(AdvisorStudentAssignment, student.student_id)
    terms = [t for t in (db.get(Term, student.start_term_id) if student.start_term_id else None,
                         _term_on(db, _local_date(link.updated_at)) if link else None) if t is not None]
    since = max(terms, key=lambda t: t.start_date) if terms else None
    parts = [program.program_name if program else None, f"your advisee since {since.name}" if since else None]
    return {"id": student.student_id, "userId": student.user_id, "name": short_name(student.name),
            "fullName": student.name, "firstName": _first_name(db, student), "initials": initials(student.name),
            "subtitle": " · ".join(p for p in parts if p)}


def stats(db: Session, student: Student, pending_plan: bool) -> list[dict]:
    summary = gpa_summary(db, student)
    cumulative, change = summary["cumulative"], summary["change"]
    if change:
        gpa_note = f"{'Up' if change > 0 else 'Down'} {abs(change):.2f} from last term"
    else:
        gpa_note = "No change from last term" if change == 0 else "First graded term"
    gpa_tag = gpa_status(cumulative)
    gpa_tone = {"On track": "teal", "Watch": "amber", "At risk": "pink"}.get(gpa_tag, "gray")

    program = db.get(Program, student.program_id)
    required = float(program.total_required_credits)
    courses = student_courses(db, student)
    earned = sum(row.credits for row in courses if row.state == "completed")
    doing = sum(row.credits for row in courses if row.state == "in_progress")
    left = max(0.0, required - earned - doing)
    term = current_term(db)
    pct = round(earned / required * 100) if required else 0

    on_time, done, total = on_time_rate(db, student)
    if on_time is None:
        on_time_tile = {"label": "On-time submission", "value": "—", "tag": "No data", "tone": "gray",
                        "note": "No assignments due yet"}
    else:
        tag, tone = ("Good", "teal") if on_time >= 90 else ("Fair", "amber") if on_time >= 75 else ("Low", "pink")
        on_time_tile = {"label": "On-time submission", "value": f"{on_time}%", "tag": tag, "tone": tone,
                        "note": f"{done} of {total} on time"}

    graduation = ({"tag": "Pending", "tone": "amber", "note": "If this plan is approved"} if pending_plan else
                  {"tag": "Planned", "tone": "indigo", "note": f"{max(0.0, required - earned):g} credits to go"})
    return [
        {"label": "Cumulative GPA", "value": f"{cumulative:.2f}" if cumulative is not None else "—", "tag": gpa_tag,
         "tone": gpa_tone, "note": gpa_note},
        {"label": "Credits", "value": f"{earned:g} / {required:g}", "tag": f"{pct}%", "tone": "indigo",
         "note": f"{doing:g} in progress · {left:g} left after {term.season if term else 'this term'}"},
        on_time_tile,
        {"label": "Expected graduation", "value": student.expected_graduation or "—", **graduation},
    ]


def _when(section: CourseSection | None, credits: float) -> str:
    """"Mon 18:10–20:55 · 3 credits"; only the credits when there is no scheduled section."""
    parts = []
    if section and section.meeting_days and section.start_time and section.end_time:
        days = section.meeting_days.replace(",", "/")
        parts.append(f"{days} {section.start_time.strftime('%H:%M')}–{section.end_time.strftime('%H:%M')}")
    parts.append(f"{credits:g} credit{'' if credits == 1 else 's'}")
    return " · ".join(parts)


def _plan_rows(db: Session, student: Student, items: list[PlanItem], term_id: int) -> list[dict]:
    fulfills = {row.course.course_id: group.title for group in assign_groups(db, student) for row in group.taken}
    sections = {s.course_id: s for s in db.query(CourseSection).filter(CourseSection.term_id == term_id)}
    rows = []
    for item in items:
        course = db.get(Course, item.course_id)
        rows.append({"code": course.course_code, "name": course.course_name,
                     "when": _when(sections.get(course.course_id), float(course.credits)),
                     "fulfills": fulfills.get(course.course_id)})
    return sorted(rows, key=lambda row: row["code"])


def latest_plan_request(db: Session, student: Student) -> ApprovalRequest | None:
    """The pending plan request, else the most recently decided one."""
    base = db.query(ApprovalRequest).filter(ApprovalRequest.student_id == student.student_id,
                                            ApprovalRequest.type == "plan",
                                            ApprovalRequest.status.in_(tuple(REVIEW_LABELS)))
    pending = base.filter(ApprovalRequest.status == "pending").order_by(ApprovalRequest.created_at.desc()).first()
    return pending or base.order_by(ApprovalRequest.decided_at.desc().nulls_last(), ApprovalRequest.id.desc()).first()


def review(db: Session, advisor: Advisor, student: Student, request: ApprovalRequest | None) -> dict | None:
    if request is None:
        return None
    ids = (request.payload or {}).get("planItemIds") or []
    items = db.query(PlanItem).filter(PlanItem.id.in_(ids)).order_by(PlanItem.id).all() if ids else []
    notes = [item.note.strip() for item in items if item.note and item.note.strip()]
    first = _first_name(db, student)
    shared = short_date(_local_date(request.created_at))
    # The record offers Undo for 10 minutes; approvals.reopen itself allows 24 hours (the dashboard's window).
    can_undo = (request.status != "pending" and request.decided_by == advisor.user_id and request.decided_at is not None
                and now() - request.decided_at <= UNDO_WINDOW)
    term = db.get(Term, request.term_id) if request.term_id else None
    opens = term.registration_opens if term and term.registration_opens and term.registration_opens >= today() else None
    return {
        "requestId": request.id,
        "title": request.title.split(" · ")[0],
        "subtitle": f"Built with Acadmate · shared by {first} on {shared}",
        "status": request.status,
        "statusLabel": REVIEW_LABELS[request.status],
        "plan": _plan_rows(db, student, items, request.term_id) if request.term_id else [],
        "checks": [{"ok": bool(c.get("ok")), "blocking": bool(c.get("blocking")), "text": c.get("text") or ""}
                   for c in (request.precheck or {}).get("checks", [])],
        "studentNote": " ".join(dict.fromkeys(notes)) or None,
        "comment": request.comment,
        "decidedAt": request.decided_at,
        "canUndo": can_undo,
        "registrationOpens": short_date(opens) if opens else None,
    }


def planned_term(db: Session, student: Student) -> dict | None:
    """Without a plan request: the next term's planned courses, read-only."""
    term = next_term(db)
    if term is None:
        return None
    items = (db.query(PlanItem).filter(PlanItem.student_id == student.student_id, PlanItem.term_id == term.id)
             .order_by(PlanItem.id).all())
    return {"title": f"{term.name} plan", "plan": _plan_rows(db, student, items, term.id)} if items else None


def groups(db: Session, student: Student) -> list[dict]:
    out = []
    for group in assign_groups(db, student):
        row = group_out(group)
        out.append({"title": row["title"], "count": row["count"], "done": group.done,
                    "inProgress": min(group.count("in_progress"), group.needed - group.done), "required": group.needed})
    return out


def _meeting_meta(meeting: Meeting, day: date) -> str:
    local = meeting.starts_at.astimezone(local_zone())
    when = "Today" if local.date() == day else short_date(local.date())
    return " · ".join([when, local.strftime("%H:%M"), FORMAT_LABELS[meeting.format]])


def meetings(db: Session, advisor: Advisor, student: Student, day: date | None = None) -> list[dict]:
    """Upcoming active meetings with the advisor (from the start of today, school time), then the last two past ones."""
    day = day or today()
    start = datetime.combine(day, time(0), local_zone()).astimezone(timezone.utc)
    base = db.query(Meeting).filter(Meeting.student_id == student.student_id, Meeting.staff_user_id == advisor.user_id)
    upcoming = (base.filter(Meeting.status.in_(MEETING_ACTIVE), Meeting.starts_at >= start)
                .order_by(Meeting.starts_at).all())
    past = (base.filter(Meeting.status.in_(("confirmed", "completed")), Meeting.starts_at < start)
            .order_by(Meeting.starts_at.desc()).limit(PAST_MEETINGS).all())
    return [{"id": m.id, "title": m.topic, "meta": _meeting_meta(m, day), "past": m in past} for m in upcoming + past]


def _note_out(note: AdvisorNote, viewer: User) -> dict:
    return {"id": note.id, "text": note.text, "when": short_date(_local_date(note.created_at)),
            "mine": note.author_id == viewer.user_id}


def notes(db: Session, student: Student, viewer: User) -> list[dict]:
    rows = (db.query(AdvisorNote).filter(AdvisorNote.student_id == student.student_id)
            .order_by(AdvisorNote.created_at.desc(), AdvisorNote.id.desc()))
    return [_note_out(note, viewer) for note in rows]


def _shares_ai(db: Session, student: Student) -> bool:
    user = db.get(User, student.user_id)
    return bool(user and preferences.get(db, user)["ai"].get("shareWithAdvisor"))


def _sentence(db: Session, event: AuditEvent) -> str | None:
    target = int(event.target_id) if event.target_id and event.target_id.isdigit() else None
    """The activity sentence, or None when the event's meeting or assignment no longer exists."""
    if event.action == "meeting.book":
        meeting = db.get(Meeting, target) if target else None
        return f"Booked “{meeting.topic}” for {short_date(_local_date(meeting.starts_at))}." if meeting else None
    if event.action == "assignment.submit":
        assignment = db.get(Assignment, target) if target else None
        return f"Submitted {assignment.title}." if assignment else None
    return None


def activity(db: Session, student: Student, shared_ai: bool, limit: int = ACTIVITY_LIMIT) -> list[dict]:
    """What the student shared: plans sent (approval requests), meetings booked, work submitted and graded, and AI chats when shared."""
    entries: list[tuple] = []
    events = (db.query(AuditEvent)
              .filter(AuditEvent.actor_id == student.user_id, AuditEvent.action.in_(SHARED_ACTIONS),
                      AuditEvent.result == "success")
              .order_by(AuditEvent.at.desc(), AuditEvent.id.desc()).yield_per(50))
    for event in events:
        text = _sentence(db, event)
        if text:
            entries.append((event.at, text))
            if len(entries) == limit:
                break
    plans = (db.query(ApprovalRequest)
             .filter(ApprovalRequest.student_id == student.student_id, ApprovalRequest.type == "plan")
             .order_by(ApprovalRequest.created_at.desc()).limit(limit))
    for request in plans:
        entries.append((request.created_at, f"Shared the {request.title.split(' · ')[0]} from Acadmate."))
    graded = (db.query(AssignmentSubmission, Assignment)
              .join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
              .filter(AssignmentSubmission.student_id == student.student_id, AssignmentSubmission.status == "graded",
                      AssignmentSubmission.submitted_at.isnot(None))
              .order_by(AssignmentSubmission.submitted_at.desc()).limit(limit))
    for submission, assignment in graded:
        score = f" ({submission.score_text})" if submission.score_text else ""
        entries.append((submission.submitted_at, f"Completed {assignment.title}{score}."))
    if shared_ai:
        threads = (db.query(AiThread).filter(AiThread.student_id == student.student_id)
                   .order_by(AiThread.updated_at.desc()).limit(limit))
        for thread in threads:
            entries.append((thread.updated_at, f"Asked Acadmate: “{thread.title}”"))
    entries.sort(key=lambda entry: entry[0], reverse=True)
    return [{"when": short_date(_local_date(at)), "text": text} for at, text in entries[:limit]]


def record(db: Session, advisor: Advisor, student_id: int) -> dict:
    student = _student(db, advisor, student_id)
    viewer = db.get(User, advisor.user_id)
    request = latest_plan_request(db, student)
    shared_ai = _shares_ai(db, student)
    return {
        "student": header(db, student),
        "stats": stats(db, student, request is not None and request.status == "pending"),
        "review": review(db, advisor, student, request),
        "plannedTerm": planned_term(db, student) if request is None else None,
        "groups": groups(db, student),
        "meetings": meetings(db, advisor, student),
        "notes": notes(db, student, viewer),
        "activity": activity(db, student, shared_ai),
        "aiShared": shared_ai,
    }


def add_note(db: Session, advisor: Advisor, student_id: int, text: str) -> dict:
    """Adds a private note. The audit row never holds the text. The caller commits."""
    student = _student(db, advisor, student_id)
    actor = db.get(User, advisor.user_id)
    note = AdvisorNote(student_id=student.student_id, author_id=actor.user_id, text=text, created_at=now())
    db.add(note)
    db.flush()
    audit.record(db, actor, "note.add", f"Added a private note on {student.name}", target=("student", student.student_id))
    return _note_out(note, actor)


def delete_note(db: Session, advisor: Advisor, note_id: int) -> None:
    """Deletes one of the advisor's own notes. The caller commits."""
    note = db.get(AdvisorNote, note_id)
    if note is None:
        raise not_found("Note")
    actor = db.get(User, advisor.user_id)
    if note.author_id != actor.user_id:
        raise forbidden("You can only delete your own notes.")
    student = db.get(Student, note.student_id)
    db.delete(note)
    audit.record(db, actor, "note.delete", f"Deleted a private note on {student.name}",
                 target=("student", student.student_id))


def ai_threads(db: Session, advisor: Advisor, student_id: int) -> dict:
    student = _student(db, advisor, student_id)
    if not _shares_ai(db, student):
        raise ApiError(403, "NOT_SHARED", f"{_first_name(db, student)} hasn't shared their AI chats with you.")
    return {"threads": list_threads(db, student)}
