from typing import Literal
from pydantic import BaseModel, Field


class StudentSummary(BaseModel):
    student_id: int = Field(gt=0)
    name: str
    email: str
    program_id: int = Field(gt=0)
    program_name: str
    gpa: float | None = Field(ge=0, le=4)
    completed_credits: float = Field(ge=0)
    total_required_credits: float = Field(gt=0)


class Enrollment(BaseModel):
    enrollment_id: int = Field(gt=0)
    course_id: int = Field(gt=0)
    course_code: str
    course_name: str
    term: str
    credits: float = Field(ge=0)
    status: Literal[
        "in_progress",
        "completed",
        "failed",
        "withdrawn"
    ]
    grade: str | None
    grade_points: float | None = Field(ge=0, le=4)


class AcademicProfileResponse(BaseModel):
    student: StudentSummary
    enrollments: list[Enrollment]
