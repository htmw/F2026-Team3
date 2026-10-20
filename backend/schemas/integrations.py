"""/admin/integrations, /admin/imports and /admin/api-keys (spec 35)."""
from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints

from schemas.base import ApiModel


class LogRow(ApiModel):
    a: str
    b: str


class SmtpConfigOut(ApiModel):
    host: str | None
    port: int | None
    username: str | None
    from_: str | None = Field(alias="from")
    tls: bool | None


class IntegrationOut(ApiModel):
    id: Literal["csv", "mail", "gcal", "outlook"]
    name: str
    desc: str
    status: Literal["Connected", "Off", "Error", "Degraded"]
    sync: str
    log: list[LogRow]
    connected: bool
    config: SmtpConfigOut | None  # mail only; the password is never returned


class IntegrationsOut(ApiModel):
    integrations: list[IntegrationOut]


class OAuthUrlOut(ApiModel):
    url: str


class SmtpIn(ApiModel):
    host: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    port: int = Field(587, ge=1, le=65535)
    username: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    password: Annotated[str, StringConstraints(max_length=200)] = ""
    from_: EmailStr = Field(alias="from")
    tls: bool = True


class SkippedRow(ApiModel):
    line: int
    reason: str


class ImportOut(ApiModel):
    job_id: int
    created: int
    updated: int
    skipped: list[SkippedRow]
    message: str


class ApiKeyOut(ApiModel):
    id: int
    name: str
    mask: str
    scope: str
    created_at: str
    last_used_at: str | None


class ApiKeysOut(ApiModel):
    keys: list[ApiKeyOut]


class ApiKeyIn(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    scope: Literal["reports:read"] = "reports:read"


class ApiKeyCreated(ApiModel):
    id: int
    name: str
    key: str  # shown once
    mask: str
