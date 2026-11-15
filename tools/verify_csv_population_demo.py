"""Read-only CSV integration checks plus authenticated local API smoke tests."""
from pathlib import Path
import argparse,json,sys,urllib.request,http.cookiejar
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,source,hashes,DAY

def verify(snapshot):
    snap=bootstrap(snapshot)
    from database import SessionLocal
    import models as m
    from sqlalchemy import select,func,text
    from risk_mvp import service,main_data
    from risk_mvp.models import Link,Offering,AssessmentVersion,Submission
    from seed_data import DEMO_PASSWORD
    data=source();manifest=json.loads((snap/'csv-population-manifest.json').read_text())
    assert hashes()==manifest['csv_sha256']
    models={'users':m.User,'programs':m.Program,'students':m.Student,'advisors':m.Advisor,'courses':m.Course,'enrollments':m.Enrollment,'advisor_student_assignments':m.AdvisorStudentAssignment,'program_requirements':m.ProgramRequirement}
    checked=0;current=Counter();replays=0
    cutoff=datetime.fromisoformat(DAY+'T23:59:59.999999+00:00')
    with SessionLocal() as db:
        db.connection(execution_options={'isolation_level':'REPEATABLE READ'});db.execute(text('SET TRANSACTION READ ONLY'))
        for name,model in models.items():
            assert db.scalar(select(func.count()).select_from(model))==len(data[name])
            key=list(model.__table__.primary_key.columns)[0].name
            for row in data[name]:
                actual=db.get(model,int(row[key]))
                for field,expected in row.items():
                    if field=='password_hash':continue
                    value=getattr(actual,'eligible_courses_ids' if field=='eligible_course_ids' else field)
                    if expected=='': assert value is None,(name,field)
                    elif field=='eligible_course_ids':assert value==json.loads(expected)
                    elif isinstance(value,bool):assert value==(expected.lower()=='true')
                    elif isinstance(value,(int,float,Decimal)):assert Decimal(str(value))==Decimal(expected),(name,field)
                    elif isinstance(value,datetime):assert value==datetime.fromisoformat(expected)
                    else:assert str(value)==expected,(name,field,value,expected)
                checked+=1
        for aid in [int(x['advisor_id']) for x in data['advisors']]:assert db.scalar(select(func.count()).select_from(m.AdvisorStudentAssignment).where(m.AdvisorStudentAssignment.advisor_id==aid))==25
        linked={x.enrollment_id:x for x in db.scalars(select(Link))}
        assert len(linked)==800
        # Shared assignment IDs and deadlines, then all observed student submissions.
        versions={x.assessment_id:x for x in db.scalars(select(AssessmentVersion))}
        subs={(x.enrollment_id,x.assessment_id):x for x in db.scalars(select(Submission))}
        task_subs=0
        for a in db.scalars(select(m.Assignment)):assert a.due_at==versions[a.id].due_at
        for e in db.scalars(select(m.Enrollment).order_by(m.Enrollment.enrollment_id)):
            off=db.get(Offering,linked[e.enrollment_id].offering_id)
            result=service.assessment(db,e.enrollment_id,cutoff);current[result['status']]+=1
            replay=service.assessment(db,e.enrollment_id,off.starts_at+__import__('datetime').timedelta(days=29,microseconds=-1))
            assert replay['status']=='scored_research_demo';assert 0<=replay['research_risk_probability']<=1;replays+=1
            tasks=db.scalars(select(m.Assignment).where(m.Assignment.section_id==e.section_id)).all()
            for a in tasks:
                stored=db.scalar(select(m.AssignmentSubmission).where(m.AssignmentSubmission.assignment_id==a.id,m.AssignmentSubmission.student_id==e.student_id))
                original=subs.get((e.enrollment_id,a.id))
                observed=original and original.known_at<=cutoff and original.submitted_at<=cutoff
                assert stored is not None
                assert stored.status==('submitted' if observed else 'todo')
                assert stored.submitted_at==(original.submitted_at if observed else None)
                task_subs+=1
    assert current['scored_research_demo']==179,current
    api='http://127.0.0.1:8004/api/v1'
    def login(email):
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        op.open(urllib.request.Request(api+'/auth/login',data=json.dumps({'email':email,'password':DEMO_PASSWORD}).encode(),headers={'Content-Type':'application/json'})).read()
        return lambda path:json.load(op.open(api+path))
    users={x['user_id']:x for x in data['users']};student_rows={int(x['student_id']):x for x in data['students']}
    api_records=0;denials=0;api_scores=0
    for advisor in data['advisors']:
        get=login(users[advisor['user_id']]['email'])
        listing=get('/advisor/advisees');assert listing['total']==25
        dashboard=get('/advisor/dashboard');assert int(next(s['value'] for s in dashboard['stats'] if s['key']=='advisees'))==25
        assigned={int(x['student_id']) for x in data['advisor_student_assignments'] if x['advisor_id']==advisor['advisor_id']}
        assert {r['studentId'] for r in listing['rows']}==assigned
        report=get('/advisor/reports');assert int(next(s['value'] for s in report['stats'] if s['label']=='Advisees'))==25
        for sid in assigned:
            record=get('/advisor/advisees/'+str(sid));assert record['student']['fullName']==student_rows[sid]['name'];assert record['hasAcademicRecords'];api_records+=1
        sid=next(s for s in assigned if any(int(e['student_id'])==s and e['status']=='in_progress' for e in data['enrollments']))
        insights=get('/advisor/research/students/'+str(sid)+'/insights')
        eid=insights['active_enrollments'][0]['enrollment_id']
        result=get('/advisor/research/enrollments/'+str(eid)+'/risk-assessment?cutoff='+insights['demo_cutoff']+'&include_explanation=true')
        assert result['status']=='scored_research_demo';assert result['explanation']['status']=='available';api_scores+=1
        foreign=next(s for s in student_rows if s not in assigned)
        try:get('/advisor/advisees/'+str(foreign));raise AssertionError('Unassigned student accessible')
        except urllib.error.HTTPError as error:assert error.code==403;denials+=1
    student_api=0
    for student in data['students']:
        get=login(student['email'])
        for endpoint in ('dashboard','courses','assignments','degree-audit'):get('/students/me/'+endpoint);student_api+=1
    admin=next(x for x in data['users'] if x['role']=='admin');get=login(admin['email'])
    get('/admin/overview');advisors=get('/admin/advisors')
    result={'passed':True,'academic_records_preserved':checked,'csv_hashes_unchanged':True,'current_assessments':dict(current),'day28_real_model_scores':replays,'assignment_submission_links_checked':task_subs,'advisor_student_records_checked':api_records,'advisor_explanation_smokes':api_scores,'denied_unassigned_checks':denials,'student_api_responses':student_api,'admin_api_smoke':'passed'}
    (snap/'csv-population-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);verify(p.parse_args().snapshot)
