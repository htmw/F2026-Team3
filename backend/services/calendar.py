"""Student schedule (spec 14): the week calendar (personal events, class meetings and office hours from sections,
the advisor's office hours (spec 24), booked meetings from services/meetings.py), deadlines, a study-block suggestion, personal event changes, and .ics calendar feeds.
Also the source of the dashboard's "Today" list (events_for_day)."""
import base64
import hashlib
import hmac
import logging
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from core.config import settings
from core.errors import ApiError, forbidden, not_found
from core.security import sha256_hex
from core.time import DAY_NAMES, local_zone, now, short_date, today
from models import Advisor, AdvisorAvailability, AdvisorStudentAssignment, CalendarFeed, Event, Student, Term, User
from services import assignments
from services.ai import settings as ai_config
from services.courses import current_enrollments, meeting_days

log = logging.getLogger(__name__)

MAX_RANGE_DAYS = 42
DEADLINE_WINDOW_DAYS = 14
SUGGEST_WITHIN_DAYS = 10
EVENING = (time(17, 0), time(22, 0))
STUDY_BLOCK = timedelta(hours=2)
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
FEED_DAYS = 120
DEV_FEED_SECRET = "acadmate-dev-calendar-secret"  # used only when SECRET_KEY is unset


def _validation(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.", [{"field": field, "message": message}])


def _hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def _dates(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def parse_range(from_: date | None, to: date | None) -> tuple[date, date]:
    """Both or neither; neither = the current Mon-Sun. At most 42 days."""
    if from_ is None and to is None:
        monday = today() - timedelta(days=today().weekday())
        return monday, monday + timedelta(days=6)
    if from_ is None or to is None:
        raise _validation("from" if from_ is None else "to", "Send both from and to, or neither.")
    if to < from_:
        raise _validation("to", "The end date must be on or after the start date.")
    if (to - from_).days > MAX_RANGE_DAYS:
        raise _validation("to", f"Choose a range of at most {MAX_RANGE_DAYS} days.")
    return from_, to


# --- event sources ------------------------------------------------------------------------------------------

def event_out(event: Event) -> dict:
    return {"id": f"ev-{event.id}", "kind": "personal", "title": event.title, "type": event.type,
            "date": event.date.isoformat(), "start": _hhmm(event.start_time), "end": _hhmm(event.end_time),
            "location": event.location, "note": event.note, "editable": True, "status": None,
            "reminder_minutes": event.reminder_minutes}


def personal_events(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    rows = (db.query(Event).filter(Event.student_id == student.student_id, Event.date >= from_, Event.date <= to)
            .order_by(Event.date, Event.start_time, Event.id))
    return [event_out(row) for row in rows]


def _section_days(db: Session, section, from_: date, to: date, weekdays: list[str]):
    """Dates in [from_, to] on the given weekdays that fall inside the section's term."""
    term = db.get(Term, section.term_id)
    if term is None:
        return
    for day in _dates(max(from_, term.start_date), min(to, term.end_date)):
        if DAY_NAMES[day.weekday()] in weekdays:
            yield day


def class_events(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    events = []
    for entry in current_enrollments(db, student):
        section, course = entry.section, entry.course
        if section is None or section.start_time is None or section.end_time is None:
            continue
        for day in _section_days(db, section, from_, to, meeting_days(section)):
            events.append({"id": f"cls-{section.id}-{day.isoformat()}", "kind": "class",
                           "title": f"{course.course_code} {course.course_name}", "type": "Class",
                           "date": day.isoformat(), "start": _hhmm(section.start_time), "end": _hhmm(section.end_time),
                           "location": f"Room {section.room}" if section.room else None, "note": None,
                           "editable": False, "status": None, "reminder_minutes": None,
                           "code": course.course_code, "course_name": course.course_name})
    return events


def office_events(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    events = []
    for entry in current_enrollments(db, student):
        section, code = entry.section, entry.course.course_code
        if section is None or not (section.office_day and section.office_start and section.office_end):
            continue
        for day in _section_days(db, section, from_, to, [section.office_day]):
            events.append({"id": f"off-{section.id}-{day.isoformat()}", "kind": "office",
                           "title": f"{code} office hours", "type": "Office hours", "date": day.isoformat(),
                           "start": _hhmm(section.office_start), "end": _hhmm(section.office_end),
                           "location": section.instructor_name, "note": None, "editable": False, "status": None,
                           "reminder_minutes": None, "code": code})
    return events


def advisor_office_events(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    """The assigned advisor's drop-in office hours (spec 24 publishes them; ids aoh-{window}-{date})."""
    rows = (db.query(AdvisorAvailability, User)
            .join(Advisor, Advisor.user_id == AdvisorAvailability.staff_user_id)
            .join(AdvisorStudentAssignment, AdvisorStudentAssignment.advisor_id == Advisor.advisor_id)
            .join(User, User.user_id == Advisor.user_id)
            .filter(AdvisorStudentAssignment.student_id == student.student_id,
                    AdvisorAvailability.kind == "office_hours").all())
    events = []
    day = from_
    while day <= to:
        for window, advisor in rows:
            if window.weekday == day.weekday():
                place = " · ".join(part for part in (window.location, advisor.name) if part)
                events.append({"id": f"aoh-{window.id}-{day.isoformat()}", "kind": "office",
                               "title": "Advisor office hours", "type": "Office hours", "date": day.isoformat(),
                               "start": _hhmm(window.start_time), "end": _hhmm(window.end_time), "location": place,
                               "note": None, "editable": False, "status": None, "reminder_minutes": None})
        day += timedelta(days=1)
    return events


def meeting_events(db: Session, student: Student, from_: date, to: date) -> list[dict]:
    """Requested / confirmed / proposed meetings (spec 18; ids mtg-…)."""
    from services import meetings  # imported here: meetings uses class_events from this module
    return meetings.events_for_student(db, student, from_, to)


def _all_events(db: Session, student: Student, from_: date, to: date, office: bool = True) -> list[dict]:
    events = personal_events(db, student, from_, to) + class_events(db, student, from_, to)
    events += meeting_events(db, student, from_, to)
    if office:
        events += office_events(db, student, from_, to) + advisor_office_events(db, student, from_, to)
    return sorted(events, key=lambda event: (event["date"], event["start"], event["end"], event["id"]))


# --- deadlines and suggestion -------------------------------------------------------------------------------

def deadlines(db: Session, student: Student, start: date, end: date) -> list[dict]:
    """Open assignments due in [start, end] (spec 15)."""
    return assignments.deadlines(db, student, start, end)


def _minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _free_evening_block(events: list[dict]) -> tuple[int, int] | None:
    """The first 2-hour block between 17:00 and 22:00 that no event overlaps, in minutes."""
    window_start, window_end = EVENING[0].hour * 60, EVENING[1].hour * 60
    need = int(STUDY_BLOCK.total_seconds() // 60)
    cursor = window_start
    for start, end in sorted((_minutes(e["start"]), _minutes(e["end"])) for e in events):
        if end <= cursor:
            continue
        if start - cursor >= need:
            break
        cursor = max(cursor, end)
        if cursor >= window_end:
            return None
    return (cursor, cursor + need) if window_end - cursor >= need else None


def study_suggestion(db: Session, student: Student, from_: date, to: date, events: list[dict]) -> dict | None:
    if not ai_config.ai_settings(db)["features"]["proactiveTips"]:
        return None
    day0 = today()
    for deadline in deadlines(db, student, day0, day0 + timedelta(days=SUGGEST_WITHIN_DAYS)):
        due = date.fromisoformat(deadline["date"])
        code = deadline["course"]
        planned = (db.query(Event).filter(Event.student_id == student.student_id, Event.type == "Study",
                                          Event.date >= day0, Event.date < due, Event.title.contains(code)).count())
        if planned:
            continue  # the student already set time aside for this course before the deadline
        for day in _dates(max(day0, from_), min(to, due - timedelta(days=1))):
            block = _free_evening_block([e for e in events if e["date"] == day.isoformat()])
            if block is None:
                continue
            sessions = sum(1 for e in events if e["kind"] == "personal" and e["type"] == "Study" and code in e["title"]) + 1
            start, end = block
            return {
                "title": f"Study · {code} {deadline['title']}"[:80],
                "text": (f"You have a free 2-hour window on {WEEKDAY_NAMES[day.weekday()]} evening. Blocking it for "
                         f"{deadline['title']} gives you {sessions} sessions before the {deadline['label']} deadline."),
                "date": day.isoformat(),
                "start": f"{start // 60:02d}:{start % 60:02d}",
                "end": f"{end // 60:02d}:{end % 60:02d}",
            }
    return None


def week(db: Session, student: Student, from_: date | None, to: date | None) -> dict:
    from_, to = parse_range(from_, to)
    events = _all_events(db, student, from_, to)
    due = {}
    for deadline in deadlines(db, student, from_, to):
        due.setdefault(deadline["date"], []).append(f"{deadline['course']} {deadline['title']}")
    days = [{"date": day.isoformat(), "name": DAY_NAMES[day.weekday()], "day": day.day,
             "due": due.get(day.isoformat(), []),
             "events": [event for event in events if event["date"] == day.isoformat()]}
            for day in _dates(from_, to)]
    return {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "today": today().isoformat(),
        "days": days,
        "deadlines": deadlines(db, student, today(), today() + timedelta(days=DEADLINE_WINDOW_DAYS)),
        "suggestion": study_suggestion(db, student, from_, to, events),
    }


def _duration(start: str, end: str) -> str:
    minutes = _minutes(end) - _minutes(start)
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{minutes} min" if minutes < 60 else f"{minutes / 60:g} h"


def events_for_day(db: Session, student: Student, day: date) -> list[dict]:
    """The dashboard's "Today" rows: classes, personal events and meetings (office hours are left out)."""
    rows = []
    for event in _all_events(db, student, day, day, office=False):
        if event["kind"] == "class":
            title, meta = f"{event['course_name']} ({event['code']})", event["location"] or ""
        else:
            title = event["title"]
            meta = " · ".join(part for part in (event["location"], _duration(event["start"], event["end"])) if part)
        rows.append({"id": event["id"], "time": event["start"], "title": title, "meta": meta, "type": event["type"]})
    return rows


# --- personal event changes ---------------------------------------------------------------------------------

def _own_event(db: Session, student: Student, raw_id: str) -> Event:
    match = re.fullmatch(r"ev-(\d+)", raw_id or "")
    if match is None:
        if re.match(r"(cls|off|mtg)-", raw_id or ""):
            raise forbidden("This event can't be changed here.")
        raise not_found("Event")
    event = db.query(Event).filter(Event.id == int(match.group(1)), Event.student_id == student.student_id).one_or_none()
    if event is None:
        raise not_found("Event")
    return event


def _check(event: Event) -> None:
    if event.type == "Class":
        raise _validation("type", "Classes come from your enrollments.")
    if event.end_time <= event.start_time:
        raise _validation("end", "End time must be after the start time.")


FIELD_COLUMNS = {"title": "title", "type": "type", "date": "date", "start": "start_time", "end": "end_time",
                 "location": "location", "note": "note", "reminder_minutes": "reminder_minutes"}


def create_event(db: Session, student: Student, data: dict) -> dict:
    event = Event(student_id=student.student_id, **{FIELD_COLUMNS[key]: value for key, value in data.items()})
    _check(event)
    db.add(event)
    db.commit()
    return event_out(event)


def update_event(db: Session, student: Student, raw_id: str, changes: dict) -> dict:
    event = _own_event(db, student, raw_id)
    for key, value in changes.items():
        setattr(event, FIELD_COLUMNS[key], value)
    _check(event)
    db.commit()
    return event_out(event)


def delete_event(db: Session, student: Student, raw_id: str) -> None:
    db.delete(_own_event(db, student, raw_id))
    db.commit()


# --- .ics feed ------------------------------------------------------------------------------------------------

def _ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """RFC 5545 line folding: at most 75 octets per line, continuation lines start with a space."""
    out, current = [], ""
    for char in line:
        limit = 75 if not out else 74
        if len((current + char).encode("utf-8")) > limit:
            out.append(current)
            current = char
        else:
            current += char
    out.append(current)
    return [out[0]] + [" " + part for part in out[1:]]


def _utc(day: str, clock: str) -> str:
    local = datetime.combine(date.fromisoformat(day), time.fromisoformat(clock), tzinfo=local_zone())
    return local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics(db: Session, student: Student, days: int = FEED_DAYS) -> str:
    stamp = now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Acadmate//Schedule//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Acadmate"]
    for event in _all_events(db, student, today(), today() + timedelta(days=days)):
        lines += ["BEGIN:VEVENT", f"UID:{event['id']}@acadmate", f"DTSTAMP:{stamp}",
                  f"DTSTART:{_utc(event['date'], event['start'])}", f"DTEND:{_utc(event['date'], event['end'])}",
                  f"SUMMARY:{_ics_text(event['title'])}", f"CATEGORIES:{_ics_text(event['type'])}"]
        if event["location"]:
            lines.append(f"LOCATION:{_ics_text(event['location'])}")
        if event["note"]:
            lines.append(f"DESCRIPTION:{_ics_text(event['note'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(f"{part}\r\n" for line in lines for part in _fold(line))


def _feed_token(student_id: int, version: int) -> str:
    secret = settings.SECRET_KEY
    if not secret:
        log.warning("SECRET_KEY is not set; calendar feed links use a development-only secret.")
        secret = DEV_FEED_SECRET
    digest = hmac.new(secret.encode(), f"calendar:{student_id}:{version}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def feed_url(db: Session, student: Student, base_url: str, rotate: bool = False) -> str:
    """The student's feed link, created on first use. rotate=True invalidates the previous link."""
    feed = db.get(CalendarFeed, student.student_id)
    if feed is None:
        feed = CalendarFeed(student_id=student.student_id, version=1, token_hash="")
        db.add(feed)
    elif rotate:
        feed.version += 1
    token = _feed_token(student.student_id, feed.version)
    if feed.token_hash != sha256_hex(token):  # also heals the stored hash if SECRET_KEY changed
        feed.token_hash = sha256_hex(token)
        db.commit()
    base = (settings.PUBLIC_API_URL or base_url).rstrip("/")
    return f"{base}/api/v1/calendar/{token}.ics"


def student_for_token(db: Session, token: str) -> Student:
    feed = db.query(CalendarFeed).filter(CalendarFeed.token_hash == sha256_hex(token)).one_or_none()
    student = db.get(Student, feed.student_id) if feed else None
    if student is None:
        raise not_found("Calendar")
    return student
