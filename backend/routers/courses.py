from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import User
from schemas.courses import GradesOut
from services.courses import grades_for

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


@router.get("/{course_id}/grades", response_model=GradesOut)
def course_grades(course_id: int, student_id: int | None = Query(None, alias="studentId"),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return grades_for(db, user, course_id, student_id)
