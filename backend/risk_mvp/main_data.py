"""Deterministic, explicitly simulated sidecars for an existing academic snapshot.

No names, grades, outcomes or advisor flags determine activity patterns. The old
CSV generator and frozen research experiment remain unchanged.
"""
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import MetaData, Table, select, insert, func
from .models import RISK_TABLES
from .generate import validate, parse

PATTERNS = ('high', 'moderate', 'declining', 'late', 'missed', 'improving')
ACADEMIC_TABLES = ('students', 'courses', 'enrollments', 'terms', 'advisor_student_assignments')


def snapshot(engine):
    """Read consistent records; deliberately never reads users/password/session tables."""
    metadata = MetaData()
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        conn.exec_driver_sql('SET TRANSACTION READ ONLY')
        result = {}
        for name in ACADEMIC_TABLES:
            table = Table(name, metadata, autoload_with=conn)
            result[name] = [dict(row) for row in conn.execute(select(table).order_by(*table.primary_key.columns)).mappings()]
    return result


def fingerprint(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def generate(records, seed=20261111):
    enrollments = records['enrollments']
    ids = [int(e['enrollment_id']) for e in enrollments]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Nonempty unique enrollments required')
    students = {int(s['student_id']) for s in records['students']}
    courses = {int(c['course_id']) for c in records['courses']}
    terms = {t['name']:t for t in records['terms']}
    if len(terms) != len(records['terms']):
        raise ValueError('Ambiguous term name')
    for e in enrollments:
        if e['student_id'] not in students or e['course_id'] not in courses:
            raise ValueError('Orphan academic enrollment')
        if e['term'] not in terms:
            raise ValueError('Enrollment has no dated term: '+e['term'])
        if e['status'] not in ('in_progress','completed','failed','withdrawn'):
            raise ValueError('Unsupported enrollment status')
    tables = {t.name:[] for t in RISK_TABLES}
    def add(name, **row):
        if name != 'risk_enrollment_offerings': row = dict(id=len(tables[name])+1, **row)
        tables[name].append(row)
        return row
    offerings = {}; tasks = {}; checkpoints = {}
    for course, term in sorted({(e['course_id'],e['term']) for e in enrollments}):
        t = terms[term]
        start = datetime.combine(t['start_date'], datetime.min.time(), timezone.utc)
        # End date is inclusive in the academic calendar; sidecar end is next UTC midnight.
        end = datetime.combine(t['end_date']+timedelta(days=1), datetime.min.time(), timezone.utc)
        length = (end-start).days
        if length <= 28: raise ValueError('Course too short for 7/14/28-day demonstration')
        off = add('risk_course_offerings', course_id=course, term=term, starts_at=start.isoformat(), ends_at=end.isoformat(), timezone='UTC', known_at=(start-timedelta(days=14)).isoformat())
        offerings[course,term] = off
        due_days = sorted({7,14,21,28,*range(35,length-1,14)})
        tasks[off['id']] = []
        for index, day in enumerate(due_days):
            a = add('risk_assessments', offering_id=off['id'], label=f'Simulated coursework {index+1}', kind='TMA')
            add('risk_assessment_versions', assessment_id=a['id'], version=1, due_at=(start+timedelta(days=day,hours=18)).isoformat(), max_score=100., known_at=start.isoformat())
            tasks[off['id']].append((a,day))
    for e in sorted(enrollments,key=lambda e:e['enrollment_id']):
        eid = e['enrollment_id']; off = offerings[e['course_id'],e['term']]
        start = parse(off['starts_at']); end = parse(off['ends_at']); length = (end-start).days
        key = hashlib.sha256(f'{seed}:{eid}'.encode()).digest()
        rng = random.Random(int.from_bytes(key[:8],'big')); pattern = PATTERNS[int.from_bytes(key[8:12],'big')%len(PATTERNS)]
        add('risk_enrollment_offerings', enrollment_id=eid, offering_id=off['id'], registered_at=(start-timedelta(days=7)).isoformat(), known_at=(start-timedelta(days=7)).isoformat(), pattern=pattern)
        # This is a simulated trajectory, not a claim about the real recorded past.
        add('risk_enrollment_history', enrollment_id=eid, status='in_progress', grade=None, grade_points=None, effective_at=start.isoformat(), known_at=start.isoformat())
        if e['status'] != 'in_progress':
            add('risk_enrollment_history', enrollment_id=eid, status=e['status'], grade=None, grade_points=None, effective_at=end.isoformat(), known_at=end.isoformat())
        for day in range(length):
            probability = {'high':.85,'moderate':.55,'late':.55,'missed':.15,'improving':.3+.5*day/length,'declining':max(.08,.9-day/length)}[pattern]
            if rng.random() < probability:
                event = start+timedelta(days=day,hours=12)
                add('risk_activity_events', enrollment_id=eid, source_event_id=f'main-simulation:{seed}:{eid}:{day}', occurred_at=event.isoformat(), known_at=event.isoformat(), count=rng.randint(5,60), event_type='synthetic_resource_interaction')
        for task, day in tasks[off['id']]:
            if rng.random() < (.55 if pattern=='missed' else .08): continue
            delay = rng.choice([1,2,4]) if pattern=='late' else rng.choice([-2,-1,0,0,1])
            submitted = start+timedelta(days=day+delay,hours=15)
            if submitted >= end: continue
            add('risk_submission_versions', enrollment_id=eid, assessment_id=task['id'], version=1, submitted_at=submitted.isoformat(), known_at=submitted.isoformat(), grade_available_at=None, score=None, status='submitted', is_banked=False)
        # Daily complete simulated feeds prevent gaps between weekly checkpoints.
        for day in range(7,length):
            cutoff = start+timedelta(days=day+1)-timedelta(microseconds=1)
            for source in ('activity','schedule','submissions'):
                add('risk_source_coverage', enrollment_id=eid, source=source, starts_at=start.isoformat(), through_at=cutoff.isoformat(), known_at=cutoff.isoformat(), complete=True)
        checkpoints[str(eid)] = {str(d):(start+timedelta(days=d+1)-timedelta(microseconds=1)).isoformat() for d in (7,14,28)}
    validate(tables,enrollments)
    return {'manifest':{'schema_version':'1.0','generator_version':'main-all-enrollments-v1','source_kind':'synthetic_lms_demo','seed':seed,'academic_sha256':fingerprint(records),'enrollment_count':len(enrollments),'counts':{n:len(rows) for n,rows in tables.items()},'checkpoints':checkpoints,'assumptions':['UTC normalization of existing term dates; end date inclusive','All activity, TMA schedules, registration times and historical in-progress trajectories are simulations','Terminal statuses occur at simulated course end; actual withdrawal/completion dates are not known','Complete synthetic feeds for every enrollment; completeness does not imply predictive validity','No real LMS access; academic outcomes do not determine generated activity']},'tables':tables}


def load(engine, bundle, records):
    """Add only risk tables to an explicitly disposable existing academic database."""
    if engine.url.host not in ('127.0.0.1','localhost') or engine.url.database not in ('acadmate_risk_demo_main_sprint2', 'acadmate_risk_csv_sprint2'):
        raise ValueError('Dedicated main-integration disposable database required')
    if fingerprint(snapshot(engine)) != bundle['manifest']['academic_sha256'] or fingerprint(records) != bundle['manifest']['academic_sha256']:
        raise ValueError('Academic snapshot changed')
    validate(bundle['tables'], records['enrollments'])
    for table in RISK_TABLES: table.create(engine, checkfirst=True)
    with engine.begin() as conn:
        if any(conn.scalar(select(func.count()).select_from(t)) for t in RISK_TABLES):
            raise ValueError('Refusing existing risk records; use a new disposable database')
        for table in RISK_TABLES:
            rows = [{c.name:parse(row[c.name]) if c.type.__class__.__name__=='DateTime' and row[c.name] is not None else row[c.name] for c in table.columns} for row in bundle['tables'][table.name]]
            if rows: conn.execute(insert(table),rows)
    if fingerprint(snapshot(engine)) != bundle['manifest']['academic_sha256']:
        raise ValueError('Academic data changed during load')
