"""Opt-in review-candidate availability defaults; reads only, no schema/seed writes."""
import os
from datetime import time


def install(service):
    if getattr(service, "_advisor_defaults_installed", False):
        return
    service._advisor_defaults_installed = True
    original_windows = service._windows
    original_office = service._office_windows
    original_books = service._books_during_office_hours
    original_staff = service._staff_members

    def enabled():
        return os.environ.get("ACADMATE_ADVISOR_DEFAULT_HOURS") == "true"

    def advisor(db, user_id):
        from models import Advisor
        return db.query(Advisor).filter_by(user_id=user_id).one_or_none()

    def office(db, user_id):
        from models import AdvisorAvailability, AuditEvent
        rows = original_office(db, user_id)
        if rows or not enabled():
            return rows
        owner = advisor(db, user_id)
        if owner is None:
            return rows
        from models import UserPreference
        pref = db.get(UserPreference, user_id)
        if pref and (pref.data or {}).get("advisorOfficeHoursConfigured"):
            return []
        # Honor earlier explicit clears too; new saves also retain a durable preference marker.
        changed = db.query(AuditEvent.id).filter_by(action="office_hours.update", target_type="advisor",
                                                   target_id=str(owner.advisor_id)).first()
        if changed:
            return []
        # Transient read-only rows: no persistence, invented room or appointment.
        return [AdvisorAvailability(id=-(user_id * 10 + day + 1), staff_user_id=user_id,
                    weekday=day, start_time=time(8), end_time=time(17), kind="office_hours", location=owner.office)
                for day in range(5)]

    def windows(db, user_id):
        rows = original_windows(db, user_id)
        if rows or not enabled() or advisor(db, user_id) is None:
            return rows
        # When no separate appointment schedule exists, follow effective office hours.
        return office(db, user_id)

    def books(db, staff):
        from models import UserPreference
        if not enabled() or advisor(db, staff.user_id) is None or original_office(db, staff.user_id):
            return original_books(db, staff)
        pref = db.get(UserPreference, staff.user_id)
        stored = (pref.data or {}).get("bookings", {}) if pref else {}
        if "bookDuringOfficeHours" in stored:
            return bool(stored["bookDuringOfficeHours"])
        return True

    def staff_members(db, student):
        from models import User
        if not enabled():
            return original_staff(db, student)
        users, mine = original_staff(db, student)
        seen = {u.user_id for u in users}
        # Retain existing staff permissions; include advisors with effective default/custom hours.
        for user in db.query(User).filter(User.is_active.is_(True), User.role == "advisor").all():
            if user.user_id not in seen and (user.bookable or user.user_id in mine) and windows(db, user.user_id):
                users.append(user)
        users.sort(key=lambda u: (u.user_id not in mine, u.role != "advisor", u.name))
        return users, mine

    service._windows = windows
    service._office_windows = office
    service.office_windows = office
    service._books_during_office_hours = books
    service._staff_members = staff_members


def mark_configured(db, advisor):
    """Save explicit configuration, including empty days, only during an authorized schedule update."""
    if os.environ.get("ACADMATE_ADVISOR_DEFAULT_HOURS") != "true":
        return
    from models import UserPreference
    row=db.get(UserPreference, advisor.user_id)
    if row is None:
        db.add(UserPreference(user_id=advisor.user_id, data={"advisorOfficeHoursConfigured": True}))
    else:
        row.data={**(row.data or {}), "advisorOfficeHoursConfigured": True}
    db.flush()
