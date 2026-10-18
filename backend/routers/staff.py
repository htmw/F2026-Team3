from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_current_student
from database import get_db
from models import Student
from schemas.meetings import AvailabilityOut, StaffListOut
from services import meetings

router = APIRouter(prefix="/api/v1/staff", tags=["Meetings"])


# Spec 18 serves the student's booking view; spec 24 opens these to advisors.
@router.get("", response_model=StaffListOut)
def list_staff(bookable: bool = True, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return meetings.bookable_staff(db, student)


@router.get("/{staff_id}/availability", response_model=AvailabilityOut)
def get_availability(staff_id: int, week: date = Query(...), student: Student = Depends(get_current_student),
                     db: Session = Depends(get_db)):
    return meetings.availability(db, student, staff_id, week)
