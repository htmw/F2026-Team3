"""Missing enrollment records must not imply reassuring academic evidence."""
from models import Advisor
from services import advisees, student_record, advisor_reports

def test_sparse_students_are_separate_from_no_flags(db):
    advisor=db.get(Advisor,203)
    missing=advisees.list_for(db,advisor,'No academic records')
    assert {row['studentId'] for row in missing['rows']}=={105,106}
    assert not {105,106} & {row['studentId'] for row in advisees.list_for(db,advisor,'On track')['rows']}
    for sid in (105,106):
        assert student_record.record(db,advisor,sid)['hasAcademicRecords'] is False
    assert student_record.record(db,advisor,104)['hasAcademicRecords'] is True
    counts={item['label']:item['count'] for item in advisor_reports.by_status(advisees.caseload(db,advisor)[0])}
    assert counts['No academic records']==2
    assert counts['On track']==1  # Diego has records; the plain test DB has no demo sidecars

def test_new_category_serializes_in_public_schema(db):
    listing=advisees.list_for(db,db.get(Advisor,203),'No academic records')
    from schemas import advisor
    candidates=[getattr(advisor,name) for name in dir(advisor) if name.endswith('Out') and hasattr(getattr(advisor,name),'model_fields') and 'tabs' in getattr(advisor,name).model_fields]
    assert candidates
    candidates[0].model_validate(listing)
