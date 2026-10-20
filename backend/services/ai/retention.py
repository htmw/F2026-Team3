"""AI conversation retention (spec 37 "Keep AI conversations for"). Run through scripts/prune.py."""
import calendar
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from core.time import MONTH_NAMES, local_zone, today
from models import AiThread, Student
from services import settings

KEEP = {"30 days": timedelta(days=30), "1 year": timedelta(days=365)}
GRACE = timedelta(days=30)  # "Until graduation" keeps threads for 30 days after graduation
FULL_MONTHS = tuple(calendar.month_name)[1:]


def graduation_date(label: str | None) -> date | None:
    """"May 2027" or "December 2026" -> the last day of that month; None when it can't be read."""
    parts = (label or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    name = parts[0][:3].title()
    if name not in MONTH_NAMES:
        return None
    month, year = MONTH_NAMES.index(name) + 1, int(parts[1])
    return date(year, month, calendar.monthrange(year, month)[1])


def prune_threads(db: Session, day: date | None = None) -> int:
    """Deletes AI threads (their messages cascade; flags keep a null message) past the retention; returns how many."""
    day = day or today()
    rule = settings.get(db, "retention")["ai"]
    query = db.query(AiThread)
    if rule in KEEP:
        cutoff = datetime.combine(day, datetime.min.time(), local_zone()) - KEEP[rule]
        query = query.filter(AiThread.updated_at < cutoff)
    else:  # Until graduation
        graduated = [student_id for student_id, label in db.query(Student.student_id, Student.expected_graduation)
                     if (when := graduation_date(label)) is not None and when + GRACE < day]
        if not graduated:
            return 0
        query = query.filter(AiThread.student_id.in_(graduated))
    count = query.delete(synchronize_session=False)
    db.commit()
    return count
