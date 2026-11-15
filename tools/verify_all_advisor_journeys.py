"""Read-only checks for every advisor/advisee in the isolated main demo."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_main_risk_demo import configure
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot',type=Path,required=True)
configure(parser.parse_args().snapshot)
from database import SessionLocal
from models import Advisor,Student,AdvisorStudentAssignment
from sqlalchemy import select,text
from services import advisor_dashboard,advisees,student_record,badges
from core.deps import advisor_can_see
from core.errors import ApiError
from models import User
from risk_mvp import service

report={'advisors':[],'records_checked':0,'denied_assignment_checks':0}
with SessionLocal() as db:
    db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
    db.execute(text('SET TRANSACTION READ ONLY'))
    all_students=db.scalars(select(Student).order_by(Student.student_id)).all()
    assigned=set(db.scalars(select(AdvisorStudentAssignment.student_id)))
    report['students_without_advisor']=len([s for s in all_students if s.student_id not in assigned])
    with patch.object(service.MODEL,'_load',side_effect=AssertionError('No inference model loading in list audit')):
        for advisor in db.scalars(select(Advisor).order_by(Advisor.advisor_id)):
            dashboard=advisor_dashboard.build(db,advisor)
            listing=advisees.list_for(db,advisor)
            attention=advisees.list_for(db,advisor,'Needs attention')
            clear=advisees.list_for(db,advisor,'On track')
            graduating=advisees.list_for(db,advisor,'Graduating')
            ids={r['studentId'] for r in listing['rows']}
            expected={s.student_id for s in advisees.advisees(db,advisor)}
            assert ids==expected
            flagged={r['studentId'] for r in listing['rows'] if r['risk']!='Low'}
            assert flagged=={r['studentId'] for r in attention['rows']}
            missing={r['studentId'] for r in listing['rows'] if r['status']=='No academic records'}
            assert ids-flagged-missing=={r['studentId'] for r in clear['rows']}
            assert missing=={r['studentId'] for r in advisees.list_for(db,advisor,'No academic records')['rows']}
            assert not missing & {r['studentId'] for r in clear['rows']}
            stats={s['key']:int(s['value']) for s in dashboard['stats']}
            assert stats['advisees']==len(ids)
            assert stats['attention']==len(flagged)==advisees.attention_count(db,advisor)
            assert badges.badges_for(db,db.get(User,advisor.user_id))['advisees']==len(flagged)
            assert len(dashboard['attention'])==min(3,len(flagged))
            assert {r['studentId'] for r in graduating['rows'] if r['risk']!='Low'}<=flagged
            for row in listing['rows']:
                student=db.get(Student,row['studentId'])
                concern=advisees.risk_for(student,advisees.risk_context(db,[student]))[1]
                if concern: assert next(r for r in listing['rows'] if r['studentId']==student.student_id)['flag']==concern
                record=student_record.record(db,advisor,student.student_id)
                assert record['student']['id']==student.student_id
                assert record['hasAcademicRecords']==(student.student_id not in missing)
                assert record['concernSummary']==concern
                for preview in dashboard['attention']:
                    if preview['studentId']==student.student_id: assert preview['flag']==concern
                searched=advisees.list_for(db,advisor,'All',student.name)
                assert student.student_id in {r['studentId'] for r in searched['rows']}
                report['records_checked']+=1
            for student in all_students:
                if student.student_id not in ids:
                    try:advisor_can_see(db,advisor.advisor_id,student.student_id)
                    except ApiError as exc:assert exc.status==403
                    else:raise AssertionError('Unassigned record was allowed')
                    report['denied_assignment_checks']+=1
            report['advisors'].append({'advisor_id':advisor.advisor_id,'advisees':len(ids),'attention':len(flagged),'no_flags':len(clear['rows']),'no_academic_records':len(missing),'graduating':len(graduating['rows'])})
print(json.dumps(report,indent=2))
print('PASS: all advisor journeys consistent; read-only; no model loading')
