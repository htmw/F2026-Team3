"""GET /students/me/dashboard (spec 10)."""
from schemas.base import ApiModel


class DashboardStudent(ApiModel):
    first_name: str
    initials: str
    term_label: str


class GpaPoint(ApiModel):
    term: str
    gpa: float
    current: bool = False


class GpaSummary(ApiModel):
    cumulative: float | None
    change: float | None
    status: str
    trend: list[GpaPoint]


class Stat(ApiModel):
    key: str
    label: str
    value: str
    pill: str
    tone: str
    pct: int | None
    warn: bool
    note: str


class Recommendation(ApiModel):
    title: str
    text: str


class RequirementRow(ApiModel):
    label: str
    count: str
    pct: int
    warn: bool


class StudyDay(ApiModel):
    day: str
    hours: float
    today: bool


class StudyHours(ApiModel):
    total: float
    goal: float
    days: list[StudyDay]


class TodayEvent(ApiModel):
    id: str
    time: str
    title: str
    meta: str
    type: str


class Today(ApiModel):
    label: str
    events: list[TodayEvent]


class Task(ApiModel):
    id: int
    title: str
    course: str
    due: str
    status: str


class CurrentCourse(ApiModel):
    code: str
    name: str
    prof: str
    pct: int
    grade: str
    tone: str


class DashboardOut(ApiModel):
    student: DashboardStudent
    gpa: GpaSummary
    stats: list[Stat]
    recommendation: Recommendation | None
    requirements: list[RequirementRow]
    alert: str | None
    study_hours: StudyHours
    today: Today
    tasks: list[Task]
    courses: list[CurrentCourse]
