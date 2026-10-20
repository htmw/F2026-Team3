"""Degree plan (spec 12): GET /students/me/degree-audit and /students/me/plan, plan changes and submit."""
from typing import Literal

from pydantic import Field

from schemas.base import ApiModel


class StatOut(ApiModel):
    label: str
    value: str
    pct: int | None
    warn: bool
    color: str | None
    note: str


class GroupItemOut(ApiModel):
    code: str
    name: str
    status: str
    meta: str | None


class GroupOut(ApiModel):
    id: int
    title: str
    required: int
    count: str
    all_done: bool
    items: list[GroupItemOut]


class GraduationOut(ApiModel):
    label: str
    status: str


class AuditOut(ApiModel):
    subtitle: str
    requirements_subtitle: str
    graduation: GraduationOut
    stats: list[StatOut]
    groups: list[GroupOut]
    alert: str | None


class PlanCourseOut(ApiModel):
    enrollment_id: int  # enrollment id for completed/current rows, plan_items.id for planned rows
    code: str
    name: str
    status: Literal["completed", "current", "planned"]
    plan_status: str | None


class TermOut(ApiModel):
    name: str
    tag: Literal["Done", "Current", "Planned"]
    credits: str
    courses: list[PlanCourseOut]


class AvailableCourseOut(ApiModel):
    code: str
    name: str
    type: str
    offered: bool


class FutureTermOut(ApiModel):
    id: int
    name: str


class PlanOut(ApiModel):
    terms: list[TermOut]
    available: list[AvailableCourseOut]
    future_terms: list[FutureTermOut]
    notice: str | None


class PlanAddIn(ApiModel):
    course_code: str = Field(min_length=1, max_length=100)
    term_id: int
    note: str | None = Field(None, max_length=500)


class PlanAddOut(ApiModel):
    enrollment_id: int
    code: str
    name: str
    term: str
    plan_status: str


class PlanSubmitIn(ApiModel):
    term_id: int


class CheckOut(ApiModel):
    ok: bool
    blocking: bool
    text: str


class PrecheckOut(ApiModel):
    ok: bool
    text: str
    checks: list[CheckOut]


class SubmitOut(ApiModel):
    precheck: PrecheckOut
    request_id: int
