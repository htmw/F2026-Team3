"""Admin settings (spec 37): GET / PATCH /api/v1/admin/settings and POST /admin/demo/reset."""
from typing import Literal

from pydantic import ConfigDict, EmailStr, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from schemas.base import ApiModel

TimeZoneLabel = Literal["Eastern", "Central", "Pacific"]
Timeout = Literal["30 min", "2 hours", "8 hours"]
AiRetention = Literal["30 days", "1 year", "Until graduation"]
AuditRetention = Literal["90 days", "1 year", "2 years"]
Accent = Literal["#0F766E", "#1D4ED8", "#7C3AED", "#B45309"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Domain = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=100,
                                          pattern=r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")]  # checked before lowercasing


class TermRef(ApiModel):
    id: int
    name: str


class InstitutionOut(ApiModel):
    name: str
    domain: str
    support_email: str
    current_term_id: int | None
    terms: list[TermRef]
    time_zone: str
    self_signup: bool


class SecurityOut(ApiModel):
    google: bool
    mfa: bool
    ip_log: bool
    timeout: str


class RetentionOut(ApiModel):
    ai: str
    audit: str


class BrandingOut(ApiModel):
    accent: str


class SettingsOut(ApiModel):
    institution: InstitutionOut
    security: SecurityOut
    retention: RetentionOut
    branding: BrandingOut
    demo_mode: bool


# Patches: every field is optional, but an explicit null is a 422; unknown fields (terms, demoMode) too.

class _Patch(ApiModel):
    model_config = ConfigDict(extra="forbid")


class InstitutionPatch(_Patch):
    name: Name = None
    domain: Domain = None
    support_email: EmailStr = None
    current_term_id: int = None
    time_zone: TimeZoneLabel = None
    self_signup: bool = None


class SecurityPatch(_Patch):
    google: bool = None
    mfa: bool = None
    ip_log: bool = None
    timeout: Timeout = None


class RetentionPatch(_Patch):
    ai: AiRetention = None
    audit: AuditRetention = None


class BrandingPatch(_Patch):
    accent: Accent = None

    @field_validator("accent", mode="before")
    @classmethod
    def _upper(cls, value):
        return value.upper() if isinstance(value, str) else value


class SettingsPatch(_Patch):
    institution: InstitutionPatch = None
    security: SecurityPatch = None
    retention: RetentionPatch = None
    branding: BrandingPatch = None


class DemoResetOut(ApiModel):
    message: str = Field(examples=["Demo data reset."])
