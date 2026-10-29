"""Advisor settings (spec 27): the advisor's title and office plus their notification, approval and booking switches.
Name and email stay on PATCH /users/me (spec 17).

Where each setting lives: the title is `users.title`, the office `advisors.office`; the switches are in the user's
preferences JSON (`advisorNotify`, `approvals`, `bookings`), next to `bookings.autoConfirm`, so bookable staff without
an advisors row (the Graduate office) share the same booking rules (spec 18 reads them per staff member)."""
from sqlalchemy.orm import Session

from models import Advisor, User
from services import audit, preferences
from services.auth import user_payload

WINDOWS = {"1 week ahead": 7, "2 weeks ahead": 14, "4 weeks ahead": 28}
WINDOW_LABELS = {days: label for label, days in WINDOWS.items()}


def get(db: Session, advisor: Advisor) -> dict:
    user = db.get(User, advisor.user_id)
    prefs = preferences.get(db, user)
    bookings = prefs["bookings"]
    return {
        "profile": {"fullName": user.name, "email": user.email, "initials": user_payload(user)["initials"]},
        "advisor": {
            "title": user.title, "department": advisor.department, "office": advisor.office,
            "meetingLength": bookings["meetingLength"],
            "bookingWindow": WINDOW_LABELS.get(bookings["bookingWindowDays"], "2 weeks ahead"),
            "autoConfirm": bookings["autoConfirm"],
        },
        "notify": prefs["advisorNotify"],
        "approvals": prefs["approvals"],
    }


def update(db: Session, advisor: Advisor, data: dict) -> dict:
    """data: the fields the caller sent (title, office, meetingLength, bookingWindow, autoConfirm, notify, approvals).
    Audits advisor.settings with the before/after of the advisor fields; commits."""
    user = db.get(User, advisor.user_id)
    before = get(db, advisor)["advisor"]
    if "title" in data:
        user.title = (data["title"] or "").strip() or None
    if "office" in data:
        advisor.office = (data["office"] or "").strip() or None

    patch: dict = {}
    bookings = {}
    if data.get("meetingLength") is not None:
        bookings["meetingLength"] = data["meetingLength"]
    if data.get("bookingWindow") is not None:
        bookings["bookingWindowDays"] = WINDOWS[data["bookingWindow"]]
    if data.get("autoConfirm") is not None:
        bookings["autoConfirm"] = data["autoConfirm"]
    if bookings:
        patch["bookings"] = bookings
    for key, stored in (("notify", "advisorNotify"), ("approvals", "approvals")):
        values = {k: v for k, v in (data.get(key) or {}).items() if v is not None}
        if values:
            patch[stored] = values

    after = {**before, "title": user.title, "office": advisor.office}
    if bookings:
        after.update({"meetingLength": bookings.get("meetingLength", before["meetingLength"]),
                      "bookingWindow": data.get("bookingWindow") or before["bookingWindow"],
                      "autoConfirm": bookings.get("autoConfirm", before["autoConfirm"])})
    changes = {field: [before[field], after[field]] for field in after if field != "department" and before[field] != after[field]}
    if changes:
        audit.record(db, user, "advisor.settings", f"{user.name} updated their advising settings",
                     target=("advisor", advisor.advisor_id), changes=changes)
    if patch:
        preferences.update(db, user, patch)  # deep-merges, audits prefs.update and commits
    else:
        db.commit()
    return get(db, advisor)
