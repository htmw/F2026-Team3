"""/advisor/meetings and /advisor/office-hours (spec 24)."""
import datetime as dt
from typing import Literal

from pydantic import StringConstraints, field_validator
from typing_extensions import Annotated

from schemas.base import ApiModel
from schemas.meetings import MeetingStatus, Note, Topic, _aware_future

Weekday = Literal["Mon", "Tue", "Wed", "Thu", "Fri"]
Clock = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class AgendaRowOut(ApiModel):
    id: int | str  # office-hour rows are "off-{window}-{date}"
    kind: Literal["meeting", "office_hours"]
    day: str
    date: str
    time: str
    who: str
    student_id: int | None
    user_id: int | None
    topic: str
    format: Literal["In person", "Online"]
    status: MeetingStatus | Literal["open"]
    video_url: str | None
    location: str | None
    notes: str | None
    note: str | None
    proposed_time: str | None
    can_complete: bool
    can_cancel: bool


class RequestRowOut(ApiModel):
    id: int
    student_id: int
    who: str
    when: str
    topic: str
    status: MeetingStatus


class OfficeHoursOut(ApiModel):
    days: list[Weekday]
    start: str | None
    end: str | None
    location: str | None
    summary: str


class AdvisorMeetingsOut(ApiModel):
    today: str
    agenda: list[AgendaRowOut]
    requests: list[RequestRowOut]
    office_hours: OfficeHoursOut


class OfficeHoursWrapOut(ApiModel):
    office_hours: OfficeHoursOut


class FreeSlotOut(ApiModel):
    starts_at: str
    time: str


class FreeSlotsOut(ApiModel):
    slots: list[FreeSlotOut]


class NotesIn(ApiModel):
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None = None


class AdvisorBookIn(ApiModel):
    student_id: int
    starts_at: dt.datetime
    format: Literal["In person", "Online"]
    topic: Topic
    note: Note | None = None

    @field_validator("starts_at")
    @classmethod
    def check_start(cls, value: dt.datetime) -> dt.datetime:
        return _aware_future(value)

    @field_validator("note")
    @classmethod
    def empty_note(cls, value: str | None) -> str | None:
        return value or None


class OfficeHoursIn(ApiModel):
    days: list[Weekday]
    start: Clock
    end: Clock
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None

    @field_validator("days")
    @classmethod
    def unique_days(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Pick each day once.")
        return value  # end after start is checked by services/advisor_meetings.set_office_hours (field "end")
