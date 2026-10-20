"""/users/me settings, preferences, export and account deletion (spec 17; shared with advisor settings, spec 27)."""
from typing import Literal

from pydantic import ConfigDict, EmailStr, StringConstraints, model_validator
from typing_extensions import Annotated

from schemas.base import ApiModel

ReminderTiming = Literal["1 day before", "2 days before", "1 week before"]
AiStyle = Literal["Concise", "Detailed"]
ClassTime = Literal["Evening", "Daytime"]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
PreferredName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Email = Annotated[EmailStr, StringConstraints(max_length=254)]


class Strict(ApiModel):
    """Unknown keys are rejected (a typo must not be stored silently)."""
    model_config = ConfigDict(extra="forbid")


class NotifyPrefs(Strict):
    deadlines: bool
    messages: bool
    suggestions: bool
    weekly_summary: bool
    sms: bool


class AiPrefs(Strict):
    use_grades: bool
    use_schedule: bool
    dashboard_suggestions: bool
    share_with_advisor: bool


class PreferencesOut(ApiModel):
    notify: NotifyPrefs
    reminder_timing: ReminderTiming
    ai: AiPrefs
    ai_style: AiStyle
    target_graduation: str | None
    class_time: ClassTime | None


class PreferencesWithOptions(PreferencesOut):
    graduation_options: list[str]  # choices for targetGraduation (response only)


class NotifyPatch(Strict):
    deadlines: bool | None = None
    messages: bool | None = None
    suggestions: bool | None = None
    weekly_summary: bool | None = None
    sms: bool | None = None


class AiPatch(Strict):
    use_grades: bool | None = None
    use_schedule: bool | None = None
    dashboard_suggestions: bool | None = None
    share_with_advisor: bool | None = None


class PreferencesPatch(Strict):
    """A full or partial preferences object. graduationOptions is accepted (and ignored) so the screen can send back
    what it loaded."""
    notify: NotifyPatch | None = None
    reminder_timing: ReminderTiming | None = None
    ai: AiPatch | None = None
    ai_style: AiStyle | None = None
    target_graduation: str | None = None
    class_time: ClassTime | None = None
    graduation_options: list[str] | None = None

    def changes(self) -> dict:
        """The keys the caller sent, camelCase like the stored JSON (null booleans dropped)."""
        data = self.model_dump(by_alias=True, exclude_unset=True, exclude={"graduation_options"})
        for group in ("notify", "ai"):
            if group in data:
                if data[group] is None:
                    del data[group]
                else:
                    data[group] = {key: value for key, value in data[group].items() if value is not None}
        for key in ("reminderTiming", "aiStyle"):
            if key in data and data[key] is None:
                del data[key]
        return data


class PreferencesResponse(ApiModel):
    preferences: PreferencesWithOptions


class ProfileOut(ApiModel):
    full_name: str
    preferred_name: str | None
    email: str
    initials: str
    role: Literal["student", "advisor", "admin"]
    has_password: bool
    student_number: str | None = None
    program: str | None = None
    advisor: str | None = None
    expected_graduation: str | None = None


class GoogleOut(ApiModel):
    available: bool
    connected: bool
    email: str | None


class SettingsMeOut(ApiModel):
    profile: ProfileOut
    preferences: PreferencesWithOptions
    google: GoogleOut


class ProfilePatch(Strict):
    full_name: FullName | None = None
    preferred_name: PreferredName | None = None
    email: Email | None = None

    @model_validator(mode="after")
    def no_null_required(self):
        for field in ("full_name", "email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{'Full name' if field == 'full_name' else 'Email'} can't be empty.")
        return self


class DeleteMeIn(Strict):
    password: Annotated[str, StringConstraints(max_length=200)] | None = None


class GoogleConnectOut(ApiModel):
    url: str
