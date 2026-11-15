"""Seeded credit totals independently checked against enrollment/course records."""
import pytest
from models import Student, Enrollment, Course, Program
from risk_mvp.graduation import projection

@pytest.mark.parametrize("student_id,earned,current,expected", [
    (101,21,9,"May 2027"),
    (107,9,0,"May 2028"),
    (108,18,6,"December 2027"),
    (109,6,3,"May 2028"),
    (110,6,0,"December 2028"),
    (111,6,0,"December 2028"),
    (112,6,0,"December 2028"),
    (113,27,9,"December 2026"),
])
def test_seeded_credit_projection(db, student_id, earned, current, expected):
    student = db.get(Student, student_id)
    assert float(db.get(Program, student.program_id).total_required_credits) == 36
    rows = db.query(Enrollment, Course).join(Course, Enrollment.course_id == Course.course_id).filter(Enrollment.student_id == student_id).all()
    completed = {c.course_id: float(c.credits) for e,c in rows if e.status == "completed" and (e.grade or "").upper() != "F"}
    underway = {c.course_id: float(c.credits) for e,c in rows if e.status == "in_progress" and e.term == "Fall 2026" and c.course_id not in completed}
    assert sum(completed.values()) == earned
    assert sum(underway.values()) == current
    # Expected dates are explicit: current Fall credits, then 9 credits each Spring/Fall.
    assert projection(db, student)["label"] == expected
