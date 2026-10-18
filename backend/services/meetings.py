"""Meetings (spec 18): bookable staff, weekly availability, booking, and the meeting state machine shared with the
advisor side (spec 24). Staff are addressed by their user id (the Graduate office is an admin without an advisors row).
Times are stored in UTC and shown in the school time zone (core.time.local_zone())."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.errors import ApiError, bad_request, conflict, not_found
from core.time import DAY_NAMES, MONTH_NAMES, iso_z, local_midnight, local_zone, now, short_date, today
from models import (MEETING_ACTIVE, Advisor, AdvisorAvailability, AdvisorStudentAssignment, Meeting, PlanItem, Student,
                    Term, User)
from services import audit, messages, preferences
from services.auth import user_payload
from services.calendar import class_events
from services.catalog import next_term

MEETING_LENGTH = timedelta(minutes=30)
BOOKING_WINDOW_WEEKS = 2
LEAD_TIME = timedelta(hours=12)  # slots starting sooner than this are shown as taken
FORMATS = {"In person": "in_person", "Online": "online"}
FORMAT_LABELS = {value: label for label, value in FORMATS.items()}
TOPIC_TAIL = ["Capstone topics", "Add or drop a course", "Internship or career", "Something else"]
VIDEO_URL = "https://meet.example.edu/{id}"  # placeholder until a video provider is configured
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SLOT_TAKEN = "That time was just taken. Pick another."
ACTION_LABELS = {"cancel": "cancelled", "accept": "accepted", "decline": "declined", "propose": "rescheduled",
                 "complete": "completed", "no-show": "marked as a no-show"}


# --- time helpers -------------------------------------------------------------------------------------------------

def _local(value: datetime) -> datetime:
    return value.astimezone(local_zone())


def _at(day: date, clock: time) -> datetime:
    """A school-local date and time as tz-aware UTC."""
    return datetime.combine(day, clock, local_zone()).astimezone(timezone.utc)


def _hhmm(value: datetime) -> str:
    return _local(value).strftime("%H:%M")


def _when(value: datetime) -> str:
    """"Thu, Oct 8 at 15:00"."""
    local = _local(value)
    return f"{DAY_NAMES[local.weekday()]}, {short_date(local.date())} at {local.strftime('%H:%M')}"


def first_week() -> date:
    """The earliest bookable week: this Monday, or next Monday once the weekend starts."""
    day = today()
    monday = day - timedelta(days=day.weekday())
    return monday + timedelta(days=7) if day.weekday() >= 5 else monday


def _check_week(week: date) -> None:
    if week.weekday() != 0:
        raise bad_request("Send the Monday of the week you want.")
    first = first_week()
    if not first <= week < first + timedelta(weeks=BOOKING_WINDOW_WEEKS):
        raise bad_request(f"Pick a week within the next {BOOKING_WINDOW_WEEKS} weeks.")


# --- staff --------------------------------------------------------------------------------------------------------

def _my_advisor_ids(db: Session, student: Student) -> set[int]:
    """User ids of the student's assigned advisors."""
    return {user_id for user_id, in (
        db.query(Advisor.user_id).join(AdvisorStudentAssignment, AdvisorStudentAssignment.advisor_id == Advisor.advisor_id)
        .filter(AdvisorStudentAssignment.student_id == student.student_id))}


def _windows(db: Session, user_id: int) -> list[AdvisorAvailability]:
    return (db.query(AdvisorAvailability)
            .filter(AdvisorAvailability.staff_user_id == user_id, AdvisorAvailability.kind == "booking")
            .order_by(AdvisorAvailability.weekday, AdvisorAvailability.start_time).all())


def _staff_members(db: Session, student: Student) -> tuple[list[User], set[int]]:
    """Active staff with booking hours that the student may book: their own advisor(s) first, then bookable staff."""
    mine = _my_advisor_ids(db, student)
    with_hours = db.query(AdvisorAvailability.staff_user_id).filter(AdvisorAvailability.kind == "booking")
    users = (db.query(User)
             .filter(User.is_active.is_(True), User.role != "student", User.user_id.in_(with_hours),
                     or_(User.bookable.is_(True), User.user_id.in_(mine)))
             .all())
    users.sort(key=lambda user: (user.user_id not in mine, user.role != "advisor", user.name))
    return users, mine


def _staff(db: Session, student: Student, staff_id: int) -> User:
    users, _ = _staff_members(db, student)
    staff = next((user for user in users if user.user_id == staff_id), None)
    if staff is None:
        raise not_found("Staff member")
    return staff


