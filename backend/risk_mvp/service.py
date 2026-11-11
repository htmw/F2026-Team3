"""Read-only as-of extraction; frozen model never receives grades or outcomes."""
from datetime import datetime,timedelta,timezone
from collections import Counter
from sqlalchemy import select
from .models import Base,Offering,Link,Assessment,AssessmentVersion,Submission,Activity,Coverage,History
from services.research_predictions import PredictionService

MODEL=PredictionService()
T=Base.metadata.tables

class MissingEnrollment(Exception):pass
class InvalidCutoff(ValueError):pass

def normalize(cutoff):
    if cutoff.tzinfo is None:raise InvalidCutoff('A timezone-aware cutoff is required')
    cutoff=cutoff.astimezone(timezone.utc)
    if cutoff.time().isoformat()!='23:59:59.999999':raise InvalidCutoff('MVP cutoff must be an end-of-day UTC timestamp (23:59:59.999999Z)')
    return cutoff

def extract(db,enrollment_id,cutoff):
    cutoff=normalize(cutoff)
    enrollment=db.execute(select(T['enrollments']).where(T['enrollments'].c.enrollment_id==enrollment_id)).mappings().first()
    if enrollment is None:raise MissingEnrollment()
    link=db.get(Link,enrollment_id)
    if link is None:return {'status':'unavailable','reason':'No dated course offering','coverage':{},'features':None,'evidence':{}}
    offering=db.get(Offering,link.offering_id)
    if offering.course_id!=enrollment['course_id']:raise ValueError('Enrollment/offering mismatch')
    if offering.timezone!='UTC':raise InvalidCutoff('Only UTC demo offerings supported')
    start_date=offering.starts_at.astimezone(timezone.utc).date()
    day=(cutoff.date()-start_date).days
    length=(offering.ends_at.astimezone(timezone.utc).date()-start_date).days
    available=offering.known_at<=cutoff and link.known_at<=cutoff and link.registered_at<=cutoff and 7<=day<length
    versions=db.scalars(select(History).where(History.enrollment_id==enrollment_id,History.known_at<=cutoff,History.effective_at<=cutoff).order_by(History.known_at)).all()
    available=available and bool(versions) and versions[-1].status=='in_progress'
    cov={}
    for record in db.scalars(select(Coverage).where(Coverage.enrollment_id==enrollment_id,Coverage.known_at<=cutoff).order_by(Coverage.known_at,Coverage.id)):
        cov[record.source]={'complete':record.complete and record.starts_at<=offering.starts_at and record.through_at>=cutoff,'through_at':record.through_at.isoformat()}
    eligibility_reason=None
    if offering.known_at>cutoff or link.known_at>cutoff:eligibility_reason='Offering or enrollment was not known at cutoff'
    elif link.registered_at>cutoff:eligibility_reason='Enrollment not yet registered at cutoff'
    elif day<7:eligibility_reason='Prediction requires course day 7 or later'
    elif day>=length:eligibility_reason='Course has ended at cutoff'
    elif not versions:eligibility_reason='No enrollment history known at cutoff'
    elif versions[-1].status!='in_progress':eligibility_reason='Enrollment is not active at cutoff'
    if eligibility_reason:
        return {'status':'unavailable','reason':eligibility_reason,'coverage':cov,'features':None,'evidence':{},
            'as_of_day':day if offering.known_at<=cutoff else None,'student_id':enrollment['student_id'],'course_id':enrollment['course_id']}
    definitions={a.id:a for a in db.scalars(select(Assessment).where(Assessment.offering_id==offering.id))}
    assessment_versions={}
    if definitions:
        for a in db.scalars(select(AssessmentVersion).where(AssessmentVersion.assessment_id.in_(definitions),AssessmentVersion.known_at<=cutoff).order_by(AssessmentVersion.known_at,AssessmentVersion.version)):
            assessment_versions[a.assessment_id]=a
    eligible={aid:a for aid,a in assessment_versions.items() if definitions[aid].kind!='Exam'}
    due=lambda a:(a.due_at.astimezone(timezone.utc).date()-start_date).days
    records={}
    for s in db.scalars(select(Submission).where(Submission.enrollment_id==enrollment_id,Submission.known_at<=cutoff,Submission.submitted_at<=cutoff).order_by(Submission.known_at,Submission.version)):
        if s.assessment_id not in definitions:raise ValueError('Cross-offering submission')
        records[s.assessment_id]=s
    submissions=[(str(aid),(s.submitted_at.astimezone(timezone.utc).date()-start_date).days,due(eligible[aid])) for aid,s in records.items() if aid in eligible and not s.is_banked and s.status in ['submitted','graded']]
    daily=Counter()
    for event in db.scalars(select(Activity).where(Activity.enrollment_id==enrollment_id,Activity.occurred_at<=cutoff,Activity.known_at<=cutoff,Activity.occurred_at>=offering.starts_at)):
        if event.event_type!='synthetic_resource_interaction':raise ValueError('Unsupported activity semantics')
        daily[(event.occurred_at.astimezone(timezone.utc).date()-start_date).days]+=event.count
    from acadmate_ml.features import snapshot
    features=snapshot(day,length,daily,submissions,[(str(aid),due(a)) for aid,a in eligible.items()])
    complete=all(cov.get(s,{}).get('complete',False) for s in ['activity','submissions','schedule'])
    evidence={'assessments_due':features['assessments_due'] if cov.get('schedule',{}).get('complete') else None,
        'submissions':features['submissions_so_far'] if all(cov.get(s,{}).get('complete') for s in ['schedule','submissions']) else None,
        'overdue_assignments':features['overdue_assessments'] if all(cov.get(s,{}).get('complete') for s in ['schedule','submissions']) else None,
        'clicks_7d':features['clicks_7d'] if cov.get('activity',{}).get('complete') else None,
        'active_days_7d':features['active_days_7d'] if cov.get('activity',{}).get('complete') else None,
        'clicks_28d':features['clicks_28d'] if cov.get('activity',{}).get('complete') else None,
        'engagement_change':features['engagement_change'] if cov.get('activity',{}).get('complete') else None,
        'days_since_activity':features['days_since_activity'] if cov.get('activity',{}).get('complete') else None,
        'late_submission_rate':features['late_submission_rate'] if all(cov.get(s,{}).get('complete') for s in ['schedule','submissions']) else None,
        'assessment_completion_rate':len({aid for aid,_,due_day in submissions if 0<=due_day<=day})/features['assessments_due'] if features['assessments_due'] and all(cov.get(s,{}).get('complete') for s in ['schedule','submissions']) else None,
        'released_scores':[{'assessment_id':aid,'score':s.score,'max_score':eligible[aid].max_score} for aid,s in records.items() if aid in eligible and s.grade_available_at is not None and s.grade_available_at<=cutoff and s.score is not None],
        'score_use':'Descriptive only; excluded from frozen model'}
    return {'status':'ready' if complete and available else 'unavailable',
        'reason':None if complete and available else 'Incomplete source coverage: '+', '.join(s for s in ['activity','submissions','schedule'] if not cov.get(s,{}).get('complete',False)),
        'coverage':cov,'features':features if complete and available else None,'evidence':evidence,'as_of_day':day,
        'student_id':enrollment['student_id'],'course_id':enrollment['course_id']}

