"""Admin integrations (spec 35): CSV data import, email (SMTP) and Google / Outlook Calendar. Status is derived:
Error after a failed connection, Off when disabled, Degraded for mail with a recent send failure, else Connected.
Secrets (the SMTP password, OAuth refresh tokens) are stored encrypted. Calendars stop at storing the refresh
token: meetings aren't pushed to them yet."""
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from core.errors import ApiError, bad_request, conflict, not_found
from core.security import decrypt, encrypt, sha256_hex
from core.time import local_zone, now, short_date, today
from models import Integration, IntegrationEvent, User
from services import audit, mailer

CARDS = {
    "csv": ("CSV data import", "Upload courses, enrollments and grades exported from your school's systems."),
    "mail": ("Email (SMTP)", "Sends meeting confirmations, reminders and invites."),
    "gcal": ("Google Calendar", "Lets students and advisors sync Acadmate meetings."),
    "outlook": ("Outlook Calendar", "Lets students and advisors sync Acadmate meetings."),
}
CALENDARS = {
    "gcal": {
        "env": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/calendar.events",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "outlook": {
        "env": ("MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"),
        "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "offline_access Calendars.ReadWrite",
        "extra": {},
    },
}
STATE_TTL = timedelta(minutes=10)
LOG_ROWS = 5
OAUTH_TIMEOUT = 10  # seconds


def when_label(at: datetime) -> str:
    """"Today 06:00", "Yesterday 14:10", else "Sep 29" (school time zone)."""
    local = at.astimezone(local_zone())
    if local.date() == today():
        return f"Today {local:%H:%M}"
    if local.date() == today() - timedelta(days=1):
        return f"Yesterday {local:%H:%M}"
    return short_date(local.date())


def _ensure(db: Session) -> dict[str, Integration]:
    rows = {row.id: row for row in db.query(Integration)}
    for key in CARDS:
        if key not in rows:
            rows[key] = Integration(id=key, enabled=False, config={})
            db.add(rows[key])
    db.flush()
    return rows


def _get(db: Session, integration_id: str) -> Integration:
    if integration_id not in CARDS:
        raise not_found("Integration")
    return _ensure(db)[integration_id]


def event(db: Session, integration_id: str, text: str, at: datetime | None = None) -> None:
    db.add(IntegrationEvent(integration_id=integration_id, text=text[:200], created_at=at or now()))


def status(row: Integration) -> str:
    if row.last_error:
        return "Error"
    if not row.enabled:
        return "Off"
    if row.id == "mail" and mailer.health()[0] == "Degraded":
        return "Degraded"
    return "Connected"


def _sync_text(row: Integration) -> str:
    if row.id == "csv":
        return f"Last import {when_label(row.last_sync_at).lower()}" if row.last_sync_at else "No imports yet"
    if row.id == "mail":
        return mailer.health()[1] if row.enabled else "Not connected"
    return "Connected" if row.enabled else "Not connected"


def _log(db: Session, row: Integration) -> list[dict]:
    events = (db.query(IntegrationEvent).filter(IntegrationEvent.integration_id == row.id)
              .order_by(IntegrationEvent.id.desc()).limit(LOG_ROWS).all())  # insertion order, like the audit log
    rows = [{"a": e.text, "b": when_label(e.created_at)} for e in events]
    if row.id == "mail" and row.enabled:
        sent = mailer.sent_today()
        rows.insert(0, {"a": f"{sent:,} email{'' if sent == 1 else 's'} sent today", "b": "Live"})
    return rows or [{"a": "Never connected", "b": "—"}]


def row_out(db: Session, row: Integration) -> dict:
    name, desc = CARDS[row.id]
    out = {"id": row.id, "name": name, "desc": desc, "status": status(row), "sync": _sync_text(row),
           "log": _log(db, row), "connected": bool(row.enabled), "config": None}
    if row.id == "mail" and row.config:
        out["config"] = {key: row.config.get(key) for key in ("host", "port", "username", "from", "tls")}
    return out


def list_all(db: Session) -> dict:
    rows = _ensure(db)
    db.commit()
    return {"integrations": [row_out(db, rows[key]) for key in CARDS]}


def get_row(db: Session, integration_id: str) -> dict:
    return row_out(db, _get(db, integration_id))


def smtp_config(db: Session) -> dict | None:
    """SMTP settings with the password decrypted, or None when mail isn't connected (mailer then logs)."""
    row = db.get(Integration, "mail")
    if row is None or not row.enabled or not row.config:
        return None
    cfg = dict(row.config)
    cfg["password"] = decrypt(cfg["password"]) if cfg.get("password") else ""
    return cfg


# --- connect / disconnect / sync -------------------------------------------------------------------------------------

def _provider(integration_id: str) -> dict:
    provider = CALENDARS[integration_id]
    client_id, secret = (getattr(settings, name) for name in provider["env"])
    if not (client_id and secret):
        raise ApiError(400, "PROVIDER_NOT_CONFIGURED", f"{CARDS[integration_id][0]} isn't configured on this server.")
    return {**provider, "client_id": client_id, "client_secret": secret}


def callback_url(integration_id: str, base_url: str) -> str:
    base = (settings.PUBLIC_API_URL or base_url).rstrip("/")
    return f"{base}/api/v1/admin/integrations/{integration_id}/callback"


