"""The app's clock. Use these instead of date.today() / datetime.now() so demo data stays consistent
(ACADMATE_TODAY pins "today"). current_term(db) / next_term(db) live in services/catalog.py."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from core.config import settings

DEFAULT_ZONE = "America/New_York"  # spec 37 "Eastern"
_zone = ZoneInfo(DEFAULT_ZONE)


def local_zone() -> ZoneInfo:
    """The institution's time zone (spec 37). services/settings.apply_time_zone() sets it from the saved setting at
    startup and after a change; other worker processes pick a change up on restart."""
    return _zone


def set_zone(name: str) -> None:
    global _zone
    _zone = ZoneInfo(name)


def today() -> date:
    """Today in the institution's time zone (or the pinned ACADMATE_TODAY)."""
    return settings.ACADMATE_TODAY or datetime.now(local_zone()).date()


def now() -> datetime:
    """Current time, tz-aware UTC. With ACADMATE_TODAY set: the pinned date at the current school-time time of day,
    so now() always falls on today() in the institution's time zone (pinning the UTC date could land on the day
    before or after there)."""
    current = datetime.now(local_zone())
    pinned = settings.ACADMATE_TODAY
    if pinned:
        current = current.replace(year=pinned.year, month=pinned.month, day=pinned.day)
    return current.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    """ISO 8601 UTC with a trailing Z, the API's timestamp format."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def short_date(value: date) -> str:
    """"Oct 3" (built by hand: strftime's %-d isn't portable to Windows)."""
    return f"{MONTH_NAMES[value.month - 1]} {value.day}"


def day_label(value: date) -> str:
    """"Thu, Oct 1"."""
    return f"{DAY_NAMES[value.weekday()]}, {short_date(value)}"


def local_midnight() -> datetime:
    """Start of today in the institution's time zone, as tz-aware UTC (daily limits reset here)."""
    local = now().astimezone(local_zone())
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
