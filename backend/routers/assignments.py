from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.deps import get_current_student, get_current_user
from database import get_db
from models import Student, User
from schemas.assignments import ProgressIn, ProgressOut, SubmitIn, SubmitOut
from services import assignments

router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])


@router.patch("/{assignment_id}/progress", response_model=ProgressOut)
def update_progress(assignment_id: int, body: ProgressIn, student: Student = Depends(get_current_student),
                    db: Session = Depends(get_db)):
    return assignments.update_progress(db, student, assignment_id, body.steps_done, body.status)


@router.post("/{assignment_id}/submit", response_model=SubmitOut)
def submit(assignment_id: int, body: SubmitIn | None = None, student: Student = Depends(get_current_student),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return assignments.submit(db, student, user, assignment_id, body.fields if body else None)
