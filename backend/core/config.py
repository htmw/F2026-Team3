"""Application settings, read once from the environment (backend/.env via python-dotenv)."""
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()


def _str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, "").strip()
    return value or default


def _bool(name: str, default: bool = False) -> bool:
    value = _str(name)
    return default if value is None else value.lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    value = _str(name)
    return default if value is None else int(value)


def _date(name: str) -> date | None:
    value = _str(name)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise RuntimeError(f"{name} must be a date like 2026-10-01, got {value!r}.") from None


class Settings:
    def __init__(self) -> None:
        database_url = _str("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set. Copy backend/.env.example to backend/.env.")
        self.DATABASE_URL: str = database_url
        self.SESSION_COOKIE: str = _str("SESSION_COOKIE", "acadmate_session")
        self.SESSION_DAYS_REMEMBER: int = _int("SESSION_DAYS_REMEMBER", 30)
        # The idle timeout for non-remembered sessions comes from admin Settings (spec 37), not env.
        self.SECRET_KEY: str | None = _str("SECRET_KEY")  # encrypts integration secrets (spec 35)
        self.DEMO_MODE: bool = _bool("DEMO_MODE")
        self.COOKIE_SECURE: bool = _bool("COOKIE_SECURE")
        self.FRONTEND_ORIGIN: str = _str("FRONTEND_ORIGIN", "http://localhost:5173")
        self.GOOGLE_CLIENT_ID: str | None = _str("GOOGLE_CLIENT_ID")
        self.GOOGLE_CLIENT_SECRET: str | None = _str("GOOGLE_CLIENT_SECRET")
        self.GOOGLE_ALLOWED_DOMAIN: str | None = _str("GOOGLE_ALLOWED_DOMAIN")
        self.MICROSOFT_CLIENT_ID: str | None = _str("MICROSOFT_CLIENT_ID")  # Outlook Calendar (spec 35)
        self.MICROSOFT_CLIENT_SECRET: str | None = _str("MICROSOFT_CLIENT_SECRET")
        self.ANTHROPIC_API_KEY: str | None = _str("ANTHROPIC_API_KEY")
        self.PUBLIC_API_URL: str | None = _str("PUBLIC_API_URL")  # base for calendar feed links; default: the request URL
        self.ACADMATE_TODAY: date | None = _date("ACADMATE_TODAY")


settings = Settings()
