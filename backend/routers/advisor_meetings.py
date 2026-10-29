"""/advisor/meetings and /advisor/office-hours (spec 24). Decisions on a meeting use spec 18's
POST /meetings/{id}/{action}."""
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_current_advisor
from database import get_db
from models import Advisor
from schemas.advisor_meetings import (AdvisorBookIn, AdvisorMeetingsOut, AgendaRowOut, FreeSlotsOut, NotesIn,
                                      OfficeHoursIn, OfficeHoursWrapOut)
from services import advisor_meetings

router = APIRouter(prefix="/api/v1/advisor", tags=["Advisor"])


@router.get("/meetings", response_model=AdvisorMeetingsOut)
def get_meetings(range: Literal["today", "week"] = "today", advisor: Advisor = Depends(get_current_advisor),
                 db: Session = Depends(get_db)):
    return advisor_meetings.page(db, advisor, range)


@router.get("/meetings/free-slots", response_model=FreeSlotsOut)
def free_slots(date: dt.date, student_id: int = Query(alias="studentId"),
               meeting_id: int | None = Query(None, alias="meetingId"),
               advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    return advisor_meetings.free_slots(db, advisor, date, student_id, meeting_id)


@router.post("/meetings", response_model=AgendaRowOut, status_code=201)
def book(body: AdvisorBookIn, advisor: Advisor = Depends(get_current_advisor), db: Session = Depends(get_db)):
    row = advisor_meetings.book_for_student(db, advisor, body.model_dump())
    db.commit()
    return row


@router.patch("/meetings/{meeting_id}", response_model=AgendaRowOut)
def save_notes(meeting_id: int, body: NotesIn, advisor: Advisor = Depends(get_current_advisor),
               db: Session = Depends(get_db)):
    row = advisor_meetings.save_notes(db, advisor, meeting_id, body.notes)
    db.commit()
    return row


@router.put("/office-hours", response_model=OfficeHoursWrapOut)
def set_office_hours(body: OfficeHoursIn, advisor: Advisor = Depends(get_current_advisor),
                     db: Session = Depends(get_db)):
    hours = advisor_meetings.set_office_hours(db, advisor, body.days, dt.time.fromisoformat(body.start),
                                              dt.time.fromisoformat(body.end), body.location)
    db.commit()
    return {"officeHours": hours}
