"""Sends tomorrow's meeting reminders (spec 18) and advisors' reminders about requests waiting more than 3 days
(spec 27). Run daily from backend/: python scripts/send_reminders.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal  # noqa: E402
from services import approvals, settings  # noqa: E402
from services.reminders import send_due_reminders  # noqa: E402


def main() -> int:
    with SessionLocal() as db:
        settings.apply_time_zone(db)
        count = send_due_reminders(db)
        advisors = approvals.remind_stale(db)
    print(f"Sent reminders for {count} meeting{'' if count == 1 else 's'}.")
    print(f"Reminded {advisors} advisor{'' if advisors == 1 else 's'} about waiting requests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
