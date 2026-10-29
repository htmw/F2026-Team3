"""Spec 02 Phase A acceptance: login, sessions, logout, signup, password reset / invite, badges, config."""
import logging
import re
from datetime import timedelta

from conftest import login
from core.config import settings
from core.security import sha256_hex
from core.time import now
from models import Advisor, AuditEvent, AuthToken, Student, User, UserSession
from seed_data import DEMO_INVITE_TOKEN
from services import auth, mailer

AMARA = "amara.okafor@pac.edu"
SARAH = "sarah.smith@pac.edu"
JORDAN = "jordan.lee@pac.edu"


def error_code(response):
    return response.json()["error"]["code"]


def session_for(db, client) -> UserSession:
    raw = client.cookies.get(settings.SESSION_COOKIE)
    return db.query(UserSession).filter(UserSession.token_hash == sha256_hex(raw)).one()


# --- login / me -------------------------------------------------------------------------------------------------

def test_login_sets_cookie_and_returns_user(client):
    response = login(client, AMARA)
    assert response.status_code == 200
    assert response.json() == {
        "user": {"id": 1, "role": "student", "email": AMARA, "fullName": "Amara Okafor", "firstName": "Amara",
                 "preferredName": "Amara", "initials": "AO", "mfaEnabled": False, "googleLinked": False},
        "home": "/student",
    }
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{settings.SESSION_COOKIE}=")
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower() and "Path=/" in cookie
    assert "Max-Age" not in cookie  # not remembered → browser-session cookie
    assert client.get("/api/v1/auth/me").json() == {"user": response.json()["user"]}


def test_login_is_case_insensitive_and_routes_by_role(client):
    assert login(client, "  Sarah.Smith@PAC.edu").json()["home"] == "/advisor"
    assert login(client, JORDAN).json()["home"] == "/admin"


def test_remember_me_keeps_session_30_days(client, db):
    response = login(client, AMARA, remember=True)
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    remaining = session_for(db, client).expires_at - now()
    assert timedelta(days=29, hours=23) < remaining <= timedelta(days=30)


def test_wrong_password_and_unknown_email_look_the_same(client):
    wrong = login(client, AMARA, "wrong-password")
    unknown = login(client, "nobody@pac.edu")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert error_code(wrong) == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == "That email and password don't match."


def test_five_failures_lock_the_email(client):
    for _ in range(5):
        assert login(client, AMARA, "wrong-password").status_code == 401
    blocked = login(client, AMARA)  # correct password, still blocked
    assert blocked.status_code == 429 and error_code(blocked) == "RATE_LIMITED"
    assert login(client, SARAH).status_code == 200  # other accounts unaffected


def test_deactivated_account(client):
    response = login(client, "sam.rivera@pac.edu")
    assert response.status_code == 403 and error_code(response) == "DEACTIVATED"


def test_empty_password_message(client):
    response = client.post("/api/v1/auth/login", json={"email": AMARA, "password": ""})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "password", "message": "Enter your password."}]


# --- sessions ---------------------------------------------------------------------------------------------------

def test_logout_revokes_session(client):
    login(client, AMARA)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert 'acadmate_session=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/logout").status_code == 204  # idempotent


def test_logged_out_token_cannot_be_reused(client, db):
    login(client, AMARA)
    raw = client.cookies.get(settings.SESSION_COOKIE)
    client.post("/api/v1/auth/logout")
    client.cookies.set(settings.SESSION_COOKIE, raw)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401 and error_code(me) == "UNAUTHENTICATED"


def test_expired_session_is_rejected(client, db):
    login(client, AMARA)
    session = session_for(db, client)
    session.expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_idle_session_slides_forward(client, db):
    login(client, AMARA)
    session = session_for(db, client)
    session.expires_at = now() + timedelta(minutes=10)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 200
    db.refresh(session)
    assert session.expires_at - now() > timedelta(hours=1, minutes=59)


def test_session_of_deactivated_user_stops_working(client, db, make_user):
    user = make_user()
    login(client, user.email)
    db.get(User, user.user_id).is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


# --- signup -----------------------------------------------------------------------------------------------------

