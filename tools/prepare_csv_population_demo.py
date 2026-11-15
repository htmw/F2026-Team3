"""Build a NEW local CSV-population demo; never alters the existing main demo."""
from pathlib import Path
import argparse, csv, json, os, sys, hashlib
from datetime import datetime, timezone, date
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
DB='acadmate_risk_csv_sprint2'
URL=f'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/{DB}'
DAY='2027-02-16'
FILES=('users','programs','students','advisors','courses','enrollments','advisor_student_assignments','program_requirements')

def bootstrap(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'): raise ValueError('Isolated snapshot required')
    os.environ.update(DATABASE_URL=URL,ACADMATE_RISK_DATABASE_URL=URL,ACADMATE_TODAY=DAY,ACADMATE_RISK_MVP_ENABLED='true',OMP_NUM_THREADS='2')
    os.chdir(snapshot/'backend')
    sys.path[:0]=[str(snapshot/'backend'),str(ROOT/'backend'),str(ROOT/'ml/src')]
    import services
    services.__path__.append(str(ROOT/'backend/services'))
    return snapshot

def source():
    data={}
    for name in FILES:
        with (ROOT/f'data/synthetic/{name}.csv').open(encoding='utf-8-sig',newline='') as f:data[name]=list(csv.DictReader(f))
    return data

def hashes():return {name:hashlib.sha256((ROOT/f'data/synthetic/{name}.csv').read_bytes()).hexdigest() for name in FILES}

def prepare(snapshot):
    snapshot=bootstrap(snapshot)
    from sqlalchemy import create_engine,select,func,text,inspect
    from sqlalchemy.orm import Session
    import models as m
    from core.security import hash_password
    from seed_data import seed_terms,DEMO_PASSWORD,reset_sequences
    from risk_mvp import main_data
    from risk_mvp.models import RISK_TABLES
    data=source();before=hashes()
    expected={'users':105,'students':100,'advisors':4,'programs':1,'courses':30,'enrollments':800,'advisor_student_assignments':100,'program_requirements':3}
    assert {k:len(v) for k,v in data.items()}==expected
    marker=snapshot/'csv-population-manifest.json'
    admin=create_engine(URL.rsplit('/',1)[0]+'/postgres',isolation_level='AUTOCOMMIT')
    with admin.connect() as conn:
        if not conn.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'),{'name':DB}):conn.exec_driver_sql('CREATE DATABASE '+DB)
    admin.dispose()
    engine=create_engine(URL)
    if inspect(engine).has_table('users'):
        with engine.connect() as conn:count=conn.scalar(select(func.count()).select_from(m.User))
        if count:
            if not marker.exists():raise ValueError('Refusing populated database without CSV provenance marker')
            manifest=json.loads(marker.read_text())
            assert manifest['csv_sha256']==before
            if manifest.get('state')=='complete':print('Existing verified CSV demo preserved.');return
    m.Base.metadata.create_all(engine)
    with Session(engine) as db:
        if not db.scalar(select(func.count()).select_from(m.User)):
            seed_terms(db)
            terms={t.name:t for t in db.scalars(select(m.Term))}
            # Current date matches the CSV active-enrollment term, not the old demo date.
            password=hash_password(DEMO_PASSWORD)
            for row in data['users']:
                parts=row['name'].split();role=row['role']
                db.add(m.User(user_id=int(row['user_id']),name=row['name'],first_name=parts[0],last_name=' '.join(parts[1:]),email=row['email'],role=role,is_active=row['is_active'].lower()=='true',password_hash=password,bookable=role=='advisor',title='Advisor' if role=='advisor' else None))
            for row in data['programs']:db.add(m.Program(program_id=int(row['program_id']),program_name=row['program_name'],total_required_credits=Decimal(row['total_required_credits'])))
            db.flush()
            for row in data['advisors']:db.add(m.Advisor(advisor_id=int(row['advisor_id']),user_id=int(row['user_id']),capacity=40,department='Computer Science'))
            types={int(cid):('Capstone' if row['group_name']=='Capstone' else 'Core' if row['group_name']=='Core' else 'Elective') for row in data['program_requirements'] for cid in json.loads(row['eligible_course_ids'])}
            for row in data['courses']:db.add(m.Course(**{k:int(row[k]) for k in ['course_id']},course_code=row['course_code'],course_name=row['course_name'],credits=Decimal(row['credits']),type=types[int(row['course_id'])]))
            student_terms={}
            for row in data['enrollments']:
                sid=int(row['student_id']);term=terms[row['term']]
                if sid not in student_terms or term.start_date<student_terms[sid].start_date:student_terms[sid]=term
            for row in data['students']:db.add(m.Student(student_id=int(row['student_id']),user_id=int(row['user_id']),name=row['name'],email=row['email'],program_id=int(row['program_id']),student_number='CSV'+row['student_id'],start_term_id=student_terms[int(row['student_id'])].id))
            db.flush()
            for i,row in enumerate(data['program_requirements']):
                credits=Decimal(row['required_credits']);assert credits%3==0
                db.add(m.ProgramRequirement(requirement_id=int(row['requirement_id']),program_id=int(row['program_id']),group_name=row['group_name'],required_credits=credits,required_courses=int(credits/3),credits_per_course=3,sort=i,eligible_courses_ids=json.loads(row['eligible_course_ids']),requires_approval=False))
            pairs=sorted({(int(e['course_id']),e['term']) for e in data['enrollments']})
            sections={}
            for i,(cid,term) in enumerate(pairs,1):
                db.add(m.CourseOffering(course_id=cid,term_id=terms[term].id))
                section=m.CourseSection(id=i,course_id=cid,term_id=terms[term].id)
                db.add(section);sections[cid,term]=i
            db.flush()
            for row in data['enrollments']:
                db.add(m.Enrollment(enrollment_id=int(row['enrollment_id']),student_id=int(row['student_id']),course_id=int(row['course_id']),term=row['term'],status=row['status'],grade=row['grade'] or None,grade_points=Decimal(row['grade_points']) if row['grade_points'] else None,section_id=sections[int(row['course_id']),row['term']]))
            for row in data['advisor_student_assignments']:db.add(m.AdvisorStudentAssignment(student_id=int(row['student_id']),advisor_id=int(row['advisor_id']),updated_at=datetime.fromisoformat(row['updated_at'])))
            db.flush();reset_sequences(db);db.commit()
            marker.write_text(json.dumps({'state':'academic_loaded','csv_sha256':before,'database':DB,'demo_day':DAY},indent=2),encoding='utf-8')
    records=main_data.snapshot(engine)
    bundle=main_data.generate(records)
    main_data.load(engine,bundle,records)
    # Project the same simulated assessment/submission identities into student UI tables.
    cutoff=datetime.combine(date.fromisoformat(DAY),datetime.max.time(),timezone.utc)
    offerings={x['id']:x for x in bundle['tables']['risk_course_offerings']}
    assessments={x['id']:x for x in bundle['tables']['risk_assessments']}
    versions={x['assessment_id']:x for x in bundle['tables']['risk_assessment_versions']}
    submitted={(x['enrollment_id'],x['assessment_id']):x for x in bundle['tables']['risk_submission_versions']}
    crosswalk=[]
    with Session(engine) as db:
        terms={x.name:x.id for x in db.scalars(select(m.Term))}
        sections={(x.course_id,x.term_id):x.id for x in db.scalars(select(m.CourseSection))}
        for aid,a in assessments.items():
            off=offerings[a['offering_id']];v=versions[aid]
            db.add(m.Assignment(id=aid,section_id=sections[off['course_id'],terms[off['term']]],title=a['label'],short_title=a['label'],type='Individual',due_at=main_data.parse(v['due_at']),weight_text='Not specified',description='Synthetic LMS demonstration coursework. No grading weight or score is assumed.'))
            crosswalk.append({'risk_assessment_id':aid,'assignment_id':aid,'course_id':off['course_id'],'term':off['term']})
        db.flush()
        for enrollment in db.scalars(select(m.Enrollment)):
            off=next(o for o in offerings.values() if o['course_id']==enrollment.course_id and o['term']==enrollment.term)
            for aid,a in assessments.items():
                if a['offering_id']!=off['id']:continue
                sub=submitted.get((enrollment.enrollment_id,aid))
                observed=sub and main_data.parse(sub['known_at'])<=cutoff and main_data.parse(sub['submitted_at'])<=cutoff
                db.add(m.AssignmentSubmission(assignment_id=aid,student_id=enrollment.student_id,status='submitted' if observed else 'todo',submitted_at=main_data.parse(sub['submitted_at']) if observed else None))
        db.flush();reset_sequences(db);db.commit()
    counts={}
    with engine.connect() as conn:
        for name in FILES:counts[name]=conn.scalar(select(func.count()).select_from(m.Base.metadata.tables[name]))
    assert counts==expected,(counts,expected)
    assert hashes()==before
    manifest={'state':'complete','database':DB,'demo_day':DAY,'counts':counts,'csv_sha256':before,'academic_sha256':main_data.fingerprint(records),'risk_counts':bundle['manifest']['counts'],'crosswalk':crosswalk,'assumptions':['All CSV academic values preserved; placeholder CSV hashes replaced only in local auth storage by the existing demo password hash','First/last names split for UI; no academic outcomes or graduation dates invented','Existing main academic calendar reused; February 16 2027 is fixed as-of day','Course sections created only for CSV course/term pairs; no instructor or timetable invented','Student assignments mirror risk assessment IDs/deadlines and only submissions known by the fixed demo date; no scores or weights invented','Advisor capacities use existing model default 40, not an academic policy']}
    marker.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (snapshot/'csv-risk-manifest.json').write_text(json.dumps(bundle['manifest'],indent=2),encoding='utf-8')
    print(json.dumps({'database':DB,'demo_day':DAY,'counts':counts,'risk_counts':bundle['manifest']['counts']},indent=2))
    engine.dispose()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);prepare(p.parse_args().snapshot)
