from fastapi import APIRouter, Depends 
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from schemas.students import AcademicProfileResponse
from services.students import get_student_profile


router = APIRouter(
    prefix="/api/v1/students",
    tags=["Students"]
)


@router.get(
    "/{student_id}/academic-profile",
    response_model=AcademicProfileResponse
)
def get_academic_profile(student_id: int, db: Session = Depends(get_db)):
    profile = get_student_profile(student_id, db)

    if profile is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Student not found.",
                    "details": []
                }
            }
        )

    return profile
