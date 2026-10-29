"""/advisor/approvals (spec 23): the advisor's queue and its decisions. Only the caller's requests; others are 404."""
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from core.deps import get_current_advisor
from database import get_db
from models import Advisor
from schemas.approvals import ApprovalRowOut, ApprovalsOut, ChangesIn, DecisionIn, StatusLabel
from services import approvals

router = APIRouter(prefix="/api/v1/advisor/approvals", tags=["Advisor"])


@router.get("", response_model=ApprovalsOut)
def list_approvals(status: StatusLabel = "Pending", advisor: Advisor = Depends(get_current_advisor),
                   db: Session = Depends(get_db)):
    return approvals.list_for(db, advisor, status)


@router.get("/{request_id}", response_model=ApprovalRowOut)
def get_approval(request_id: int, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return approvals.get(db, advisor, request_id)


@router.post("/{request_id}/approve", response_model=ApprovalRowOut)
def approve(request_id: int, body: DecisionIn | None = Body(None), advisor: Advisor = Depends(get_current_advisor),
            db: Session = Depends(get_db)):
    request = approvals.approve(db, advisor, request_id, body.comment if body else None)
    db.commit()
    return approvals.row(db, advisor, request)


@router.post("/{request_id}/request-changes", response_model=ApprovalRowOut)
def request_changes(request_id: int, body: ChangesIn, advisor: Advisor = Depends(get_current_advisor),
                    db: Session = Depends(get_db)):
    request = approvals.request_changes(db, advisor, request_id, body.comment)
    db.commit()
    return approvals.row(db, advisor, request)


@router.post("/{request_id}/reopen", response_model=ApprovalRowOut)
def reopen(request_id: int, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    request = approvals.reopen(db, advisor, request_id)
    db.commit()
    return approvals.row(db, advisor, request)
