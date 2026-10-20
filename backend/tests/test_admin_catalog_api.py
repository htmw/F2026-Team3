"""Admin courses & catalog over HTTP (spec 33): /api/v1/admin/catalog*. Service rules are in test_admin_catalog.py."""
import pytest

from conftest import login
from database import SessionLocal
from models import CatalogDraft
from test_foundation import assert_envelope

CATALOG = "/api/v1/admin/catalog"
JORDAN = "jordan.lee@pac.edu"
COURSE_KEYS = {"id", "code", "name", "type", "credits", "offered", "offerLabel", "prerequisites", "description", "draft"}
TERM_KEYS = {"id", "name", "startDate", "endDate", "registrationOpens", "lastAdd", "lastDrop", "isCurrent", "draft"}


def _clear_drafts():
    with SessionLocal() as db:
        db.query(CatalogDraft).delete()
        db.commit()


@pytest.fixture
def admin(client):
    _clear_drafts()
    assert login(client, JORDAN).status_code == 200
    yield client
    _clear_drafts()


def calls(client):
    """One request per route (bodies valid enough to reach the role check)."""
    return [
        client.get(f"{CATALOG}/summary"),
        client.get(f"{CATALOG}/courses"),
        client.post(f"{CATALOG}/courses", json={"code": "CS 699", "name": "X", "credits": 3}),
        client.put(f"{CATALOG}/courses/CS%20680", json={}),
        client.get(f"{CATALOG}/requirements"),
        client.put(f"{CATALOG}/requirements", json={"programId": 1, "groups": [{"id": 401, "courses": 2}]}),
        client.get(f"{CATALOG}/terms"),
        client.post(f"{CATALOG}/terms", json={"name": "Spring 2030", "startDate": "2030-01-20", "endDate": "2030-05-10"}),
        client.put(f"{CATALOG}/terms/5", json={}),
        client.post(f"{CATALOG}/publish"),
        client.delete(f"{CATALOG}/drafts"),
    ]


def test_catalog_routes_need_an_admin(client, as_user):
    for response in calls(client):
        assert_envelope(response, 401, "UNAUTHENTICATED")
    for role in ("student", "advisor"):
        as_user(role)
        for response in calls(client):
            assert_envelope(response, 403, "FORBIDDEN")


def test_summary_and_lists(admin):
    summary = admin.get(f"{CATALOG}/summary").json()
    assert summary == {"draftCount": 0, "catalogYear": "2026–27", "nextTerm": {"id": 5, "name": "Spring 2027"}}

    courses = admin.get(f"{CATALOG}/courses").json()["courses"]
    assert all(set(row) == COURSE_KEYS for row in courses)
    by_code = {row["code"]: row for row in courses}
    assert (by_code["CS 691"]["type"], by_code["CS 691"]["offerLabel"]) == ("Capstone", "Spring 27")
    assert by_code["CS 691"]["prerequisites"] == ["CS 600", "CS 620"]
    assert by_code["CS 650"]["offerLabel"] == "Not offered"
    assert [row["code"] for row in admin.get(f"{CATALOG}/courses", params={"q": "machine"}).json()["courses"]] == ["CS 680"]
    assert [row["code"] for row in admin.get(f"{CATALOG}/courses", params={"q": "cs680"}).json()["courses"]] == ["CS 680"]

    reqs = admin.get(f"{CATALOG}/requirements").json()
    assert reqs["totalCredits"] == 36 and reqs["program"] == {"id": 1, "name": "M.S. Computer Science"}
    assert reqs["groups"][0]["eligible"] == ["CS 501", "CS 510"]

    terms = admin.get(f"{CATALOG}/terms").json()
    assert all(set(row) == TERM_KEYS for row in terms["terms"]) and terms["nextTermId"] == 5
    spring = next(row for row in terms["terms"] if row["id"] == 5)
    assert (spring["registrationOpens"], spring["lastAdd"], spring["lastDrop"]) == ("2026-11-03", "2027-01-29", "2027-03-12")


def test_course_draft_round_trip(admin):
    response = admin.put(f"{CATALOG}/courses/CS%20650", json={"name": "Cloud Systems", "prerequisites": ["cs 620"]})
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["prerequisites"], body["draft"]) == ("Cloud Systems", ["CS 620"], True)
    assert admin.get(f"{CATALOG}/summary").json()["draftCount"] == 1
    assert admin.delete(f"{CATALOG}/drafts").status_code == 204
    assert admin.get(f"{CATALOG}/summary").json()["draftCount"] == 0


def test_course_errors(admin):
    assert_envelope(admin.put(f"{CATALOG}/courses/CS%20999", json={"name": "X"}), 404, "NOT_FOUND")
    error = assert_envelope(admin.put(f"{CATALOG}/courses/CS%20675", json={"prerequisites": ["CS 680"]}), 400, "BAD_REQUEST")
    assert error["message"] == "CS 675 can't require itself through CS 680."
    assert_envelope(admin.put(f"{CATALOG}/courses/CS%20675", json={"credits": 9}), 422, "VALIDATION_ERROR")
    assert_envelope(admin.put(f"{CATALOG}/courses/CS%20675", json={"name": None}), 422, "VALIDATION_ERROR")
    error = assert_envelope(admin.post(f"{CATALOG}/courses", json={"code": "cs-699", "name": "X", "credits": 3}),
                            422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "code"
    assert_envelope(admin.post(f"{CATALOG}/courses", json={"code": "CS 680", "name": "X", "credits": 3}), 409, "CONFLICT")
    created = admin.post(f"{CATALOG}/courses", json={"code": "cs  699", "name": "Special Topics", "credits": 3})
    assert created.status_code == 201 and created.json()["code"] == "CS 699"


def test_term_and_requirement_errors(admin):
    error = assert_envelope(admin.put(f"{CATALOG}/terms/5", json={"lastDrop": "2027-01-20"}), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "lastDrop"
    assert_envelope(admin.put(f"{CATALOG}/terms/999", json={"lastDrop": "2027-01-20"}), 404, "NOT_FOUND")
    assert_envelope(admin.put(f"{CATALOG}/requirements", json={"programId": 1, "groups": [{"id": 401, "courses": 21}]}),
                    422, "VALIDATION_ERROR")
    assert_envelope(admin.post(f"{CATALOG}/terms", json={"name": "Fall 2027", "startDate": "2030-08-20",
                                                         "endDate": "2030-12-10"}), 409, "CONFLICT")
    assert_envelope(admin.post(f"{CATALOG}/publish"), 409, "CONFLICT")


def test_requirements_draft(admin):
    response = admin.put(f"{CATALOG}/requirements", json={"programId": 1, "groups": [{"id": 401, "courses": 3}]})
    assert response.status_code == 200
    assert (response.json()["totalCredits"], response.json()["draft"]) == (39, True)
