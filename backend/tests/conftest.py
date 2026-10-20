"""Test setup: points the app at a separate test database, rebuilds and seeds it once per run.

TEST_DATABASE_URL (backend/.env) names that database; when unset it is DATABASE_URL with "_test" appended
to the database name. Create it once: docker exec acadmate-fastapi-db createdb -U acadmate acadmate_test
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")


def _test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    url = make_url(os.environ["DATABASE_URL"])
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


# Must happen before anything imports core.config / database.
os.environ["DATABASE_URL"] = _test_database_url()
# The seed's current term and week depend on "today"; pin it so date-dependent assertions are stable.
os.environ["ACADMATE_TODAY"] = "2026-10-01"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from core.deps import get_current_user  # noqa: E402
from core.security import hash_password  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models import Base, LoginAttempt, User  # noqa: E402
from seed_data import DEMO_PASSWORD, seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    try:
        Base.metadata.drop_all(bind=engine)
    except OperationalError as exc:
        pytest.exit(f"Test database unavailable ({engine.url.render_as_string(hide_password=True)}): {exc.orig}", returncode=1)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
        db.commit()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    """A fresh client per test, so session cookies never leak between tests."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_login_attempts():
    """Rate limits count recent attempts; start every test from zero."""
    yield
    with SessionLocal() as session:
        session.query(LoginAttempt).delete()
        session.commit()


def login(client, email: str, password: str = DEMO_PASSWORD, remember: bool = False):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password, "remember": remember})


_HASH = hash_password(DEMO_PASSWORD)
_made = 0


@pytest.fixture
def make_user():
    """make_user(role="student") creates a throwaway active user with DEMO_PASSWORD (for tests that change data)."""
    def create(role: str = "student") -> User:
        global _made
        _made += 1
        with SessionLocal() as session:
            user = User(name=f"Test User{_made}", first_name="Test", last_name=f"User{_made}",
                        email=f"test.user{_made}@pac.edu", password_hash=_HASH, role=role)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
        return user
    return create


@pytest.fixture
def as_user():
    """as_user("student" | "advisor" | "admin") signs the client in as that seeded user, until the test ends.
    For real cookie sign-in use login(client, email)."""
    def sign_in(role: str) -> User:
        with SessionLocal() as session:
            user = session.query(User).filter(User.role == role).order_by(User.user_id).first()
            session.expunge(user)
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield sign_in
    app.dependency_overrides.pop(get_current_user, None)
