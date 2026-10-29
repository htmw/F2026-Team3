from sqlalchemy.orm import Session

from models import Advisor, Student, User
from services import advisees, approvals
from services.assignments import due_soon_count
from services.messages import unread_count


def badges_for(db: Session, user: User) -> dict[str, int]:
    """Sidebar counts per role. Each count is filled in by its owner feature: assignments due within a week (spec 15),
    unread messages (16), advisees with risk High or Medium (21) and pending approval requests (23)."""
    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user.user_id).one_or_none()
        return {"assignments": due_soon_count(db, student) if student else 0, "messages": unread_count(db, user)}
    if user.role == "advisor":
        advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one_or_none()
        if advisor is None:
            return {"advisees": 0, "approvals": 0, "messages": unread_count(db, user)}
        return {"advisees": advisees.attention_count(db, advisor), "approvals": approvals.pending_count(db, advisor),
                "messages": unread_count(db, user)}
    return {}
