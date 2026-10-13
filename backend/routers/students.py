from fastapi import APIRouter
from fastapi.responses import JSONResponse

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
def get_academic_profile(student_id: int):
    profile = get_student_profile(student_id)

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