def _plan_topic(db: Session, student: Student) -> str:
    """"Spring 2027 plan": the next term the student has planned courses in, else the next term."""
    term = (db.query(Term).join(PlanItem, PlanItem.term_id == Term.id)
            .filter(PlanItem.student_id == student.student_id, Term.start_date > today())
            .order_by(Term.start_date).first()) or next_term(db)
    return f"{term.name} plan" if term else "Next term plan"


def bookable_staff(db: Session, student: Student) -> dict:
    users, mine = _staff_members(db, student)
    staff = []
    for user in users:
        windows = _windows(db, user.user_id)
        staff.append({
            "id": user.user_id, "user_id": user.user_id, "name": user.name, "initials": user_payload(user)["initials"],
            "role": "Faculty advisor" if user.user_id in mine else (user.title or user.role.capitalize()),
            "helps": user.helps_with, "is_my_advisor": user.user_id in mine,
            "office": next((window.location for window in windows if window.location), None),
            "meeting_length": int(MEETING_LENGTH.total_seconds() // 60), "booking_window_weeks": BOOKING_WINDOW_WEEKS,
        })
    return {"staff": staff, "topics": [_plan_topic(db, student), *TOPIC_TAIL], "formats": list(FORMATS),
            "first_week": first_week().isoformat()}


# --- availability -------------------------------------------------------------------------------------------------

def _intervals(meeting: Meeting) -> list[tuple[datetime, datetime]]:
    """The times an active meeting holds: its slot, plus the proposed one while a new time is pending."""
    spans = [(meeting.starts_at, meeting.ends_at)]
    if meeting.status == "proposed" and meeting.proposed_starts_at is not None:
        spans.append((meeting.proposed_starts_at, meeting.proposed_starts_at + (meeting.ends_at - meeting.starts_at)))
    return spans


def _busy(db: Session, student: Student, staff_user_id: int, start: datetime, end: datetime,
          ignore_id: int | None = None) -> list[tuple[datetime, datetime]]:
    """Busy intervals in [start, end): the staff member's and the student's active meetings and the student's classes."""
    slack = timedelta(days=1)
    query = db.query(Meeting).filter(
        Meeting.status.in_(MEETING_ACTIVE),
        or_(Meeting.staff_user_id == staff_user_id, Meeting.student_id == student.student_id),
        or_(and_(Meeting.starts_at < end + slack, Meeting.ends_at > start - slack),
            and_(Meeting.proposed_starts_at.isnot(None), Meeting.proposed_starts_at < end + slack,
                 Meeting.proposed_starts_at > start - slack)))
    if ignore_id is not None:
        query = query.filter(Meeting.id != ignore_id)
    busy = [span for meeting in query for span in _intervals(meeting)]
    first, last = _local(start).date(), _local(end - timedelta(microseconds=1)).date()
    for event in class_events(db, student, first, last):
        day = date.fromisoformat(event["date"])
        busy.append((_at(day, time.fromisoformat(event["start"])), _at(day, time.fromisoformat(event["end"]))))
    return busy


def _week_slots(db: Session, student: Student, staff: User, week: date,
                ignore_id: int | None = None) -> list[tuple[date, list[tuple[datetime, bool, AdvisorAvailability]]]]:
    """Mon–Fri of the week, each with its (start, taken, window) slots in time order."""
    busy = _busy(db, student, staff.user_id, _at(week, time(0)), _at(week + timedelta(days=5), time(0)), ignore_id)
    cutoff = now() + LEAD_TIME
    windows = _windows(db, staff.user_id)
    days = []
    for offset in range(5):
        day = week + timedelta(days=offset)
        slots = []
        for window in windows:
            if window.weekday != day.weekday():
                continue
            cursor, stop = datetime.combine(day, window.start_time), datetime.combine(day, window.end_time)
            while cursor + MEETING_LENGTH <= stop:
                start = cursor.replace(tzinfo=local_zone()).astimezone(timezone.utc)
                end = start + MEETING_LENGTH
                taken = start < cutoff or any(b_start < end and start < b_end for b_start, b_end in busy)
                slots.append((start, taken, window))
                cursor += MEETING_LENGTH
        days.append((day, sorted(slots, key=lambda slot: slot[0])))
    return days


def availability(db: Session, student: Student, staff_id: int, week: date) -> dict:
    staff = _staff(db, student, staff_id)
    _check_week(week)
    days = []
    for day, slots in _week_slots(db, student, staff, week):
        open_ = sum(1 for _, taken, _ in slots if not taken)
        days.append({"date": day.isoformat(), "dow": DAY_NAMES[day.weekday()], "day": str(day.day), "open": open_,
                     "free": f"{open_} open" if open_ else "Full",
                     "slots": [{"starts_at": iso_z(start), "time": _hhmm(start), "taken": taken}
                               for start, taken, _ in slots]})
    return {"staff_id": staff.user_id, "week": week.isoformat(), "time_zone": local_zone().key, "days": days}


def _find_slot(db: Session, student: Student, staff: User, start: datetime, ignore_id: int | None = None):
    """(taken, window) of the slot that starts at `start`, or None when it isn't one of the staff member's slots."""
    local_day = _local(start).date()
    week = local_day - timedelta(days=local_day.weekday())
    for day, slots in _week_slots(db, student, staff, week, ignore_id):
        for slot_start, taken, window in slots:
            if slot_start == start:
                return taken, window
    return None


def _lock_staff(db: Session, staff: User) -> None:
    """Serialises bookings per staff member: a second booking waits here until the first commits."""
    db.query(User.user_id).filter(User.user_id == staff.user_id).with_for_update().one()


# --- rows and text ------------------------------------------------------------------------------------------------

def _names(db: Session, user_ids: set[int]) -> dict[int, str]:
    return dict(db.query(User.user_id, User.name).filter(User.user_id.in_(user_ids)).all()) if user_ids else {}


def _row(meeting: Meeting, staff_name: str) -> dict:
    local = _local(meeting.starts_at)
    day = "Today" if local.date() == today() else DAY_NAMES[local.weekday()]
    return {
        "id": meeting.id,
        "staff_id": meeting.staff_user_id,
        "title": meeting.topic,
        "mon": MONTH_NAMES[local.month - 1],
        "day": str(local.day),
        "meta": " · ".join([day, local.strftime("%H:%M"), FORMAT_LABELS[meeting.format], staff_name]),
        "starts_at": iso_z(meeting.starts_at),
        "status": meeting.status,
        "proposed_starts_at": iso_z(meeting.proposed_starts_at) if meeting.proposed_starts_at else None,
    }


def _topic_phrase(topic: str) -> str:
    if topic in TOPIC_TAIL:
        return topic[0].lower() + topic[1:]
    if topic.endswith(" plan"):
        return f"your {topic}"
    return f"“{topic}”"


def summary_text(meeting: Meeting, staff: User) -> str:
    """The design sentence: "You're meeting Dr. Smith on Wednesday, Oct 7 at 10:00–10:30 (in person) about capstone topics."."""
    local = _local(meeting.starts_at)
    when = (f"{WEEKDAY_NAMES[local.weekday()]}, {short_date(local.date())} at "
            f"{local.strftime('%H:%M')}–{_hhmm(meeting.ends_at)}")
    detail = f"on {when} ({FORMAT_LABELS[meeting.format].lower()}) about {_topic_phrase(meeting.topic)}."
    if meeting.status == "confirmed":
        return f"You're meeting {staff.name} {detail} A confirmation is in your Messages."
    return f"You asked to meet {staff.name} {detail}"


def _place(meeting: Meeting) -> str:
    return "online" if meeting.format == "online" else (meeting.location or "in person")


# --- booking ------------------------------------------------------------------------------------------------------

def _auto_confirm(db: Session, staff: User) -> bool:
    """Spec 27's "auto-confirm bookings" staff setting."""
    return bool(preferences.get(db, staff).get("bookings", {}).get("autoConfirm", False))


def book(db: Session, student: Student, user: User, data: dict, ip: str | None = None) -> dict:
    """data: staff_id, starts_at (aware), format ("In person" / "Online"), topic, note, attach_plan."""
    staff = _staff(db, student, data["staff_id"])
    _lock_staff(db, staff)
    start = data["starts_at"].astimezone(timezone.utc)
    local_day = _local(start).date()
    _check_week(local_day - timedelta(days=local_day.weekday()))
    slot = _find_slot(db, student, staff, start)
    if slot is None:
        raise bad_request("Pick one of the open times.")
    taken, window = slot
    if taken:
        raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)

    format_ = FORMATS[data["format"]]
    advisor = db.query(Advisor).filter(Advisor.user_id == staff.user_id).one_or_none()
    meeting = Meeting(student_id=student.student_id, advisor_id=advisor.advisor_id if advisor else None,
                      staff_user_id=staff.user_id, starts_at=start, ends_at=start + MEETING_LENGTH, format=format_,
                      location=window.location if format_ == "in_person" else None, topic=data["topic"],
                      note=data.get("note"), attach_plan=bool(data.get("attach_plan")),
                      status="confirmed" if _auto_confirm(db, staff) else "requested")
    db.add(meeting)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)
    if format_ == "online":
        meeting.video_url = VIDEO_URL.format(id=meeting.id)

    when, place = _when(start), _place(meeting)
    if meeting.status == "confirmed":
        messages.notify(db, user.user_id, f"Meeting confirmed: {meeting.topic} with {staff.name} on {when} ({place}).")
        messages.notify(db, staff.user_id, f"{user.name} booked a meeting: {meeting.topic} on {when} ({place}).")
    else:
        messages.notify(db, user.user_id, f"Meeting requested: {meeting.topic} with {staff.name} on {when} ({place}). "
                                          f"You'll get a message here when it's confirmed.")
        messages.notify(db, staff.user_id, f"{user.name} requested a meeting: {meeting.topic} on {when} ({place}). "
                                           f"Accept it or propose another time.")
    audit.record(db, user, "meeting.book", f"{user.name} booked {meeting.topic} with {staff.name} on {when}",
                 target=("meeting", meeting.id), ip=ip)
    db.commit()
    return {"id": meeting.id, "status": meeting.status, "summary": summary_text(meeting, staff),
            "meeting": _row(meeting, staff.name)}


