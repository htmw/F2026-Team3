"""Spec 01 acceptance: error envelope, auth dependencies, clock, reset guard, existing endpoint."""
import subprocess
import sys
from datetime import date

import pytest
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from conftest import BACKEND
from core import time as clock
from core.config import settings
from core.deps import advisor_can_see, get_current_student, get_current_user, require_role
from core.errors import ApiError
from main import app
from models import Student, User

# Throwaway routes that exercise the handlers and dependencies.
probe = APIRouter(prefix="/api/v1/__test")


class EchoIn(BaseModel):
    email: EmailStr
    n: int


@probe.post("/echo")
def echo(body: EchoIn):
    return body


@probe.get("/boom")
def boom():
    raise RuntimeError("secret internals")


@probe.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.user_id}


@probe.get("/admin-only")
def admin_only(user: User = Depends(require_role("admin"))):
    return {"id": user.user_id}


@probe.get("/my-student")
def my_student(student: Student = Depends(get_current_student)):
    return {"studentId": student.student_id}


app.include_router(probe)


def assert_envelope(response, status: int, code: str):
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], list)
    return error


def test_unknown_route_is_404_envelope(client):
    assert_envelope(client.get("/api/v1/nope"), 404, "NOT_FOUND")


def test_wrong_method_is_405_envelope(client):
    response = client.delete("/api/v1/health")
    assert_envelope(response, 405, "METHOD_NOT_ALLOWED")
    assert "GET" in response.headers.get("allow", "")


def test_validation_error_lists_fields(client):
    error = assert_envelope(client.post("/api/v1/__test/echo", json={"email": "nope", "n": "x"}), 422, "VALIDATION_ERROR")
    assert error["message"] == "Check the highlighted fields."
    assert {"field": "email", "message": "Enter a valid email address."} in error["details"]
    assert {"field": "n", "message": "Enter a number."} in error["details"]


def test_missing_field_message(client):
    error = assert_envelope(client.post("/api/v1/__test/echo", json={"email": "a@pac.edu"}), 422, "VALIDATION_ERROR")
    assert error["details"] == [{"field": "n", "message": "This field is required."}]


def test_unhandled_error_is_500_without_internals(client):
    response = client.get("/api/v1/__test/boom")
    assert_envelope(response, 500, "INTERNAL")
    assert "secret internals" not in response.text and "Traceback" not in response.text


def test_no_cookie_is_401(client):
    assert_envelope(client.get("/api/v1/__test/me"), 401, "UNAUTHENTICATED")
    client.cookies.set(settings.SESSION_COOKIE, "made-up-token")
    assert_envelope(client.get("/api/v1/__test/me"), 401, "UNAUTHENTICATED")


def test_wrong_role_is_403(client, as_user):
    as_user("student")
    assert_envelope(client.get("/api/v1/__test/admin-only"), 403, "FORBIDDEN")
    admin = as_user("admin")
    response = client.get("/api/v1/__test/admin-only")
    assert response.status_code == 200 and response.json() == {"id": admin.user_id}


def test_current_student(client, as_user):
    as_user("student")
    assert client.get("/api/v1/__test/my-student").json() == {"studentId": 101}
    as_user("advisor")
    assert_envelope(client.get("/api/v1/__test/my-student"), 403, "FORBIDDEN")


def test_advisor_can_see(db):
    advisor_can_see(db, 201, 101)
    with pytest.raises(ApiError) as caught:
        advisor_can_see(db, 201, 999)
    assert caught.value.status == 403


def test_academic_profile(client, as_user):
    as_user("admin")
    response = client.get("/api/v1/students/101/academic-profile")
    assert response.status_code == 200
    student = response.json()["student"]
    assert student["name"] == "Amara Okafor"
    assert student["gpa"] == 3.73 and student["completed_credits"] == 21
    assert_envelope(client.get("/api/v1/students/999/academic-profile"), 404, "NOT_FOUND")


def test_cors_allows_frontend_origin(client):
    response = client.get("/api/v1/health", headers={"Origin": settings.FRONTEND_ORIGIN})
    assert response.headers["access-control-allow-origin"] == settings.FRONTEND_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_clock_honours_pinned_today(monkeypatch):
    monkeypatch.setattr(settings, "ACADMATE_TODAY", date(2026, 10, 1))
    assert clock.today() == date(2026, 10, 1)
    assert clock.now().tzinfo is not None
    # The pinned date holds in school time at any hour (the UTC date can be the next day in the evening).
    assert clock.now().astimezone(clock.local_zone()).date() == date(2026, 10, 1)
    assert clock.iso_z(clock.now()).endswith("Z")


def test_reset_db_requires_yes():
    result = subprocess.run([sys.executable, "reset_db.py"], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 1
    assert "--yes" in result.stdout
