from sqlalchemy.orm import Session

from models import Advisor, ApprovalRequest, Student, User
from services.assignments import due_soon_count
from services.messages import unread_count


def badges_for(db: Session, user: User) -> dict[str, int]:
    """Sidebar counts per role. Each count is filled in by its owner feature: assignments due within a week (spec 15),
    unread messages (16), advisees needing attention (21). Pending approvals come from approval_requests (spec 12; spec 23 owns the queue).
    The others are 0 until their features land."""
    if user.role == "student":
        student = db.query(Student).filter(Student.user_id == user.user_id).one_or_none()
        return {"assignments": due_soon_count(db, student) if student else 0, "messages": unread_count(db, user)}
    if user.role == "advisor":
        advisor = db.query(Advisor).filter(Advisor.user_id == user.user_id).one_or_none()
        approvals = 0
        if advisor is not None:
            approvals = db.query(ApprovalRequest).filter(ApprovalRequest.advisor_id == advisor.advisor_id,
                                                         ApprovalRequest.status == "pending").count()
        return {"advisees": 0, "approvals": approvals, "messages": unread_count(db, user)}
    return {}
