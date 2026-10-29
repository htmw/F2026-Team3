"""/advisor/approvals request and response models (spec 23). `Comment` is shared with the student record's notes."""
import datetime as dt
from typing import Annotated, Literal

from pydantic import StringConstraints

from schemas.base import ApiModel

Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
StatusLabel = Literal["Pending", "Approved", "Changes requested"]


class DecisionIn(ApiModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class ChangesIn(ApiModel):
    comment: Comment


class ApprovalLineOut(ApiModel):
    a: str
    b: str


class ApprovalRowOut(ApiModel):
    id: int
    student_id: int
    name: str
    first_name: str
    type: Literal["Course plan", "Form", "Request"]
    item: str
    when: str
    status: str
    ok: bool
    check_short: str
    check: str
    lines: list[ApprovalLineOut]
    comment: str | None
    decided_at: dt.datetime | None
    can_undo: bool


class ApprovalTabOut(ApiModel):
    label: StatusLabel
    count: int


class ApprovalsOut(ApiModel):
    tabs: list[ApprovalTabOut]
    rows: list[ApprovalRowOut]
    prechecks: bool  # the advisor's "Run Acadmate pre-checks" setting (spec 27); off hides the check UI
