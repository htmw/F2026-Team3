"""/advisor/* response models: dashboard (spec 20), advisees (spec 21) and the student record (spec 22). The
approvals queue's models (spec 23) are in schemas/approvals.py."""
import datetime as dt
from typing import Annotated, Literal

from pydantic import ConfigDict, StringConstraints

from schemas.approvals import Comment
from schemas.base import ApiModel


class AdvisorHeaderOut(ApiModel):
    display_name: str
    subtitle: str
    initials: str


class AdvisorStatOut(ApiModel):
    key: Literal["advisees", "waiting", "meetings", "attention"]
    label: str
    value: str
    tag: str | None
    tone: str
    note: str


class QueueItemOut(ApiModel):
    id: int
    student_id: int
    name: str
    initials: str
    type: Literal["Course plan", "Form", "Request"]
    item: str
    when: str
    check: str
    ok: bool


class TodayMeetingOut(ApiModel):
    id: str
    time: str
    who: str
    student_id: int | None
    topic: str
    action: Literal["Notes", "Join", "Open", "Details"]
    href: str


class TodayOut(ApiModel):
    label: str
    meetings: list[TodayMeetingOut]


class AttentionOut(ApiModel):
    student_id: int
    user_id: int
    name: str
    initials: str
    flag: str | None
    gpa: str
    last: str
    level: Literal["High", "Medium"]


class CaseloadOut(ApiModel):
    label: str
    n: int
    tone: str


class GradBucketOut(ApiModel):
    n: int
    label: str


class AdvisorDashboardOut(ApiModel):
    advisor: AdvisorHeaderOut
    stats: list[AdvisorStatOut]
    queue: list[QueueItemOut]
    queue_total: int
    today: TodayOut
    attention: list[AttentionOut]
    caseload: list[CaseloadOut]
    graduation: list[GradBucketOut]
    prechecks: bool  # spec 27 "Run Acadmate pre-checks"; off: never disable quick Approve, hide the check line


class AdviseeTabOut(ApiModel):
    label: Literal["All", "Needs attention", "On track", "Graduating"]
    count: int


class AdviseeRowOut(ApiModel):
    student_id: int
    user_id: int
    name: str
    full_name: str
    initials: str
    program: str | None
    credits: float
    required_credits: float
    gpa: str
    status: Literal["On track", "Needs attention", "Graduating"]
    risk: Literal["High", "Medium", "Low"]
    flag: str | None
    next: str
    graduates: str | None


class AdviseesOut(ApiModel):
    subtitle: str
    tabs: list[AdviseeTabOut]
    rows: list[AdviseeRowOut]
    total: int


class RecordStudentOut(ApiModel):
    id: int
    user_id: int
    name: str
    full_name: str
    first_name: str
    initials: str
    subtitle: str


class RecordStatOut(ApiModel):
    label: str
    value: str
    tag: str
    tone: str
    note: str


class PlanRowOut(ApiModel):
    code: str
    name: str
    when: str
    fulfills: str | None


class CheckOut(ApiModel):
    ok: bool
    blocking: bool
    text: str


class ReviewOut(ApiModel):
    request_id: int
    title: str
    subtitle: str
    status: Literal["pending", "approved", "changes_requested"]
    status_label: str
    plan: list[PlanRowOut]
    checks: list[CheckOut]
    student_note: str | None
    comment: str | None
    decided_at: dt.datetime | None
    can_undo: bool
    registration_opens: str | None


class PlannedTermOut(ApiModel):
    title: str
    plan: list[PlanRowOut]


class GroupBarOut(ApiModel):
    title: str
    count: str
    done: int
    in_progress: int
    required: int


class RecordMeetingOut(ApiModel):
    id: int
    title: str
    meta: str
    past: bool


class NoteIn(ApiModel):
    text: Comment


class NoteOut(ApiModel):
    id: int
    text: str
    when: str
    mine: bool


class ActivityOut(ApiModel):
    when: str
    text: str


class RecordOut(ApiModel):
    student: RecordStudentOut
    stats: list[RecordStatOut]
    review: ReviewOut | None
    planned_term: PlannedTermOut | None
    groups: list[GroupBarOut]
    meetings: list[RecordMeetingOut]
    notes: list[NoteOut]
    activity: list[ActivityOut]
    ai_shared: bool


class ReportTermOut(ApiModel):
    id: int
    label: str


class ReportStatOut(ApiModel):
    label: str
    value: str
    note: str


class StatusRowOut(ApiModel):
    label: Literal["On track", "Needs attention", "Graduating"]
    count: int
    tone: Literal["accent", "amber", "violet"]


class WeekOut(ApiModel):
    label: str
    value: int


class CheckOnOut(ApiModel):
    student_id: int
    name: str
    reason: str
    action: Literal["Review request", "Review plan", "Message", "View advisee"]
    to: str


class ReportOut(ApiModel):
    terms: list[ReportTermOut]
    current_term_id: int
    term_id: int
    term_label: str
    stats: list[ReportStatOut]
    by_status: list[StatusRowOut]
    weeks: list[WeekOut]
    check_on: list[CheckOnOut]


class SettingsProfileOut(ApiModel):
    full_name: str
    email: str
    initials: str


class AdvisorFieldsOut(ApiModel):
    title: str | None
    department: str | None
    office: str | None
    meeting_length: Literal[15, 30, 45]
    booking_window: Literal["1 week ahead", "2 weeks ahead", "4 weeks ahead"]
    auto_confirm: bool


class AdvisorNotifyOut(ApiModel):
    new_approval: bool
    booking: bool
    messages: bool
    weekly_digest: bool


class AdvisorApprovalsOut(ApiModel):
    precheck: bool
    remind_after3_days: bool


class AdvisorSettingsOut(ApiModel):
    profile: SettingsProfileOut
    advisor: AdvisorFieldsOut
    notify: AdvisorNotifyOut
    approvals: AdvisorApprovalsOut


class _StrictIn(ApiModel):
    model_config = ConfigDict(extra="forbid")


class AdvisorNotifyPatch(_StrictIn):
    new_approval: bool | None = None
    booking: bool | None = None
    messages: bool | None = None
    weekly_digest: bool | None = None


class AdvisorApprovalsPatch(_StrictIn):
    precheck: bool | None = None
    remind_after3_days: bool | None = None


class AdvisorSettingsPatch(_StrictIn):
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    office: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    meeting_length: Literal[15, 30, 45] | None = None
    booking_window: Literal["1 week ahead", "2 weeks ahead", "4 weeks ahead"] | None = None
    auto_confirm: bool | None = None
    notify: AdvisorNotifyPatch | None = None
    approvals: AdvisorApprovalsPatch | None = None


class SharedThreadOut(ApiModel):
    id: int
    title: str
    updated_at: str


class SharedThreadsOut(ApiModel):
    threads: list[SharedThreadOut]
