from datetime import date, datetime
from typing import Literal

from pydantic import Field

from schemas.base import ApiModel


InterventionStatus = Literal["open", "in_progress", "done"]


class InterventionCreateIn(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None


class InterventionPatchIn(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    status: InterventionStatus | None = None


class InterventionOut(ApiModel):
    id: int
    student_id: int
    advisor_id: int | None
    title: str
    description: str | None
    due_date: date | None
    status: InterventionStatus
    created_at: datetime
    updated_at: datetime


class InterventionsOut(ApiModel):
    interventions: list[InterventionOut]