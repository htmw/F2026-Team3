"""/staff, /meetings and /students/me/meetings (spec 18)."""
import datetime as dt
from typing import Literal

from pydantic import StringConstraints, field_validator
from pydantic_core import PydanticCustomError
from typing_extensions import Annotated

from core.time import now
from schemas.base import ApiModel

Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
MeetingStatus = Literal["requested", "confirmed", "proposed", "cancelled", "completed", "no_show"]


class StaffOut(ApiModel):
    id: int  # the staff member's user id
    user_id: int
    name: str
    initials: str
    role: str
    helps: str | None
    is_my_advisor: bool
    office: str | None
    meeting_length: int
    booking_window_weeks: int


class StaffListOut(ApiModel):
    staff: list[StaffOut]
    topics: list[str]
    formats: list[str]
    first_week: str  # the earliest bookable week (Monday); the frontend pages from here


class SlotOut(ApiModel):
    starts_at: str
    time: str
    taken: bool


class DayAvailOut(ApiModel):
    date: str
    dow: str
    day: str
    open: int
    free: str
    slots: list[SlotOut]


class AvailabilityOut(ApiModel):
    staff_id: int
    week: str
    time_zone: str
    days: list[DayAvailOut]


def _aware_future(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        raise PydanticCustomError("timezone", "Send the time with a time zone, e.g. 2026-10-07T14:00:00Z.")
    if value <= now():
        raise PydanticCustomError("past", "Pick a time in the future.")
    return value


class BookIn(ApiModel):
    staff_id: int
    starts_at: dt.datetime
    format: Literal["In person", "Online"]
    topic: Topic
    note: Note | None = None
    attach_plan: bool = True

    @field_validator("starts_at")
    @classmethod
    def check_start(cls, value: dt.datetime) -> dt.datetime:
        return _aware_future(value)

    @field_validator("note")
    @classmethod
    def empty_note(cls, value: str | None) -> str | None:
        return value or None


class ActionIn(ApiModel):
    """Optional body of POST /meetings/{id}/{action}: startsAt for propose, note for decline."""
    starts_at: dt.datetime | None = None
    note: Note | None = None

    @field_validator("starts_at")
    @classmethod
    def check_start(cls, value: dt.datetime | None) -> dt.datetime | None:
        return None if value is None else _aware_future(value)


class MeetingRowOut(ApiModel):
    id: int
    staff_id: int
    title: str
    mon: str
    day: str
    meta: str
    starts_at: str
    status: MeetingStatus
    proposed_starts_at: str | None


class MeetingListOut(ApiModel):
    meetings: list[MeetingRowOut]


class BookOut(ApiModel):
    id: int
    status: MeetingStatus
    summary: str
    meeting: MeetingRowOut
