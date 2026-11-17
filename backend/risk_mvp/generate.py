"""Deterministic sidecar data; original academic CSVs are read-only."""
import argparse,csv,hashlib,json,random
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import insert,select
from .models import Base,RISK_TABLES

ROOT=Path(__file__).resolve().parents[2]
CALENDAR={'Fall 2025':'2025-09-01','Spring 2026':'2026-01-12','Summer 2026':'2026-05-18','Fall 2026':'2026-08-31','Spring 2027':'2027-01-11'}
PATTERNS=['high','moderate','declining','late','missed','improving','feed_gap']
def stamp(t):return t.isoformat()
def parse(t):return datetime.fromisoformat(t)

def generate(seed=20261104,academic=ROOT/'data/synthetic'):
    with (academic/'enrollments.csv').open(newline='',encoding='utf-8') as stream:
        enrollments=list(csv.DictReader(stream))
    tables={t.name:[] for t in RISK_TABLES}
    def add(name,**row):
        if name!='risk_enrollment_offerings':row={'id':len(tables[name])+1,**row}
        tables[name].append(row);return row
    offerings={};assessments={}
    for course,term in sorted({(int(r['course_id']),r['term']) for r in enrollments}):
        start=parse(CALENDAR[term]).replace(tzinfo=timezone.utc)
        off=add('risk_course_offerings',course_id=course,term=term,starts_at=stamp(start),ends_at=stamp(start+timedelta(days=112)),timezone='UTC',known_at=stamp(start-timedelta(days=14)))
        offerings[course,term]=off
        assessments[off['id']]=[]
        if term=='Spring 2027':
            for index,due in enumerate([7,14,21,35,49,63,77]):
                a=add('risk_assessments',offering_id=off['id'],label=f'Coursework {index+1}',kind='TMA')
                add('risk_assessment_versions',assessment_id=a['id'],version=1,due_at=stamp(start+timedelta(days=due,hours=18)),max_score=100.,known_at=stamp(start))
                assessments[off['id']].append((a,due))
    for r in sorted(enrollments,key=lambda r:int(r['enrollment_id'])):
        eid=int(r['enrollment_id']);off=offerings[int(r['course_id']),r['term']];start=parse(off['starts_at'])
        rng=random.Random(int(hashlib.sha256(f'{seed}:{eid}'.encode()).hexdigest()[:16],16))
        pattern=PATTERNS[int(hashlib.sha256(f'{seed}:student:{r["student_id"]}'.encode()).hexdigest()[:8],16)%len(PATTERNS)]
        add('risk_enrollment_offerings',enrollment_id=eid,offering_id=off['id'],registered_at=stamp(start-timedelta(days=7)),known_at=stamp(start-timedelta(days=7)),pattern=pattern)
        effective=start if r['status']=='in_progress' else parse(off['ends_at'])
        add('risk_enrollment_history',enrollment_id=eid,status=r['status'],grade=r['grade'] or None,grade_points=float(r['grade_points']) if r['grade_points'] else None,effective_at=stamp(effective),known_at=stamp(effective))
        if r['status']!='in_progress':continue
        for day in range(85):
            probability=.85 if pattern=='high' else .55
            if pattern=='declining':probability=max(.08,.9-day/90)
            if pattern=='missed':probability=.15
            if rng.random()<probability:
                event=start+timedelta(days=day,hours=12)
                add('risk_activity_events',enrollment_id=eid,source_event_id=f'synthetic:{seed}:{eid}:{day}',occurred_at=stamp(event),known_at=stamp(event+timedelta(days=2 if day%19==0 else 0)),count=rng.randint(5,60),event_type='synthetic_resource_interaction')
        for a,due in assessments[off['id']]:
            if rng.random()<(.55 if pattern=='missed' else .08):continue
            delay=rng.choice([1,2,4]) if pattern=='late' else rng.choice([-2,-1,0,0,1])
            submitted=start+timedelta(days=due+delay,hours=15)
            # Variable explicitly synthetic grading observations, not institutional policy.
            graded=submitted+timedelta(days=rng.randint(1,5))
            score=max(0,min(100,rng.gauss(65+due*.25 if pattern=='improving' else 72,15)))
            common=dict(enrollment_id=eid,assessment_id=a['id'],submitted_at=stamp(submitted),is_banked=False)
            add('risk_submission_versions',**common,version=1,known_at=stamp(submitted),grade_available_at=None,score=None,status='submitted')
            add('risk_submission_versions',**common,version=2,known_at=stamp(graded),grade_available_at=stamp(graded),score=round(score,2),status='graded')
        for day in [7,14,21,28,35,42,49,56,63,70,77,84]:
            cutoff=start+timedelta(days=day+1)-timedelta(microseconds=1)
            for source in ['activity','submissions','schedule']:
                add('risk_source_coverage',enrollment_id=eid,source=source,starts_at=stamp(start),through_at=stamp(cutoff),known_at=stamp(cutoff),complete=not(pattern=='feed_gap' and source=='activity'))
    manifest={'schema_version':'1.0','source_kind':'synthetic_lms_demo','seed':seed,'generator_version':'1',
        'demo_cutoff':'2027-02-08T23:59:59.999999+00:00',
        'original_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(academic.glob('*.csv'))},
        'counts':{k:len(v) for k,v in tables.items()},
        'warning':'Synthetic flow testing only, not model accuracy evidence; UTC calendar and 112-day courses are demo assumptions'}
    validate(tables,enrollments)
    return {'manifest':manifest,'tables':tables}

