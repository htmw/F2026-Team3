"""/admin/catalog/* (spec 33): courses, degree requirements and term dates, saved as drafts until publish."""
import datetime as dt
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from schemas.base import ApiModel

CourseType = Literal["Foundation", "Core", "Elective", "Capstone"]
CODE_PATTERN = r"^[A-Z]{2,4} \d{3}[A-Z]?$"


class TermRef(ApiModel):
    id: int
    name: str


class CatalogSummary(ApiModel):
    draft_count: int
    catalog_year: str
    next_term: TermRef | None


class CatalogCourse(ApiModel):
    id: int | None  # null for a new course that isn't published yet
    code: str
    name: str
    type: CourseType
    credits: int | float
    offered: bool
    offer_label: str  # "Spring 27" or "Not offered"
    prerequisites: list[str]
    description: str | None
    draft: bool


class CoursesOut(ApiModel):
    courses: list[CatalogCourse]
    term: TermRef | None


class CourseIn(ApiModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=CODE_PATTERN)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    credits: int = Field(ge=1, le=6)
    type: CourseType = "Elective"

    @field_validator("code", mode="before")
    @classmethod
    def _squash(cls, value):
        return " ".join(value.split()).upper() if isinstance(value, str) else value


class CoursePatch(ApiModel):
    """Only the fields sent are applied; an explicit null is a 422. `offered` is for `termId` (default next term)."""
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = None
    type: CourseType = None
    credits: Annotated[int, Field(ge=1, le=6)] = None
    offered: bool = None
    term_id: int = None
    prerequisites: Annotated[list[str], Field(max_length=20)] = None
    description: Annotated[str, StringConstraints(max_length=2000)] = None


class RequirementGroupOut(ApiModel):
    id: int
    label: str
    courses: int
    credits_per_course: int
    eligible: list[str]
    requires_approval: bool


class RequirementsOut(ApiModel):
    program: TermRef
    programs: list[TermRef]
    catalog_year: str
    groups: list[RequirementGroupOut]
    total_credits: int
    draft: bool


class RequirementGroupIn(ApiModel):
    id: int
    courses: int = Field(ge=0, le=20)
    eligible: list[str] | None = None


class RequirementsIn(ApiModel):
    program_id: int
    groups: list[RequirementGroupIn] = Field(min_length=1, max_length=20)


class TermOut(ApiModel):
    id: int
    name: str
    start_date: dt.date
    end_date: dt.date
    registration_opens: dt.date | None
    last_add: dt.date | None
    last_drop: dt.date | None
    is_current: bool
    draft: bool


class TermsOut(ApiModel):
    terms: list[TermOut]
    next_term_id: int | None


class TermPatch(ApiModel):
    """Key dates; only the fields sent are applied."""
    start_date: dt.date = None
    end_date: dt.date = None
    registration_opens: dt.date = None
    last_add: dt.date = None
    last_drop: dt.date = None


class TermIn(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    start_date: dt.date
    end_date: dt.date


class PublishOut(ApiModel):
    published: int
    message: str
