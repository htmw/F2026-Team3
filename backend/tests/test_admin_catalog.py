"""Admin courses & catalog (spec 33): drafts, cycle checks, date rules and publish. Tests that publish put the seeded
catalog back with a second publish, and every test starts and ends without drafts."""
from datetime import date

import pytest

from core.errors import ApiError
from database import SessionLocal
from models import AuditEvent, CatalogDraft, Program, ProgramRequirement, Term, User
from services import admin_catalog as ac
from services import catalog
from services.ai import plans

SPRING = 5  # Spring 2027, the seeded next term
ML = 22  # CS 680


@pytest.fixture
def admin(db):
    db.query(CatalogDraft).delete()
    db.commit()
    yield db.get(User, 3)
    db.rollback()
    db.query(CatalogDraft).delete()
    db.commit()


def test_courses_overlay_drafts_until_publish(db, admin):
    ac.save_course_draft(db, admin, "CS 680", {"offered": False})
    row = next(r for r in ac.courses(db)["courses"] if r["code"] == "CS 680")
    assert (row["offered"], row["offerLabel"], row["draft"]) == (False, "Not offered", True)
    assert ac.summary(db)["draftCount"] == 1
    # Students still see the published catalog.
    assert catalog.is_offered(db, ML, SPRING)
    assert [r["code"] for r in plans.validate(db, [{"code": "CS 680"}], "Spring 2027")] == ["CS 680"]

    try:
        result = ac.publish(db, admin)
        assert result == {"published": 1, "message": ac.PUBLISHED}
        assert ac.summary(db)["draftCount"] == 0
        assert not catalog.is_offered(db, ML, SPRING)
        assert plans.validate(db, [{"code": "CS 680"}], "Spring 2027") == []
        event = db.query(AuditEvent).filter(AuditEvent.action == "catalog.publish").order_by(AuditEvent.id.desc()).first()
        assert event.changes == {"courses": 1, "requirements": 0, "terms": 0}
    finally:
        ac.save_course_draft(db, admin, "CS 680", {"offered": True})
        ac.publish(db, admin)
    assert catalog.is_offered(db, ML, SPRING)


def test_saving_the_published_value_drops_the_draft(db, admin):
    ac.save_course_draft(db, admin, "CS 650", {"name": "Cloud Systems"})
    assert ac.summary(db)["draftCount"] == 1
    ac.save_course_draft(db, admin, "CS 650", {"name": "Cloud Computing"})
    assert ac.summary(db)["draftCount"] == 0


def test_prerequisite_cycles_are_refused(db, admin):
    with pytest.raises(ApiError) as err:
        ac.save_course_draft(db, admin, "CS 675", {"prerequisites": ["CS 680"]})  # CS 680 already needs CS 675
    assert (err.value.status, err.value.message) == (400, "CS 675 can't require itself through CS 680.")
    with pytest.raises(ApiError) as err:
        ac.save_course_draft(db, admin, "CS 675", {"prerequisites": ["CS 675"]})
    assert err.value.message == "CS 675 can't require itself."
    # A drafted edge counts too.
    ac.save_course_draft(db, admin, "CS 665", {"prerequisites": ["CS 680"]})
    with pytest.raises(ApiError) as err:
        ac.save_course_draft(db, admin, "CS 675", {"prerequisites": ["CS 665"]})
    assert err.value.message == "CS 675 can't require itself through CS 665."


def test_unknown_prerequisite_is_a_field_error(db, admin):
    with pytest.raises(ApiError) as err:
        ac.save_course_draft(db, admin, "CS 675", {"prerequisites": ["CS 999"]})
    assert err.value.status == 422 and err.value.details[0]["field"] == "prerequisites"


def test_new_course_is_a_draft_until_publish(db, admin):
    row = ac.add_course(db, admin, {"code": "CS 699", "name": "Special Topics", "credits": 3, "type": "Elective"})
    assert (row["id"], row["draft"], row["offered"]) == (None, True, False)
    with pytest.raises(ApiError) as err:
        ac.add_course(db, admin, {"code": "CS 699", "name": "Again", "credits": 3, "type": "Elective"})
    assert err.value.status == 409
    with pytest.raises(ApiError) as err:
        ac.add_course(db, admin, {"code": "CS 680", "name": "Again", "credits": 3, "type": "Elective"})
    assert err.value.status == 409