# --- reading ------------------------------------------------------------------------------------------------------

def _upcoming(db: Session, student: Student):
    """Active meetings from the start of today (school time) on, soonest first."""
    return (db.query(Meeting)
            .filter(Meeting.student_id == student.student_id, Meeting.status.in_(MEETING_ACTIVE),
                    Meeting.starts_at >= local_midnight())
            .order_by(Meeting.starts_at, Meeting.id))


def upcoming_for_student(db: Session, student: Student) -> list[dict]:
    rows = _upcoming(db, student).all()
    names = _names(db, {meeting.staff_user_id for meeting in rows})
    return [_row(meeting, names.get(meeting.staff_user_id, "Former staff")) for meeting in rows]


def next_meeting(db: Session, student: Student) -> dict | None:
    """The student's next confirmed meeting, for the AI advisor's context panel."""
    meeting = _upcoming(db, student).filter(Meeting.status == "confirmed").first()
    if meeting is None:
        return None
    local = _local(meeting.starts_at)
    return {"date": local.date().isoformat(), "time": local.strftime("%H:%M")}


def events_for_student(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    """Active meetings in [from_, to] as schedule events (spec 14 shape, kind "meeting")."""
    rows = (db.query(Meeting)
            .filter(Meeting.student_id == student.student_id, Meeting.status.in_(MEETING_ACTIVE),
                    Meeting.starts_at >= _at(from_, time(0)), Meeting.starts_at < _at(to + timedelta(days=1), time(0)))
            .order_by(Meeting.starts_at, Meeting.id).all())
    names = _names(db, {meeting.staff_user_id for meeting in rows})
    events = []
    for meeting in rows:
        local = _local(meeting.starts_at)
        place = "Online" if meeting.format == "online" else (meeting.location or "In person")
        events.append({"id": f"mtg-{meeting.id}", "kind": "meeting", "title": meeting.topic, "type": "Advising",
                       "date": local.date().isoformat(), "start": local.strftime("%H:%M"), "end": _hhmm(meeting.ends_at),
                       "location": f"{place} · {names.get(meeting.staff_user_id, 'Former staff')}", "note": meeting.note,
                       "editable": False, "status": meeting.status, "reminder_minutes": None})
    return events


def export_rows(db: Session, student: Student) -> list[dict]:
    """Every meeting of the student, for the data export (spec 17)."""
    rows = db.query(Meeting).filter(Meeting.student_id == student.student_id).order_by(Meeting.starts_at).all()
    names = _names(db, {meeting.staff_user_id for meeting in rows})
    return [{"topic": meeting.topic, "with": names.get(meeting.staff_user_id), "startsAt": iso_z(meeting.starts_at),
             "endsAt": iso_z(meeting.ends_at), "format": FORMAT_LABELS[meeting.format], "location": meeting.location,
             "status": meeting.status, "note": meeting.note, "attachPlan": meeting.attach_plan}
            for meeting in rows]


# --- changes ------------------------------------------------------------------------------------------------------

def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def act(db: Session, user: User, meeting_id: int, action: str, data: dict | None = None, ip: str | None = None) -> dict:
    """cancel (either side), accept (student: proposed time; staff: request), decline / propose / complete / no-show
    (staff). Anyone else gets 404; a move the meeting's state doesn't allow gets 409."""
    data = data or {}
    meeting = db.get(Meeting, meeting_id)
    student = db.get(Student, meeting.student_id) if meeting else None
    is_student = student is not None and student.user_id == user.user_id
    is_staff = meeting is not None and meeting.staff_user_id == user.user_id
    if not (is_student or is_staff):
        raise not_found("Meeting")
    staff = db.get(User, meeting.staff_user_id)
    student_user = db.get(User, student.user_id)
    refused = conflict(f"This meeting can't be {ACTION_LABELS[action]} now.")
    when = _when(meeting.starts_at)
    notice: tuple[int, str] | None = None

    if action == "cancel":
        if meeting.status not in MEETING_ACTIVE:
            raise refused
        meeting.status, meeting.proposed_starts_at = "cancelled", None
        notice = ((staff.user_id, f"{student_user.name} cancelled {meeting.topic} on {when}.") if is_student else
                  (student_user.user_id, f"{staff.name} cancelled your meeting on {when} ({meeting.topic})."))
    elif action == "accept":
        if is_student and meeting.status == "proposed" and meeting.proposed_starts_at is not None:
            length = meeting.ends_at - meeting.starts_at
            meeting.starts_at, meeting.ends_at = meeting.proposed_starts_at, meeting.proposed_starts_at + length
            meeting.proposed_starts_at, meeting.status = None, "confirmed"
            notice = (staff.user_id, f"{student_user.name} accepted the new time: {meeting.topic} on {_when(meeting.starts_at)}.")
        elif is_staff and meeting.status == "requested":
            meeting.status = "confirmed"
            notice = (student_user.user_id, f"{staff.name} confirmed your meeting on {when} ({meeting.topic}).")
        else:
            raise refused
    elif action == "decline":
        if not (is_staff and meeting.status == "requested"):
            raise refused
        meeting.status = "cancelled"
        if data.get("note"):
            meeting.advisor_notes = data["note"]
        reason = f" {data['note']}" if data.get("note") else ""
        notice = (student_user.user_id, f"{staff.name} can't meet on {when} ({meeting.topic}).{reason} Book another time.")
    elif action == "propose":
        if not (is_staff and meeting.status in ("requested", "confirmed")):
            raise refused
        start = data.get("starts_at")
        if start is None:
            raise _validation("startsAt", "Pick the new time.")
        start = start.astimezone(timezone.utc)
        _lock_staff(db, staff)
        slot = _find_slot(db, student, staff, start, ignore_id=meeting.id)
        if slot is None:
            raise bad_request("Pick one of your open times.")
        if slot[0]:
            raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)
        meeting.status, meeting.proposed_starts_at = "proposed", start
        notice = (student_user.user_id, f"{staff.name} proposed a new time for {meeting.topic}: {_when(start)}. "
                                        f"Accept it on Book a meeting.")
    elif action in ("complete", "no-show"):
        if not (is_staff and meeting.status == "confirmed" and meeting.starts_at <= now()):
            raise refused
        meeting.status = "completed" if action == "complete" else "no_show"
    else:
        raise not_found("Action")

    if notice is not None:
        messages.notify(db, *notice)
    audit.record(db, user, f"meeting.{action.replace('-', '_')}", f"{user.name} {ACTION_LABELS[action]} {meeting.topic} ({when})",
                 target=("meeting", meeting.id), ip=ip)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)
    return _row(meeting, staff.name)


def cancel_future_for(db: Session, student: Student) -> None:
    """Self-delete (spec 17): cancels the student's upcoming meetings and tells the staff member. Doesn't commit."""
    for meeting in (db.query(Meeting).filter(Meeting.student_id == student.student_id,
                                             Meeting.status.in_(MEETING_ACTIVE), Meeting.starts_at >= now())):
        meeting.status, meeting.proposed_starts_at = "cancelled", None
        messages.notify(db, meeting.staff_user_id, f"{student.name} cancelled {meeting.topic} on {_when(meeting.starts_at)}.")
