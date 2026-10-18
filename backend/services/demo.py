"""Reset demo data (spec 37, DEMO_MODE only): drops and recreates every table, re-runs the seed and keeps the calling
admin signed in by restoring their user row (when it isn't a seeded one) and their session."""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core.config import settings as env
from core.errors import conflict, not_found
from core.security import sha256_hex
from core.time import DEFAULT_ZONE, set_zone
from database import SessionLocal, engine
from models import Base, User, UserSession
from services import audit, mailer
from services.ai import recommend

logger = logging.getLogger("acadmate.demo")

MESSAGE = "Demo data reset."


def _row(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(type(obj)).column_attrs}


def reset(db: Session, admin: User, raw_token: str | None, ip: str | None = None) -> dict:
    if not env.DEMO_MODE:
        raise not_found("Page")
    import seed_data  # the top-level seed script

    user = _row(admin)
    session = None
    if raw_token:
        found = db.query(UserSession).filter(UserSession.token_hash == sha256_hex(raw_token)).one_or_none()
        session = _row(found) if found is not None else None
    # Release this request's connection so dropping the tables isn't blocked by our own locks.
    db.rollback()
    db.close()

    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            Base.metadata.drop_all(bind=conn)
            Base.metadata.create_all(bind=conn)
    except OperationalError as exc:
        logger.warning("Demo reset could not drop the tables: %s", exc.orig)
        raise conflict("Someone is still using the database. Try again in a moment.") from None

    with SessionLocal() as fresh:
        seed_data.seed(fresh)
        fresh.flush()
        restored = fresh.get(User, user["user_id"])
        if restored is None:  # a non-seed admin: bring the account back with the same id
            restored = User(**user)
            fresh.add(restored)
            fresh.flush()
        if session is not None:  # a new id: the old one may belong to a seeded session now
            fresh.add(UserSession(**{k: v for k, v in session.items() if k != "id"}))
        fresh.flush()
        seed_data.reset_sequences(fresh)
        audit.record(fresh, restored, "demo.reset", "Reset the demo data", ("settings", "institution"), ip=ip)
        fresh.commit()

    # In-memory state that pointed at the old data.
    recommend._cache.clear()
    mailer.configure(None)
    set_zone(DEFAULT_ZONE)
    return {"message": MESSAGE}
