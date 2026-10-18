from typing import Literal

from pydantic import EmailStr, Field, StringConstraints
from typing_extensions import Annotated

from schemas.base import ApiModel

Password = Annotated[str, StringConstraints(min_length=8, max_length=200)]


class LoginIn(ApiModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    remember: bool = False


class SignupIn(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: EmailStr
    password: Password


class ResetRequestIn(ApiModel):
    email: EmailStr


class ResetConfirmIn(ApiModel):
    token: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    password: Password


class UserOut(ApiModel):
    id: int
    role: Literal["student", "advisor", "admin"]
    email: str
    full_name: str
    first_name: str
    preferred_name: str | None = None
    initials: str
    mfa_enabled: bool
    google_linked: bool


class AuthOut(ApiModel):
    user: UserOut
    home: str


class MeOut(ApiModel):
    user: UserOut


class ConfigOut(ApiModel):
    google_enabled: bool
    accent: str
    institution_name: str
    self_signup: bool


class LinkOut(ApiModel):
    email: str
    purpose: Literal["reset", "invite"]


class OkOut(ApiModel):
    ok: bool = True


class BadgesOut(ApiModel):
    badges: dict[str, int] = Field(default_factory=dict)