def validate(tables,enrollments):
    e={int(r['enrollment_id']):r for r in enrollments};o={r['id']:r for r in tables['risk_course_offerings']}
    links={r['enrollment_id']:r for r in tables['risk_enrollment_offerings']}
    a={r['id']:r for r in tables['risk_assessments']};versions={r['assessment_id']:r for r in tables['risk_assessment_versions']}
    if set(links)!=set(e):raise ValueError('Enrollment links incomplete')
    for eid,l in links.items():
        if o[l['offering_id']]['course_id']!=int(e[eid]['course_id']):raise ValueError('Course linkage mismatch')
    for s in tables['risk_submission_versions']:
        if a[s['assessment_id']]['offering_id']!=links[s['enrollment_id']]['offering_id']:raise ValueError('Submission offering mismatch')
        if parse(s['known_at'])<parse(s['submitted_at']):raise ValueError('Submission availability before occurrence')
        if s['score'] is not None and not 0<=s['score']<=versions[s['assessment_id']]['max_score']:raise ValueError('Score outside assessment bounds')
    for event in tables['risk_activity_events']:
        if event['enrollment_id'] not in e or event['count']<0:raise ValueError('Invalid activity record')
        if parse(event['known_at'])<parse(event['occurred_at']):raise ValueError('Activity availability before occurrence')

def load(engine,bundle,academic=ROOT/'data/synthetic'):
    """Bootstrap EMPTY disposable local DB only. Never alters existing data."""
    if engine.url.host not in {'127.0.0.1','localhost'} or not engine.url.database.startswith('acadmate_risk_demo'):
        raise ValueError('Disposable loopback database required')
    for name,expected in bundle['manifest']['original_sha256'].items():
        if hashlib.sha256((academic/name).read_bytes()).hexdigest()!=expected:raise ValueError('Original dataset provenance mismatch')
    with (academic/'enrollments.csv').open(newline='',encoding='utf-8') as stream:validate(bundle['tables'],list(csv.DictReader(stream)))
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        if db.execute(select(Base.metadata.tables['students'].c.student_id).limit(1)).first():raise ValueError('Refusing nonempty database')
        for t in Base.metadata.sorted_tables:
            if t.name.startswith('risk_'):rows=bundle['tables'][t.name]
            else:
                with (academic/(t.name+'.csv')).open() as stream:raw=list(csv.DictReader(stream))
                rows=[]
                for row in raw:
                    converted={}
                    for c in t.columns:
                        v=row.get(c.name)
                        if v in [None,'']:converted[c.name]=None;continue
                        kind=c.type.__class__.__name__.lower()
                        if kind=='array':v=json.loads(v)
                        elif kind=='boolean':v=v.lower()=='true'
                        elif kind=='integer':v=int(v)
                        elif kind=='numeric':v=float(v)
                        elif kind=='datetime':v=parse(v)
                        converted[c.name]=v
                    rows.append(converted)
            if rows:
                values=[]
                for row in rows:
                    values.append({c.name:parse(row[c.name]) if isinstance(row.get(c.name),str) and isinstance(c.type,__import__('sqlalchemy').DateTime) else row.get(c.name) for c in t.columns})
                db.execute(insert(t),values)
        # Explicit deterministic IDs must advance local PostgreSQL sequences.
        from sqlalchemy import text
        for t in Base.metadata.sorted_tables:
            for column in t.primary_key.columns:
                seq=db.execute(text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':t.name,'column':column.name}).scalar()
                if seq:
                    maximum=db.execute(select(__import__('sqlalchemy').func.max(column))).scalar()
                    if maximum is not None:db.execute(text('SELECT setval(:sequence,:value,true)'),{'sequence':seq,'value':maximum})

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--load-local',action='store_true')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Output exists')
    bundle=generate();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(bundle,indent=2)+'\n',encoding='utf-8')
    if args.load_local:
        from .database import engine
        load(engine(),bundle)
    print(json.dumps(bundle['manifest'],indent=2))

if __name__=='__main__':main()
