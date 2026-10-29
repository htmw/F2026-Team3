"""Advisor meetings (spec 24): the agenda with office-hour rows, booking requests, office hours, free slots, booking
for an advisee and private notes. Decisions (accept / propose / cancel / complete / no-show) are spec 18's
meetings.act(); slot rules are spec 18's too."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.deps import advisor_can_see
from core.errors import ApiError, bad_request, not_found
from core.time import DAY_NAMES, iso_z, local_zone, now, short_date, today
from models import MEETING_ACTIVE, Advisor, AdvisorAvailability, Meeting, Student, User
from services import audit, messages
from services.advisees import short_name
from services.meetings import (FORMAT_LABELS, FORMATS, SLOT_TAKEN, VIDEO_URL, _week_slots, booking_weeks, check_week,
                               local_when, lock_staff, meeting_length, office_windows, slot_at)

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
AGENDA_STATUSES = ("confirmed", "proposed", "completed", "no_show")
RANGE_DAYS = {"today": 1, "week": 7}
EARLIEST, LATEST = time(7, 0), time(22, 0)


def _local(value: datetime) -> datetime:
    return value.astimezone(local_zone())


def _at(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, local_zone()).astimezone(timezone.utc)


def _day_label(day: date) -> str:
    return "Today" if day == today() else f"{DAY_NAMES[day.weekday()]}, {short_date(day)}"


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def _meeting_row(meeting: Meeting, student: Student) -> dict:
    local = _local(meeting.starts_at)
    proposed = _local(meeting.proposed_starts_at) if meeting.proposed_starts_at else None
    return {
        "id": meeting.id, "kind": "meeting", "day": _day_label(local.date()), "date": local.date().isoformat(),
        "time": local.strftime("%H:%M"), "who": short_name(student.name), "studentId": student.student_id,
        "userId": student.user_id, "topic": meeting.topic, "format": FORMAT_LABELS[meeting.format],
        "status": meeting.status, "videoUrl": meeting.video_url, "location": meeting.location,
        "notes": meeting.advisor_notes, "note": meeting.note,
        "proposedTime": f"{_day_label(proposed.date())} · {proposed.strftime('%H:%M')}" if proposed else None,
        "canComplete": meeting.status == "confirmed" and meeting.starts_at <= now(),
        "canCancel": meeting.status in MEETING_ACTIVE,
    }


def _office_row(window: AdvisorAvailability, day: date) -> dict:
    return {
        "id": f"off-{window.id}-{day.isoformat()}", "kind": "office_hours", "day": _day_label(day),
        "date": day.isoformat(), "time": window.start_time.strftime("%H:%M"), "who": "Drop-in office hours",
        "studentId": None, "userId": None, "topic": "Open to all advisees", "format": "In person", "status": "open",
        "videoUrl": None, "location": window.location, "notes": None, "note": None, "proposedTime": None,
        "canComplete": False, "canCancel": False,
    }


def agenda(db: Session, advisor: Advisor, range_: str = "today") -> list[dict]:
    """The advisor's meetings from the start of today for 1 or 7 days (completed / no-show ones only today), with an
    office-hours row for each window in range, by time."""
    first = today()
    days = RANGE_DAYS[range_]
    start, end = _at(first, time(0)), _at(first + timedelta(days=days), time(0))
    meetings = (db.query(Meeting, Student).join(Student, Student.student_id == Meeting.student_id)
                .filter(Meeting.staff_user_id == advisor.user_id, Meeting.status.in_(AGENDA_STATUSES),
                        Meeting.starts_at >= start, Meeting.starts_at < end))
    rows = [_meeting_row(meeting, student) for meeting, student in meetings
            if meeting.status in MEETING_ACTIVE or _local(meeting.starts_at).date() == first]
    windows = office_windows(db, advisor.user_id)
    for offset in range(days):
        day = first + timedelta(days=offset)
        rows.extend(_office_row(window, day) for window in windows if window.weekday == day.weekday())
    rows.sort(key=lambda row: (row["date"], row["time"]))
    return rows


def requests(db: Session, advisor: Advisor) -> list[dict]:
    """Meetings students asked for that the advisor hasn't answered, soonest first."""
    rows = (db.query(Meeting, Student).join(Student, Student.student_id == Meeting.student_id)
            .filter(Meeting.staff_user_id == advisor.user_id, Meeting.status == "requested",
                    Meeting.starts_at >= _at(today(), time(0)))
            .order_by(Meeting.starts_at, Meeting.id))
    out = []
    for meeting, student in rows:
        local = _local(meeting.starts_at)
        out.append({"id": meeting.id, "studentId": student.student_id, "who": short_name(student.name),
                    "when": f"{_day_label(local.date())} · {local.strftime('%H:%M')}",
                    "topic": f"{meeting.topic} · {FORMAT_LABELS[meeting.format]}", "status": meeting.status})
    return out


def _booking_location(db: Session, advisor: Advisor) -> str | None:
    return (db.query(AdvisorAvailability.location)
            .filter(AdvisorAvailability.staff_user_id == advisor.user_id, AdvisorAvailability.kind == "booking",
                    AdvisorAvailability.location.isnot(None))
            .order_by(AdvisorAvailability.weekday).limit(1).scalar())


def _span(window: AdvisorAvailability) -> str:
    return f"{window.start_time.strftime('%H:%M')}–{window.end_time.strftime('%H:%M')}"