def test_signup_creates_student_and_signs_in(client, db):
    response = client.post("/api/v1/auth/signup", json={"name": "  Lena   Park ", "email": "Lena.Park@pac.edu", "password": "longenough"})
    assert response.status_code == 201
    body = response.json()
    assert body["home"] == "/student"
    assert body["user"]["fullName"] == "Lena Park" and body["user"]["initials"] == "LP" and body["user"]["email"] == "lena.park@pac.edu"
    student = db.query(Student).filter(Student.user_id == body["user"]["id"]).one()
    assert student.program_id == 1 and student.student_id > 101
    assert client.get("/api/v1/auth/me").status_code == 200


def test_signup_rejects_taken_email(client):
    response = client.post("/api/v1/auth/signup", json={"name": "Amara Two", "email": AMARA, "password": "longenough"})
    assert response.status_code == 409 and error_code(response) == "EMAIL_TAKEN"


def test_signup_requires_school_email(client):
    response = client.post("/api/v1/auth/signup", json={"name": "Out Sider", "email": "out.sider@gmail.com", "password": "longenough"})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"field": "email", "message": "Use your school email (pac.edu)."}]


def test_signup_short_password_message(client):
    response = client.post("/api/v1/auth/signup", json={"name": "Short Pw", "email": "short.pw@pac.edu", "password": "short"})
    assert response.status_code == 422
    assert {"field": "password", "message": "Use at least 8 characters for your password."} in response.json()["error"]["details"]


# --- password reset / invite ------------------------------------------------------------------------------------

def reset_link(caplog) -> str:
    match = re.search(r"/reset-password\?token=([\w-]+)", caplog.text)
    assert match, "reset link was not logged"
    return match.group(1)


def test_reset_for_unknown_email_looks_successful(client, caplog):
    with caplog.at_level(logging.INFO, logger="acadmate.mail"):
        response = client.post("/api/v1/auth/password-reset", json={"email": "nobody@pac.edu"})
    assert response.status_code == 202 and response.json() == {"ok": True}
    assert "reset-password" not in caplog.text


def test_password_reset_flow(client, make_user, caplog):
    user = make_user()
    other_browser = client.__class__(client.app)
    assert login(other_browser, user.email).status_code == 200

    with caplog.at_level(logging.INFO, logger="acadmate.mail"):
        assert client.post("/api/v1/auth/password-reset", json={"email": user.email}).status_code == 202
    token = reset_link(caplog)

    assert client.get(f"/api/v1/auth/password-reset/{token}").json() == {"email": user.email, "purpose": "reset"}
    confirm = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "brand-new-pass"})
    assert confirm.status_code == 204

    assert other_browser.get("/api/v1/auth/me").status_code == 401  # existing sessions revoked
    assert login(client, user.email).status_code == 401  # old password
    assert login(client, user.email, "brand-new-pass").status_code == 200

    reused = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "another-pass"})
    assert reused.status_code == 410 and error_code(reused) == "LINK_EXPIRED"
    assert client.get(f"/api/v1/auth/password-reset/{token}").status_code == 410


def test_new_reset_request_invalidates_older_link(client, make_user, caplog):
    user = make_user()
    with caplog.at_level(logging.INFO, logger="acadmate.mail"):
        client.post("/api/v1/auth/password-reset", json={"email": user.email})
        first = reset_link(caplog)
        caplog.clear()
        client.post("/api/v1/auth/password-reset", json={"email": user.email})
    assert client.get(f"/api/v1/auth/password-reset/{first}").status_code == 410


