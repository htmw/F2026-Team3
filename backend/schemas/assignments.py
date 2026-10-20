"""Assignments (spec 15): GET /students/me/assignments, progress and submit."""
from typing import Literal

from pydantic import Field

from schemas.base import ApiModel
from schemas.plan import PrecheckOut

AssignmentStatus = Literal["To do", "In progress", "Submitted", "Graded"]


class StepOut(ApiModel):
    text: str
    done: bool


class AssignmentRowOut(ApiModel):
    id: int
    title: str
    course: str
    due: str
    due_date: str
    status: AssignmentStatus
    deadline: Literal["Overdue", "Due soon", "In progress", "Not started", "Done"]
    score: str
    weight: str
    type: Literal["Individual", "Team", "Form"]
    desc: str | None
    submission_url: str | None
    steps: list[StepOut]


class StatOut(ApiModel):
    label: str
    value: str
    note: str


class TabOut(ApiModel):
    label: str
    count: int


class CourseOptionOut(ApiModel):
    value: str
    label: str


class AssignmentsOut(ApiModel):
    subtitle: str
    stats: list[StatOut]
    tabs: list[TabOut]
    courses: list[CourseOptionOut]
    rows: list[AssignmentRowOut]


class ProgressIn(ApiModel):
    steps_done: list[int] | None = Field(None, max_length=50)
    status: Literal["In progress"] | None = None


class ProgressOut(ApiModel):
    status: AssignmentStatus
    steps_done: list[int]


class SubmitIn(ApiModel):
    fields: dict[str, str] | None = None  # advising forms: {"Proposed topic", "Project summary"}


class SubmitOut(ApiModel):
    status: AssignmentStatus
    submitted_at: str
    precheck: PrecheckOut | None
