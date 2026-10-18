"""Deletes audit events and AI conversations older than the retention settings (spec 36/37). Run daily from
backend/: python scripts/prune.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal  # noqa: E402
from services import audit, settings  # noqa: E402
from services.ai import retention  # noqa: E402


def main() -> int:
    with SessionLocal() as db:
        settings.apply_time_zone(db)
        events = audit.prune(db)
        threads = retention.prune_threads(db)
    print(f"Deleted {events} audit event{'' if events == 1 else 's'} and {threads} AI "
          f"conversation{'' if threads == 1 else 's'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
