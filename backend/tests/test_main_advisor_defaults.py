"""Default hours use existing scheduling, permissions and conflict rules."""
from datetime import date, time
import pytest
from models import Advisor, AdvisorAvailability, AuditEvent, Student, User, UserPreference
from services import meetings, advisor_meetings

@pytest.fixture
def owner(db, make_user, monkeypatch):
    monkeypatch.setenv("ACADMATE_ADVISOR_DEFAULT_HOURS", "true")
    user=make_user("advisor")
    row=Advisor(user_id=user.user_id)
    db.add(row);db.flush()
    return row

def test_weekday_defaults_are_read_only(db, owner):
    before=db.query(AdvisorAvailability).count()
    rows=meetings.office_windows(db,owner.user_id)
    assert [(w.weekday,w.start_time,w.end_time) for w in rows]==[(d,time(8),time(17)) for d in range(5)]
    assert all(w not in db for w in rows)
    assert len(meetings._windows(db,owner.user_id))==5
    assert db.query(AdvisorAvailability).count()==before
    assert advisor_meetings.office_hours(db,owner)["days"]==["Mon","Tue","Wed","Thu","Fri"]

def test_custom_hours_and_explicit_clear_override(db,owner):
    advisor_meetings.set_office_hours(db,owner,["Wed"],time(10),time(12),None)
    assert [(w.weekday,w.start_time,w.end_time) for w in meetings._windows(db,owner.user_id)]==[(2,time(10),time(12))]
    advisor_meetings.set_office_hours(db,owner,[],time(10),time(12),None)
    assert meetings.office_windows(db,owner.user_id)==[]
    db.query(AuditEvent).filter_by(action="office_hours.update",target_id=str(owner.advisor_id)).delete()
    db.flush()
    assert meetings._windows(db,owner.user_id)==[]

def test_explicit_booking_schedule_is_preserved(db,owner):
    db.add(AdvisorAvailability(staff_user_id=owner.user_id,weekday=1,start_time=time(9),end_time=time(10),kind="booking"));db.flush()
    assert [(w.weekday,w.start_time) for w in meetings._windows(db,owner.user_id)]==[(1,time(9))]
    assert meetings._books_during_office_hours(db,db.get(User,owner.user_id)) is True
    db.add(AdvisorAvailability(staff_user_id=owner.user_id,weekday=1,start_time=time(9),end_time=time(10),kind="office_hours"));db.flush()
    assert meetings._books_during_office_hours(db,db.get(User,owner.user_id)) is False

def test_explicit_booking_preference_is_preserved(db,owner):
    staff=db.get(User,owner.user_id)
    assert meetings._books_during_office_hours(db,staff) is True
    db.add(UserPreference(user_id=staff.user_id,data={"bookings":{"bookDuringOfficeHours":False}}));db.flush()
    assert meetings._books_during_office_hours(db,staff) is False

def test_disabled_and_nonadvisor_unchanged(db,owner,monkeypatch,make_user):
    nonadvisor=make_user("admin")
    assert meetings.office_windows(db,nonadvisor.user_id)==[]
    monkeypatch.setenv("ACADMATE_ADVISOR_DEFAULT_HOURS","false")
    assert meetings.office_windows(db,owner.user_id)==[]
    db.query(AuditEvent).filter_by(action="office_hours.update",target_id=str(owner.advisor_id)).delete()
    db.flush()
    assert meetings._windows(db,owner.user_id)==[]

def test_real_slots_use_school_time_and_lead_time(db,owner):
    staff=db.get(User,owner.user_id);student=db.query(Student).order_by(Student.student_id).first()
    days=meetings._week_slots(db,student,staff,date(2026,9,28))
    assert all(not slots for day,slots in days if day < date(2026,10,1)) or all(taken for day,slots in days if day < date(2026,10,1) for _,taken,_ in slots)
    friday=days[4][1]
    assert friday and any(not taken for _,taken,_ in friday)
    assert all(time(8)<=start.astimezone(meetings.local_zone()).time()<time(17) for start,_,_ in friday)
    assert sum(len(slots) for _,slots in days)==90

def test_default_advisor_is_discoverable_only_under_existing_permission(db,owner):
    student=db.query(Student).order_by(Student.student_id).first()
    staff=db.get(User,owner.user_id)
    staff.bookable=False;db.flush()
    assert owner.user_id not in {u.user_id for u in meetings._staff_members(db,student)[0]}
    staff.bookable=True;db.flush()
    assert owner.user_id in {u.user_id for u in meetings._staff_members(db,student)[0]}