def test_requirements_total_follows_the_steppers(db, admin):
    before = ac.requirements(db)
    assert [(g["label"], g["courses"]) for g in before["groups"]] == [
        ("Foundation", 2), ("Core courses", 4), ("Electives", 5), ("Capstone", 1)]
    assert before["totalCredits"] == 36 and before["catalogYear"] == "2026–27"

    draft = ac.save_requirements_draft(db, admin, {"program_id": 1, "groups": [{"id": 403, "courses": 6}]})
    assert (draft["totalCredits"], draft["draft"]) == (39, True)
    assert db.get(Program, 1).total_required_credits == 36  # not yet published
    try:
        ac.publish(db, admin)
        db.expire_all()
        assert db.get(Program, 1).total_required_credits == 39
        req = db.get(ProgramRequirement, 403)
        assert (req.required_courses, req.required_credits) == (6, 18)
    finally:
        ac.save_requirements_draft(db, admin, {"program_id": 1, "groups": [{"id": 403, "courses": 5}]})
        ac.publish(db, admin)
    assert db.get(Program, 1).total_required_credits == 36


def test_requirement_group_must_belong_to_the_program(db, admin):
    with pytest.raises(ApiError) as err:
        ac.save_requirements_draft(db, admin, {"program_id": 1, "groups": [{"id": 999, "courses": 1}]})
    assert err.value.status == 422 and err.value.details[0]["field"] == "groups"


def test_term_date_rules(db, admin):
    with pytest.raises(ApiError) as err:
        ac.save_term_draft(db, admin, SPRING, {"last_drop": date(2027, 1, 20)})  # before the last day to add
    assert err.value.details[0]["field"] == "lastDrop"
    with pytest.raises(ApiError) as err:
        ac.save_term_draft(db, admin, SPRING, {"last_add": date(2027, 1, 2)})
    assert err.value.details[0]["field"] == "lastAdd"
    with pytest.raises(ApiError) as err:
        ac.save_term_draft(db, admin, SPRING, {"end_date": date(2027, 1, 1)})
    assert err.value.details[0]["field"] == "endDate"

    row = ac.save_term_draft(db, admin, SPRING, {"last_drop": date(2027, 3, 19)})
    assert (row["lastDrop"], row["draft"]) == (date(2027, 3, 19), True)
    assert db.get(Term, SPRING).last_drop == date(2027, 3, 12)


def test_create_term_rejects_overlaps(db, admin):
    with pytest.raises(ApiError) as err:
        ac.create_term(db, admin, {"name": "Spring 2027", "start_date": date(2028, 1, 1), "end_date": date(2028, 5, 1)})
    assert err.value.status == 409
    with pytest.raises(ApiError) as err:
        ac.create_term(db, admin, {"name": "Winter 2027", "start_date": date(2028, 1, 1), "end_date": date(2028, 5, 1)})
    assert err.value.details[0]["field"] == "name"
    with pytest.raises(ApiError) as err:
        ac.create_term(db, admin, {"name": "Spring 2028", "start_date": date(2027, 12, 1), "end_date": date(2028, 5, 1)})
    assert (err.value.status, err.value.message) == (409, "Spring 2028 overlaps Fall 2027.")


def test_publish_without_drafts_is_a_conflict(db, admin):
    with pytest.raises(ApiError) as err:
        ac.publish(db, admin)
    assert err.value.status == 409


def test_discard_removes_every_draft(db, admin):
    ac.save_course_draft(db, admin, "CS 650", {"name": "Cloud Systems"})
    ac.save_term_draft(db, admin, SPRING, {"last_drop": date(2027, 3, 19)})
    ac.discard(db, admin)
    assert ac.summary(db)["draftCount"] == 0
    with SessionLocal() as other:
        assert other.query(CatalogDraft).count() == 0
