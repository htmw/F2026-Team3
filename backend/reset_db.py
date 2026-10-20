"""Drops and recreates every table from models.py (there are no migrations). Then run: python seed_data.py"""
import sys

from database import engine
from models import Base


def main() -> int:
    target = engine.url.render_as_string(hide_password=True)
    if "--yes" not in sys.argv[1:]:
        print(f"This drops every Acadmate table in {target}. Re-run with --yes.")
        return 1
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print(f"Tables recreated in {target}. Next: python seed_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
