"""Read-only feedback from the latest decision that still applies to current plan items."""

def returned_feedback(db,student,term_id):
    from models import ApprovalRequest,PlanItem
    current={item.id for item in db.query(PlanItem).filter(PlanItem.student_id==student.student_id,PlanItem.term_id==term_id,PlanItem.status=="changes_requested")}
    if not current:return None
    requests=db.query(ApprovalRequest).filter(ApprovalRequest.student_id==student.student_id,ApprovalRequest.term_id==term_id,ApprovalRequest.type=="plan").order_by(ApprovalRequest.created_at.desc(),ApprovalRequest.id.desc())
    # Only the newest request touching these items owns their current decision.
    for request in requests:
        if current.intersection((request.payload or {}).get("planItemIds") or []):
            return request.comment if request.status=="changes_requested" else None
    return None


def has_returned_plan(db,student):
    from core.time import today
    from models import PlanItem,Term
    return db.query(PlanItem.id).join(Term,PlanItem.term_id==Term.id).filter(PlanItem.student_id==student.student_id,PlanItem.status=="changes_requested",Term.end_date>=today()).first() is not None
