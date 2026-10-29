"""/conversations/* (spec 16)."""
from typing import Literal

from pydantic import Field, StringConstraints
from typing_extensions import Annotated

from schemas.base import ApiModel

MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
GroupTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ConversationOut(ApiModel):
    id: int
    kind: Literal["direct", "group", "system"]
    name: str
    initials: str
    role: str
    preview: str | None
    time: str | None
    last_at: str | None
    unread: int
    can_reply: bool
    bookable: bool
    other_user_id: int | None
    members: int
    student_id: int | None  # the other person, when they are the caller's advisee (spec 25)
    team: bool


class ConversationListOut(ApiModel):
    conversations: list[ConversationOut]


class ContactOut(ApiModel):
    id: int
    name: str
    initials: str
    role: str
    title: str | None


class ContactsOut(ApiModel):
    contacts: list[ContactOut]


class StartIn(ApiModel):
    recipient_ids: list[int] = Field(min_length=1, max_length=30)
    text: MessageText | None = None
    title: GroupTitle | None = None


class StartOut(ApiModel):
    id: int


class MessageOut(ApiModel):
    id: int
    sender: str = Field(alias="from")  # "from" is a Python keyword
    mine: bool
    show_name: bool
    text: str
    time: str
    sent_at: str


class ThreadOut(ApiModel):
    can_reply: bool
    messages: list[MessageOut]


class SendIn(ApiModel):
    text: MessageText
