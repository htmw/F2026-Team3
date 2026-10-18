from typing import Literal

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from core.deps import get_current_student, get_current_user
from database import get_db
from models import Student, User
from schemas.meetings import ActionIn, BookIn, BookOut, MeetingRowOut
from services import meetings
from services.audit import request_ip

router = APIRouter(prefix="/api/v1/meetings", tags=["Meetings"])

Action = Literal["cancel", "accept", "decline", "propose", "complete", "no-show"]


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def book_meeting(body: BookIn, request: Request, student: Student = Depends(get_current_student),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return meetings.book(db, student, user, body.model_dump(), ip=request_ip(request))


@router.post("/{meeting_id}/{action}", response_model=MeetingRowOut)
def change_meeting(meeting_id: int, action: Action, request: Request, body: ActionIn | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump() if body else {}
    return meetings.act(db, user, meeting_id, action, data, ip=request_ip(request))
