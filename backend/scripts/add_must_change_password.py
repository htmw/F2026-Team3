"""Adds users.must_change_password (spec 31 revision 2) to an existing database without resetting it.
Safe to run more than once. Run from backend/: python scripts/add_must_change_password.py
(reset_db.py / the tests create the column from models.py, so they don't need this.)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from database import engine  # noqa: E402

SQL = "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false"


def main() -> int:
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print(f"users.must_change_password is in place on {engine.url.database}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
