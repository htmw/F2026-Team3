"""Day-before meeting reminders (spec 18). Run by scripts/send_reminders.py (a daily cron job later)."""
from datetime import time, timedelta

from sqlalchemy.orm import Session

from core.time import now, today
from models import Meeting, Student, User
from services import messages
from services.meetings import _at, _hhmm


def send_due_reminders(db: Session) -> int:
    """Notifies both sides of every confirmed meeting tomorrow (school time) that hasn't been reminded yet.
    Returns how many meetings were reminded."""
    tomorrow = today() + timedelta(days=1)
    rows = (db.query(Meeting)
            .filter(Meeting.status == "confirmed", Meeting.reminded_at.is_(None),
                    Meeting.starts_at >= _at(tomorrow, time(0)), Meeting.starts_at < _at(tomorrow + timedelta(days=1), time(0)))
            .order_by(Meeting.starts_at).all())
    for meeting in rows:
        staff = db.get(User, meeting.staff_user_id)
        student = db.get(Student, meeting.student_id)
        at = _hhmm(meeting.starts_at)
        messages.notify(db, student.user_id, f"Reminder: {meeting.topic} with {staff.name} tomorrow at {at}.")
        messages.notify(db, staff.user_id, f"Reminder: {meeting.topic} with {student.name} tomorrow at {at}.")
        meeting.reminded_at = now()
    db.commit()
    return len(rows)