def assessment(db,enrollment_id,cutoff):
    row=extract(db,enrollment_id,cutoff)
    response={k:v for k,v in row.items() if k!='features'}
    response.update(enrollment_id=enrollment_id,cutoff=normalize(cutoff).isoformat(),research_only=True,
        source_kind='synthetic_lms_demo',research_risk_probability=None,model_version='final-experiment-v1',
        calibration_method='sigmoid',computed_at_utc=datetime.now(timezone.utc).isoformat(),
        warnings=['Synthetic database workflow; not validated institutional risk probabilities.','Early-course probabilities can overestimate risk.'])
    if row['status']=='ready':
        from acadmate_ml.predict import predict
        with MODEL._lock:
            if MODEL._artifacts is None:MODEL._artifacts=MODEL._load()
            document={'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':row['as_of_day'],
                'rows':[{'enrollment_id':str(enrollment_id),'student_id':str(row['student_id']),'course_id':str(row['course_id']),
                    'as_of_day':row['as_of_day'],'case':'database_demo','source_kind':'synthetic_lms_demo','status':'ready','reason':None,'features':row['features']}]}
            scored=predict(document,*MODEL._artifacts)['rows'][0]
        response.update(status='scored_research_demo',research_risk_probability=scored['research_risk_probability'])
    return response

def insights(db,student_id):
    student=db.execute(select(T['students']).where(T['students'].c.student_id==student_id)).mappings().first()
    if student is None:raise MissingEnrollment()
    e,c=T['enrollments'],T['courses']
    rows=db.execute(select(e,c.c.course_code,c.c.credits).join(c,e.c.course_id==c.c.course_id).where(e.c.student_id==student_id)).mappings().all()
    completed=[r for r in rows if r['status']=='completed' and r['grade_points'] is not None]
    credits=sum(float(r['credits']) for r in completed)
    gpa=round(sum(float(r['credits'])*float(r['grade_points']) for r in completed)/credits,2) if credits else None
    return {'student_id':student_id,'name':student['name'],'source_kind':'synthetic_lms_demo',
        'academic_summary_scope':'Current recorded snapshot, not historical as-of GPA',
        'recorded_gpa':gpa,'completed_credits':credits,'gpa_policy':'Matches existing profile implementation; policy unconfirmed',
        'failed_courses':[r['course_code'] for r in rows if r['status']=='failed'],
        'withdrawn_courses':[r['course_code'] for r in rows if r['status']=='withdrawn'],
        'active_enrollments':[{'enrollment_id':r['enrollment_id'],'course_id':r['course_id'],'course_code':r['course_code'],'term':r['term']} for r in rows if r['status']=='in_progress']}
