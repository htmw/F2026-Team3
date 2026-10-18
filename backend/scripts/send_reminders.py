"""Sends tomorrow's meeting reminders (spec 18). Run daily from backend/: python scripts/send_reminders.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal  # noqa: E402
from services import settings  # noqa: E402
from services.reminders import send_due_reminders  # noqa: E402


def main() -> int:
    with SessionLocal() as db:
        settings.apply_time_zone(db)
        count = send_due_reminders(db)
    print(f"Sent reminders for {count} meeting{'' if count == 1 else 's'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
