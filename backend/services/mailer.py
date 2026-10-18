"""Outgoing email. Sends through SMTP when the `mail` integration is connected (spec 35), else writes the message
to the server log. Mail goes out after the commit, so a failed send is logged and counted, never raised.
health() feeds the admin overview's System status (spec 30) and the Email integration card."""
import logging
import smtplib
from collections import deque
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import NamedTuple

from core.time import local_zone, now, today

logger = logging.getLogger("acadmate.mail")

HEALTH_WINDOW = timedelta(hours=1)
SMTP_TIMEOUT = 10  # seconds
_failures: deque[datetime] = deque(maxlen=500)
_sent: deque[datetime] = deque(maxlen=10000)
_UNSET = object()
_config = _UNSET  # SMTP settings (password decrypted), None for log-only; loaded on first use


class Mail(NamedTuple):
    """An email built inside a transaction and sent once it commits (send_all), so a rollback never mails a dead link."""
    to: str
    subject: str
    text: str


def configure(cfg: dict | None) -> None:
    """Called by services/integrations after the mail integration is connected (cfg) or disconnected (None)."""
    global _config
    _config = cfg


def _load_config() -> dict | None:
    from database import SessionLocal  # imported here: database settings load at import time
    from services import integrations
    with SessionLocal() as db:
        return integrations.smtp_config(db)


def _current_config() -> dict | None:
    global _config
    if _config is _UNSET:
        try:
            _config = _load_config()
        except Exception:
            logger.exception("Could not load the SMTP settings; writing emails to the log")
            _config = None
    return _config


def _smtp_send(cfg: dict, to: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = cfg["from"], to, subject
    message.set_content(text)
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT) as smtp:
        if cfg.get("tls", True):
            smtp.starttls()
        if cfg.get("username"):
            smtp.login(cfg["username"], cfg.get("password") or "")
        smtp.send_message(message)


def test_send(cfg: dict, to: str) -> None:
    """Sends a test email with `cfg`; raises on any SMTP or network error (the caller reports the message)."""
    _smtp_send(cfg, to, "Acadmate test email", "Acadmate can send email through this server.")


def send(to: str, subject: str, text: str) -> None:
    cfg = _current_config()
    if cfg is None:
        logger.info("Email to %s | %s\n%s", to, subject, text)
    else:
        try:
            _smtp_send(cfg, to, subject, text)
        except Exception:
            logger.exception("Could not send email to %s (%s)", to, subject)
            record_failure()
            return
    _sent.append(now())


def send_all(mails: list[Mail]) -> None:
    for mail in mails:
        send(*mail)


def record_failure() -> None:
    _failures.append(now())


def sent_today() -> int:
    day = today()
    return sum(1 for at in _sent if at.astimezone(local_zone()).date() == day)


def health() -> tuple[str, str]:
    """("Healthy" | "Degraded", detail): Degraded when a send failed in the last hour."""
    cutoff = now() - HEALTH_WINDOW
    if any(at > cutoff for at in _failures):
        return "Degraded", "Delays of up to 15 minutes"
    return "Healthy", "Meeting confirmations, reminders and invites"
