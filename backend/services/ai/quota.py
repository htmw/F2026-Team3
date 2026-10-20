"""Daily question limit: questions count from local midnight (core.time.local_midnight)."""
from sqlalchemy.orm import Session

from core.time import local_midnight
from models import AiMessage, AiThread, Student


def asked_today(db: Session, student: Student) -> int:
    return (db.query(AiMessage).join(AiThread, AiMessage.thread_id == AiThread.id)
            .filter(AiThread.student_id == student.student_id, AiMessage.role == "user",
                    AiMessage.created_at >= local_midnight())
            .count())


def remaining_today(db: Session, student: Student, limit: int) -> int:
    return max(0, limit - asked_today(db, student))
