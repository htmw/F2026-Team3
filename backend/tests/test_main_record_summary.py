from models import Student
from services.advisees import risk_context, risk_for

def test_record_concern_uses_shared_rules(client, as_user, db):
    as_user('advisor')
    for sid in (101,108,113):
        student=db.get(Student,sid)
        expected=risk_for(student,risk_context(db,[student]))[1]
        response=client.get(f'/api/v1/advisor/advisees/{sid}')
        assert response.status_code==200
        assert response.json()['concernSummary']==expected

def test_concern_does_not_bypass_assignment_guard(client, as_user):
    as_user('advisor')
    assert client.get('/api/v1/advisor/advisees/104').status_code==403
