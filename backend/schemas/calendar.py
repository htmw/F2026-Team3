"""Schedule and calendar feed (spec 14)."""
import datetime as dt
from typing import Literal

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError
from pydantic_core.core_schema import ValidationInfo

from schemas.base import ApiModel

PERSONAL_TYPES = ("Study", "Team", "Office hours", "Advising")


class EventOut(ApiModel):
    id: str
    kind: Literal["personal", "class", "meeting", "office"]
    title: str
    type: str
    date: str
    start: str
    end: str
    location: str | None
    note: str | None
    editable: bool
    status: str | None
    reminder_minutes: int | None


class DayOut(ApiModel):
    date: str
    name: str
    day: int
    due: list[str]
    events: list[EventOut]


class DeadlineOut(ApiModel):
    id: str
    title: str
    course: str
    date: str
    label: str
    status: str


class SuggestionOut(ApiModel):
    title: str
    text: str
    date: str
    start: str
    end: str


class WeekOut(ApiModel):
    from_: str = Field(alias="from")
    to: str
    today: str
    days: list[DayOut]
    deadlines: list[DeadlineOut]
    suggestion: SuggestionOut | None


def _type(value: str) -> str:
    if value == "Class":
        raise PydanticCustomError("event_type", "Classes come from your enrollments.")
    if value not in PERSONAL_TYPES:
        raise PydanticCustomError("event_type", "Choose Study, Team, Office hours or Advising.")
    return value


def _text(value: str | None, limit: int, required: bool = False) -> str | None:
    value = (value or "").strip()
    if required and not value:
        raise PydanticCustomError("required", "This field is required.")
    if len(value) > limit:
        raise PydanticCustomError("too_long", "Must be at most {limit} characters.", {"limit": limit})
    return value or None


class EventIn(ApiModel):
    title: str
    type: str
    date: dt.date
    start: dt.time
    end: dt.time
    location: str | None = None
    note: str | None = None

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str) -> str:
        return _text(value, 80, required=True)

    @field_validator("type")
    @classmethod
    def check_type(cls, value: str) -> str:
        return _type(value)

    @field_validator("location")
    @classmethod
    def check_location(cls, value: str | None) -> str | None:
        return _text(value, 80)

    @field_validator("note")
    @classmethod
    def check_note(cls, value: str | None) -> str | None:
        return _text(value, 500)

    @field_validator("end")
    @classmethod
    def check_end(cls, value: dt.time, info: ValidationInfo) -> dt.time:
        start = info.data.get("start")
        if start is not None and value <= start:
            raise PydanticCustomError("end_before_start", "End time must be after the start time.")
        return value


class EventPatch(ApiModel):
    """Any subset of the event fields; the service re-checks end > start after merging."""
    title: str | None = None
    type: str | None = None
    date: dt.date | None = None
    start: dt.time | None = None
    end: dt.time | None = None
    location: str | None = None
    note: str | None = None
    reminder_minutes: int | None = Field(None, ge=0, le=1440)

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str | None) -> str | None:
        return None if value is None else _text(value, 80, required=True)

    @field_validator("type")
    @classmethod
    def check_type(cls, value: str | None) -> str | None:
        return None if value is None else _type(value)

    @field_validator("location")
    @classmethod
    def check_location(cls, value: str | None) -> str | None:
        return _text(value, 80)

    @field_validator("note")
    @classmethod
    def check_note(cls, value: str | None) -> str | None:
        return _text(value, 500)

    @field_validator("end")
    @classmethod
    def check_end(cls, value: dt.time | None, info: ValidationInfo) -> dt.time | None:
        start = info.data.get("start")
        if value is not None and start is not None and value <= start:
            raise PydanticCustomError("end_before_start", "End time must be after the start time.")
        return value


class FeedOut(ApiModel):
    url: str