def test_reset_requests_are_rate_limited(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/password-reset", json={"email": "spam.target@pac.edu"}).status_code == 202
    response = client.post("/api/v1/auth/password-reset", json={"email": "spam.target@pac.edu"})
    assert response.status_code == 429 and error_code(response) == "RATE_LIMITED"


def test_invite_activates_account(client):
    link = client.get(f"/api/v1/auth/password-reset/{DEMO_INVITE_TOKEN}")
    assert link.json() == {"email": "priya.natarajan@pac.edu", "purpose": "invite"}
    assert login(client, "priya.natarajan@pac.edu").status_code == 401  # no password yet
    confirm = client.post("/api/v1/auth/password-reset/confirm", json={"token": DEMO_INVITE_TOKEN, "password": "priya-password"})
    assert confirm.status_code == 204
    response = login(client, "priya.natarajan@pac.edu", "priya-password")
    assert response.status_code == 200 and response.json()["home"] == "/advisor"


def test_unknown_link(client):
    response = client.get("/api/v1/auth/password-reset/not-a-token")
    assert response.status_code == 410 and response.json()["error"]["message"] == "This link is invalid or has expired."


# --- badges, config, audit, guarded endpoint --------------------------------------------------------------------

def test_badges_per_role(client):
    assert client.get("/api/v1/users/me/badges").status_code == 401
    login(client, AMARA)
    assert client.get("/api/v1/users/me/badges").json() == {"badges": {"assignments": 2, "messages": 3}}  # due within a week (spec 15), unread (16)
    login(client, SARAH)
    assert client.get("/api/v1/users/me/badges").json() == {"badges": {"advisees": 4, "approvals": 5, "messages": 3}}  # specs 21, 23
    login(client, JORDAN)
    assert client.get("/api/v1/users/me/badges").json() == {"badges": {}}


def test_public_config(client):
    assert client.get("/api/v1/auth/config").json() == {
        "googleEnabled": False, "accent": "#0F766E", "institutionName": "Pace University", "selfSignup": True}


def test_sign_ins_are_audited(client, db):
    login(client, SARAH, "wrong-password")
    login(client, SARAH)
    actions = [(e.action, e.result) for e in db.query(AuditEvent).filter(AuditEvent.actor_id == 2).order_by(AuditEvent.id)]
    assert actions[-2:] == [("auth.login_failed", "failed"), ("auth.login", "success")]


def test_academic_profile_access(client, db, make_user):
    path = "/api/v1/students/101/academic-profile"
    assert client.get(path).status_code == 401
    login(client, AMARA)
    assert client.get(path).status_code == 403
    login(client, SARAH)
    assert client.get(path).status_code == 200
    login(client, JORDAN)
    assert client.get(path).status_code == 200

    other_advisor = make_user("advisor")
    db.add(Advisor(user_id=other_advisor.user_id))
    db.commit()
    login(client, other_advisor.email)
    response = client.get(path)
    assert response.status_code == 403 and error_code(response) == "FORBIDDEN"


# --- invite / reset helpers for admin users (spec 31) ---------------------------------------------------------------

def test_name_from_email():
    assert auth.name_from_email("priya.natarajan@pac.edu") == "Priya Natarajan"
    assert auth.name_from_email("j_doe-smith+cs@pac.edu") == "J Doe Smith Cs"
    assert auth.name_from_email("x@pac.edu") == "X"


def test_issue_invite_waits_for_the_caller(client, db, make_user, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda *mail: sent.append(mail))
    user = db.get(User, make_user("advisor").user_id)

    first = auth.issue_invite(db, user, "Jordan Lee")
    db.commit()
    assert sent == []  # nothing is mailed until the caller sends it
    first_token = re.search(r"token=([\w-]+)", first.text).group(1)
    assert first.to == user.email and first.subject == "You're invited to Acadmate"
    assert first.text.startswith("Jordan Lee invited you to Acadmate.")

    second = auth.issue_invite(db, user, "Jordan Lee")
    db.commit()
    mailer.send_all([second])
    assert sent == [tuple(second)]
    second_token = re.search(r"token=([\w-]+)", second.text).group(1)
    assert client.get(f"/api/v1/auth/password-reset/{first_token}").status_code == 410  # older link stops working
    assert client.get(f"/api/v1/auth/password-reset/{second_token}").json() == {"email": user.email, "purpose": "invite"}
    token = db.query(AuthToken).filter(AuthToken.token_hash == sha256_hex(second_token)).one()
    assert timedelta(days=6, hours=23) < token.expires_at - token.created_at <= timedelta(days=7, minutes=1)


def test_issue_reset_link_rolls_back_cleanly(client, db, make_user):
    user = db.get(User, make_user().user_id)
    mail = auth.issue_reset_link(db, user)
    db.rollback()  # the caller's transaction failed: the link must not exist
    token = re.search(r"token=([\w-]+)", mail.text).group(1)
    assert client.get(f"/api/v1/auth/password-reset/{token}").status_code == 410