def connect(db: Session, admin: User, integration_id: str, body: dict | None, base_url: str,
            ip: str | None = None) -> dict:
    """csv and mail return the integration; a calendar returns {"url"} to send the admin to the provider."""
    row = _get(db, integration_id)
    if integration_id == "csv":
        row.enabled, row.last_error = True, None
        event(db, row.id, "Connected")
    elif integration_id == "mail":
        if body is None:
            raise ApiError(422, "VALIDATION_ERROR", "Check the highlighted fields.",
                           [{"field": "host", "message": "Enter the SMTP server settings."}])
        cfg = {"host": body["host"], "port": body["port"], "username": body.get("username") or "",
               "password": body.get("password") or "", "from": body["from"], "tls": body.get("tls", True)}
        try:
            mailer.test_send(cfg, admin.email)
        except Exception as err:  # smtplib and socket errors: report the server's message, save nothing
            raise ApiError(400, "SMTP_FAILED", str(err) or err.__class__.__name__) from None
        row.config = {**cfg, "password": encrypt(cfg["password"]) if cfg["password"] else ""}
        row.enabled, row.last_error, row.last_sync_at = True, None, now()
        event(db, row.id, f"Connected · test email sent to {admin.email}")
        audit.record(db, admin, "integration.connect", f"Connected {CARDS[row.id][0]}", ("integration", row.id),
                     {"host": [None, cfg["host"]]}, ip=ip)
        db.commit()
        mailer.configure(cfg)
        return get_row(db, row.id)
    else:
        provider = _provider(integration_id)
        state = secrets.token_urlsafe(24)
        row.config = {**(row.config or {}), "pendingState": sha256_hex(state),
                      "stateExpires": (now() + STATE_TTL).isoformat()}
        db.commit()
        query = {"client_id": provider["client_id"], "redirect_uri": callback_url(row.id, base_url),
                 "response_type": "code", "scope": provider["scope"], "state": state, **provider["extra"]}
        return {"url": f"{provider['authorize']}?{urlencode(query)}"}

    audit.record(db, admin, "integration.connect", f"Connected {CARDS[row.id][0]}", ("integration", row.id), ip=ip)
    db.commit()
    return get_row(db, row.id)


def oauth_callback(db: Session, admin: User, integration_id: str, code: str | None, state: str | None,
                   base_url: str, ip: str | None = None) -> None:
    """Exchanges the provider's code for a refresh token. A bad state is a 400; a provider error marks the
    integration Error (the admin sees it on the card) instead of failing the redirect."""
    if integration_id not in CALENDARS:
        raise not_found("Integration")
    row = _get(db, integration_id)
    cfg = row.config or {}
    expires = cfg.get("stateExpires")
    if (not state or cfg.get("pendingState") != sha256_hex(state) or not expires
            or datetime.fromisoformat(expires) < now()):
        raise bad_request("This connection link has expired. Try Connect again.")
    provider = _provider(integration_id)
    name = CARDS[row.id][0]
    try:
        response = httpx.post(provider["token"], timeout=OAUTH_TIMEOUT, data={
            "code": code or "", "client_id": provider["client_id"], "client_secret": provider["client_secret"],
            "redirect_uri": callback_url(row.id, base_url), "grant_type": "authorization_code"})
        response.raise_for_status()
        token = response.json().get("refresh_token")
        if not token:
            raise ValueError("The provider didn't return a refresh token.")
    except Exception as err:
        row.config, row.enabled, row.last_error = {}, False, str(err)[:300]
        event(db, row.id, f"Connection failed: {str(err)[:150]}")
        audit.record(db, admin, "integration.connect", f"Couldn't connect {name}", ("integration", row.id),
                     ip=ip, result="failed", error=str(err))
        db.commit()
        return
    row.config = {"refreshToken": encrypt(token)}
    row.enabled, row.last_error, row.last_sync_at = True, None, now()
    event(db, row.id, "Connected")
    audit.record(db, admin, "integration.connect", f"Connected {name}", ("integration", row.id), ip=ip)
    db.commit()


def disconnect(db: Session, admin: User, integration_id: str, ip: str | None = None) -> dict:
    row = _get(db, integration_id)
    row.enabled, row.config, row.last_error = False, {}, None
    event(db, row.id, "Disconnected")
    audit.record(db, admin, "integration.disconnect", f"Disconnected {CARDS[row.id][0]}", ("integration", row.id), ip=ip)
    db.commit()
    if row.id == "mail":
        mailer.configure(None)
    return get_row(db, row.id)


def sync(db: Session, admin: User, integration_id: str, ip: str | None = None) -> dict:
    row = _get(db, integration_id)
    name = CARDS[row.id][0]
    if not row.enabled:
        raise conflict(f"Connect {name} first.")
    if row.id == "csv":
        from services import imports  # imported here: imports uses this module's event()
        imports.rerun_latest(db, admin, ip=ip)
        audit.record(db, admin, "integration.sync", f"Synced {name}", ("integration", row.id), ip=ip)
        db.commit()
        return get_row(db, row.id)
    if row.id == "mail":
        try:
            mailer.test_send(smtp_config(db), admin.email)
        except Exception as err:
            mailer.record_failure()
            raise ApiError(400, "SMTP_FAILED", str(err) or err.__class__.__name__) from None
        event(db, row.id, f"Test email sent to {admin.email}")
    else:
        event(db, row.id, "Manual sync completed")
    row.last_sync_at = now()
    audit.record(db, admin, "integration.sync", f"Synced {name}", ("integration", row.id), ip=ip)
    db.commit()
    return get_row(db, row.id)
