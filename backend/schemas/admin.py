"""/admin/* response models: overview (spec 30), users (spec 31), advisors (spec 32), audit log (spec 36)."""
from typing import Annotated, Any, Literal

from pydantic import EmailStr, Field, StringConstraints, model_validator

from schemas.base import ApiModel

Percent = int | float | None  # ints stay ints in the JSON ("91", not "91.0"); flagged-as-wrong has 1 dp


class StatOut(ApiModel):
    key: Literal["activeStudents", "advisors", "aiQuestions", "plansWaiting"]
    label: str
    value: str
    tag: str | None
    tone: str
    note: str | None


class WeekOut(ApiModel):
    label: str
    value: int
    highlight: bool


class ChangeOut(ApiModel):
    pct: int | None
    direction: Literal["up", "down", "flat"]
    text: str


class WeeklyActiveOut(ApiModel):
    weeks: list[WeekOut]
    change: ChangeOut


class AiQuestionsOut(ApiModel):
    value: str
    note: str


class QualityRowOut(ApiModel):
    label: str
    pct: Percent
    tone: str
    note: str


class SystemOut(ApiModel):
    key: str
    name: str
    detail: str
    status: Literal["Healthy", "Degraded", "Down", "Off"]


class WorkloadRowOut(ApiModel):
    advisor_id: int
    user_id: int
    name: str
    advisees: int
    capacity: int
    waiting: int
    avg_reply: str
    load_pct: int
    load: Literal["OK", "Over"]


class OverviewOut(ApiModel):
    subtitle: str
    stats: list[StatOut]
    weekly_active: WeeklyActiveOut
    ai_questions: AiQuestionsOut
    ai_quality: list[QualityRowOut]
    systems: list[SystemOut]
    advisors: list[WorkloadRowOut]


# --- users (spec 31) ----------------------------------------------------------------------------------------------

EmailText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]
RoleIn = Literal["student", "advisor", "admin"]


class AdminUserRow(ApiModel):
    id: int
    name: str
    initials: str
    email: str
    role: Literal["Student", "Advisor", "Admin"]
    dept: str
    program_id: int | None
    status: Literal["Active", "Invited", "Deactivated"]
    last_active: str
    last_active_at: str | None
    student_id: int | None
    advisor_id: int | None
    advisor_name: str | None


class AdvisorOption(ApiModel):
    id: int
    user_id: int
    name: str
    advisees: int


class ProgramOption(ApiModel):
    id: int
    name: str


class AdminUsersOut(ApiModel):
    rows: list[AdminUserRow]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]  # {"All", "Students", "Advisors", "Admins"}
    advisors: list[AdvisorOption]
    programs: list[ProgramOption]


class InviteIn(ApiModel):
    emails: list[EmailText] = Field(min_length=1, max_length=100)
    role: RoleIn


class InviteSkip(ApiModel):
    email: str
    reason: str


class InviteOut(ApiModel):
    sent: int
    skipped: list[InviteSkip]


class ImportSkip(ApiModel):
    line: int
    reason: str


class ImportOut(ApiModel):
    created: int
    updated: int
    skipped: list[ImportSkip]
    file: str | None


class UserPatch(ApiModel):
    """Only the fields sent are applied. Defaults aren't validated, so leaving a field out is fine but an explicit
    null is a 422 for everything except advisorId, where null means "no advisor"."""
    role: RoleIn = None
    advisor_id: int | None = None
    program_id: int = None
    status: Literal["Active", "Deactivated"] = None


# --- advisors (spec 32) --------------------------------------------------------------------------------------------

Department = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class AdminAdvisorRow(ApiModel):
    id: int
    user_id: int
    name: str
    dept: str
    load: int
    cap: int
    pending: int
    resp: str  # "1.4 days", "—" without decisions in the last 60 days
    status: Literal["Over capacity", "Near capacity", "Has room"]
    active: bool


class AdvisorsOut(ApiModel):
    advisors: list[AdminAdvisorRow]


class AddAdvisorIn(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: EmailStr
    department: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    capacity: int = Field(40, ge=1, le=200)


class AdvisorPatch(ApiModel):
    """Only the fields sent are applied; an explicit null is a 422. An empty department or title clears it."""
    capacity: Annotated[int, Field(ge=1, le=200)] = None
    department: Department = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = None


class ReassignIn(ApiModel):
    """Either `count` (the service picks who moves) or exactly these `studentIds`."""
    to_advisor_id: int
    count: int | None = Field(None, ge=1)
    student_ids: list[int] | None = Field(None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _one_of(self):
        if (self.count is None) == (self.student_ids is None):
            raise ValueError("Send either count or studentIds.")
        return self


class ReassignOut(ApiModel):
    moved: int
    from_: AdminAdvisorRow = Field(alias="from")
    to: AdminAdvisorRow
    message: str


# --- audit log (spec 36) -------------------------------------------------------------------------------------------

class AuditChangeOut(ApiModel):
    field: str
    from_: Any = Field(alias="from")
    to: Any


class AuditLinkOut(ApiModel):
    to: str
    label: str


class AuditEventOut(ApiModel):
    id: int
    event_id: str  # "evt_1042"
    when: str  # "Today 14:02"
    at: str
    who: str
    role: Literal["Admin", "Advisor", "Student", "System"]
    action: str  # the sentence
    key: str  # the machine action, e.g. "advisor.reassign"
    target: str | None
    ip: str | None
    result: Literal["Success", "Failed"]
    error: str | None
    changes: list[AuditChangeOut]
    link: AuditLinkOut | None


class AuditListOut(ApiModel):
    events: list[AuditEventOut]
    next_cursor: str | None