def office_hours(db: Session, advisor: Advisor) -> dict:
    """{days, start, end, location, summary}; summary groups days that share a time ("Wed, Thu · 16:30–17:30")."""
    windows = [w for w in office_windows(db, advisor.user_id) if w.weekday < 5]
    if not windows:
        return {"days": [], "start": None, "end": None, "location": _booking_location(db, advisor),
                "summary": "No office hours set"}
    groups: dict[str, list[str]] = {}
    for window in windows:
        groups.setdefault(_span(window), []).append(WEEKDAYS[window.weekday])
    first = windows[0]
    return {"days": [WEEKDAYS[w.weekday] for w in windows if _span(w) == _span(first)],
            "start": first.start_time.strftime("%H:%M"), "end": first.end_time.strftime("%H:%M"),
            "location": first.location or _booking_location(db, advisor),
            "summary": "; ".join(f"{', '.join(days)} · {span}" for span, days in groups.items())}


def set_office_hours(db: Session, advisor: Advisor, days: list[str], start: time, end: time,
                     location: str | None) -> dict:
    """Replaces the advisor's office hours with one window per chosen day. Audited; the caller commits."""
    if end <= start:
        raise _validation("end", "End after the start time.")
    if start < EARLIEST or end > LATEST:
        raise _validation("start", "Keep office hours between 07:00 and 22:00.")
    before = office_hours(db, advisor)
    for window in office_windows(db, advisor.user_id):
        db.delete(window)
    place = (location or "").strip() or _booking_location(db, advisor)
    for weekday in sorted({WEEKDAYS.index(day) for day in days}):
        db.add(AdvisorAvailability(staff_user_id=advisor.user_id, weekday=weekday, start_time=start, end_time=end,
                                   kind="office_hours", location=place))
    db.flush()
    after = office_hours(db, advisor)
    actor = db.get(User, advisor.user_id)
    audit.record(db, actor, "office_hours.update", f"Set office hours: {after['summary']}",
                 target=("advisor", advisor.advisor_id),
                 changes={"days": [before["days"], after["days"]],
                          "time": [f"{before['start']}–{before['end']}" if before["start"] else None,
                                   f"{after['start']}–{after['end']}" if after["start"] else None]})
    return after


def page(db: Session, advisor: Advisor, range_: str) -> dict:
    """The screen's data; `today` (school time, maybe pinned) bounds the date pickers."""
    return {"today": today().isoformat(), "agenda": agenda(db, advisor, range_), "requests": requests(db, advisor),
            "officeHours": office_hours(db, advisor)}


def _advisee(db: Session, advisor: Advisor, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    advisor_can_see(db, advisor.advisor_id, student_id)
    return student


def free_slots(db: Session, advisor: Advisor, day: date, student_id: int, meeting_id: int | None = None) -> dict:
    """The advisor's open slots on `day` that the student can take too (spec 18 rules: the student's classes and
    meetings, office hours and the 12-hour lead time). `meeting_id` is a meeting being moved."""
    student = _advisee(db, advisor, student_id)
    week = day - timedelta(days=day.weekday())
    if day.weekday() >= 5:
        return {"slots": []}
    staff = db.get(User, advisor.user_id)
    check_week(week, booking_weeks(db, staff))
    slots = []
    for slot_day, day_slots in _week_slots(db, student, staff, week, ignore_id=meeting_id):
        if slot_day == day:
            slots = [{"startsAt": iso_z(start), "time": _local(start).strftime("%H:%M")}
                     for start, taken, _ in day_slots if not taken]
    return {"slots": slots}


def book_for_student(db: Session, advisor: Advisor, data: dict) -> dict:
    """Books a confirmed meeting with an advisee in one of the advisor's open slots and tells the student."""
    student = _advisee(db, advisor, data["student_id"])
    staff = db.get(User, advisor.user_id)
    lock_staff(db, staff)
    start = data["starts_at"].astimezone(timezone.utc)
    local_day = _local(start).date()
    check_week(local_day - timedelta(days=local_day.weekday()), booking_weeks(db, staff))
    slot = slot_at(db, student, staff, start)
    if slot is None:
        raise bad_request("Pick one of your open times.")
    taken, window = slot
    if taken:
        raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)

    format_ = FORMATS[data["format"]]
    meeting = Meeting(student_id=student.student_id, advisor_id=advisor.advisor_id, staff_user_id=staff.user_id,
                      starts_at=start, ends_at=start + meeting_length(db, staff), format=format_,
                      location=window.location if format_ == "in_person" else None, topic=data["topic"],
                      note=data.get("note"), status="confirmed")
    db.add(meeting)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "SLOT_TAKEN", SLOT_TAKEN)
    if format_ == "online":
        meeting.video_url = VIDEO_URL.format(id=meeting.id)
    place = "online" if format_ == "online" else (meeting.location or "in person")
    when = local_when(start)
    messages.notify(db, student.user_id, f"{staff.name} booked a meeting with you: {meeting.topic} on {when} ({place}).")
    audit.record(db, staff, "meeting.book", f"{staff.name} booked {meeting.topic} with {student.name} on {when}",
                 target=("meeting", meeting.id))
    db.flush()
    return _meeting_row(meeting, student)


def save_notes(db: Session, advisor: Advisor, meeting_id: int, notes: str | None) -> dict:
    """The advisor's private notes on one of their meetings; the audit row never holds the text. The caller commits."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None or meeting.staff_user_id != advisor.user_id:
        raise not_found("Meeting")
    meeting.advisor_notes = notes or None
    actor = db.get(User, advisor.user_id)
    student = db.get(Student, meeting.student_id)
    audit.record(db, actor, "meeting.notes", f"Updated notes for {meeting.topic} with {student.name}",
                 target=("meeting", meeting.id))
    db.flush()
    return _meeting_row(meeting, student)
