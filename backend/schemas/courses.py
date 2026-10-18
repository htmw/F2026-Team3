"""GET /students/me/courses and GET /courses/{courseId}/grades (spec 11)."""
from typing import Literal

from schemas.base import ApiModel


class UpcomingOut(ApiModel):
    date: str
    mon: str
    day: str
    title: str
    meta: str


class CourseCardOut(ApiModel):
    course_id: int
    enrollment_id: int
    code: str
    name: str
    credits: str
    prof: str
    when: str
    room: str
    office: str | None
    site_url: str | None
    pct: int
    grade: str
    tone: str
    next: str | None
    insight: str | None
    upcoming: list[UpcomingOut]


class WeekItemOut(ApiModel):
    time: str
    code: str
    room: str
    tone: str
    kind: Literal["class", "office"]


class WeekDayOut(ApiModel):
    day: str
    items: list[WeekItemOut]


class CompletedOut(ApiModel):
    course_id: int
    code: str
    name: str
    term: str
    credits: float
    grade: str


class CompletedSummaryOut(ApiModel):
    credits: float
    gpa: float | None


class PlannedOut(ApiModel):
    enrollment_id: int  # spec 12 plan_items.id
    course_id: int
    code: str
    name: str
    term: str
    credits: float
    status: str
    fulfills: str | None
    why: str | None


class CountsOut(ApiModel):
    current: int
    completed: int
    planned: int


class MyCoursesOut(ApiModel):
    subtitle: str
    add_drop_url: str | None
    counts: CountsOut
    current: list[CourseCardOut]
    week: list[WeekDayOut]
    completed: list[CompletedOut]
    completed_summary: CompletedSummaryOut
    planned_notice: str | None
    planned: list[PlannedOut]


class GradePartOut(ApiModel):
    label: str
    weight: float
    score: float | None
    display: str


class GradesOut(ApiModel):
    parts: list[GradePartOut]
    weighted_score: float | None
    letter: str | None
