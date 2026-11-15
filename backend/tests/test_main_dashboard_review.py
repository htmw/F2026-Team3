"""Regression checks run with main's fixtures in the isolated test database."""
from datetime import timedelta
from core.time import now
from models import Advisor, Meeting, Student, User
from services.advisees import RiskContext, risk_for, last_contact


def test_missing_sign_in_does_not_claim_observed_inactivity():
    student = Student(student_id=999, user_id=999, name="Example Student", program_id=1)
    context = RiskContext(users={999: User(first_name="Example", name="Example Student")})
    level, text = risk_for(student, context)
    assert level == "Medium"
    assert "No sign-in history is recorded" in text
    assert "21+ days" not in text
    context.last_sign_in[999] = now() - timedelta(days=30)
    assert "signed in to AcadMate for 21+ days" in risk_for(student, context)[1]


def test_only_completed_meetings_count_as_contact(db):
    advisor = db.get(Advisor, 201)
    student = db.get(Student, 101)
    # Roll back all test alterations; this test uses only the dedicated test DB.
    try:
        from models import ConversationParticipant
        db.query(ConversationParticipant).filter(ConversationParticipant.user_id == student.user_id).delete()
        meetings = db.query(Meeting).filter(Meeting.staff_user_id == advisor.user_id, Meeting.student_id == 101).all()
        for meeting in meetings:
            meeting.status = "confirmed"
            meeting.starts_at = now() - timedelta(days=1)
            meeting.ends_at = now() - timedelta(days=1) + timedelta(minutes=30)
        db.flush()
        assert 101 not in last_contact(db, advisor, [student])
        assert meetings, "Seeded meeting required"
        meetings[0].status = "completed"
        db.flush()
        assert 101 in last_contact(db, advisor, [student])
    finally:
        db.rollback()
