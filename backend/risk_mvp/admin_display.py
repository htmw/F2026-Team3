"""Admin presentation helpers; no configuration changes or delivery attempts."""
from math import floor


def workload_percent(count, capacity):
    return min(100, floor(count / capacity * 100 + 0.5)) if capacity else 100


def email_health(db):
    from models import Integration
    from services import integrations, mailer
    row = db.get(Integration, "mail")
    state = integrations.status(row) if row is not None else "Off"
    if state == "Off":
        return "Off", "SMTP not connected; email delivery is disabled"
    if state == "Error":
        return "Down", "SMTP connection error; review Integrations"
    if state == "Degraded":
        return "Degraded", mailer.health()[1]
    return "Healthy", "SMTP connected; delivery is not verified by this status"
