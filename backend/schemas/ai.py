"""/students/me/ai/* (spec 13)."""
from typing import Literal

from pydantic import Field, StringConstraints
from typing_extensions import Annotated

from schemas.base import ApiModel

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Issue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AdvisorRef(ApiModel):
    id: int
    name: str


class NextMeetingOut(ApiModel):
    date: str
    time: str


class AiContextOut(ApiModel):
    enabled: bool
    engine: Literal["Claude", "Rules"]
    daily_limit: int
    remaining_today: int
    prompts: list[str]
    program: str
    progress: str
    goal: str
    preferences: list[str]
    sources: list[str]
    advisor: AdvisorRef | None
    next_meeting: NextMeetingOut | None
    retention: str


class ThreadOut(ApiModel):
    id: int
    title: str
    updated_at: str


class ThreadListOut(ApiModel):
    threads: list[ThreadOut]


class PlanRowOut(ApiModel):
    code: str
    name: str
    meta: str
    fulfills: str
    why: str | None = None
    on_plan: bool = False


class ActionOut(ApiModel):
    label: str
    to: str


class MessageOut(ApiModel):
    id: int
    role: Literal["user", "assistant"]
    kind: Literal["answer", "handoff", "limit"]
    text: str
    created_at: str
    plan_term: str | None
    plan: list[PlanRowOut]
    follow: str | None
    actions: list[ActionOut]
    sources: list[str]
    rating: int | None


class ThreadDetailOut(ApiModel):
    thread: ThreadOut
    messages: list[MessageOut]


class AskIn(ApiModel):
    text: Question


class CreateThreadOut(ApiModel):
    thread: ThreadOut
    messages: list[MessageOut]


class ReplyOut(ApiModel):
    user_message: MessageOut
    reply: MessageOut


class RatingIn(ApiModel):
    helpful: bool | None = Field(...)


class FlagIn(ApiModel):
    issue: Issue


class FlagOut(ApiModel):
    id: int


# --- admin flags (/admin/ai/flags, specs 30 and 34) ----------------------------------------------------------------

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class FlagRowOut(ApiModel):
    id: int
    q: str
    why: str
    answer: str
    when: str
    student: str | None
    source: str
    status: Literal["Open", "Resolved", "Dismissed"]


class FlagCountsOut(ApiModel):
    open: int
    resolved: int
    dismissed: int


class FlagsOut(ApiModel):
    flags: list[FlagRowOut]
    counts: FlagCountsOut


class ResolveIn(ApiModel):
    resolution: Literal["Resolved", "Dismissed"]
    note: Note | None = None


class FlagResultOut(ApiModel):
    flag: FlagRowOut


# --- admin AI settings and test box (spec 34) ----------------------------------------------------------------------

Style = Literal["Concise", "Balanced", "Detailed"]
Engine = Literal["Claude", "Rules"]
Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class AiFeatures(ApiModel):
    advisor: bool
    plan_suggestions: bool
    grade_insights: bool
    proactive_tips: bool


class AiSources(ApiModel):
    catalog: bool
    audits: bool
    grades: bool
    schedules: bool


class AiSettingsOut(ApiModel):
    features: AiFeatures
    sources: AiSources
    style: Style
    blocked_topics: list[str]
    engine: Engine
    daily_limit: int
    claude_available: bool


class AiFeaturesPatch(ApiModel):
    advisor: bool = None
    plan_suggestions: bool = None
    grade_insights: bool = None
    proactive_tips: bool = None


class AiSourcesPatch(ApiModel):
    catalog: bool = None
    audits: bool = None
    grades: bool = None
    schedules: bool = None


class AiSettingsPatch(ApiModel):
    """Any subset of the settings; only the fields sent are applied and an explicit null is a 422."""
    features: AiFeaturesPatch = None
    sources: AiSourcesPatch = None
    style: Style = None
    blocked_topics: Annotated[list[Topic], Field(max_length=30)] = None
    engine: Engine = None
    daily_limit: Annotated[int, Field(ge=1, le=500)] = None


class AiTestIn(ApiModel):
    question: Question
    student_id: int  # a student's user id (the /admin/users row id)
    settings: AiSettingsPatch = AiSettingsPatch()


class AiTestOut(ApiModel):
    engine: Engine
    advisor_on: bool
    reply: MessageOut
