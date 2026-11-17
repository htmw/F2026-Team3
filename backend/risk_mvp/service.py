"""Read-only as-of extraction; frozen model never receives grades or outcomes."""
import numpy as np
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
    # Project only required academic fields: main metadata may have newer columns
    # than the isolated research database (for example section_id).
    e=T['enrollments'].c
    enrollment=db.execute(select(e.student_id,e.course_id).where(e.enrollment_id==enrollment_id)).mappings().first()
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

FACTOR_LABELS = {
    "course_day": "Course timing",
    "course_progress": "Course progress",
    "window_days_28d": "Recent observation window",
    "clicks_7d": "LMS activity in the last 7 days",
    "clicks_28d": "LMS activity in the last 28 days",
    "active_days_7d": "Active LMS days in the last 7 days",
    "active_days_28d": "Active LMS days in the last 28 days",
    "engagement_change": "Change in recent engagement",
    "days_since_activity": "Time since last LMS activity",
    "no_activity": "No recorded LMS activity",
    "assessments_due": "Assessments due",
    "submissions_so_far": "Assignments submitted",
    "overdue_assessments": "Overdue assessments",
    "late_submission_rate": "Late submission rate",
    "days_since_submission": "Time since last submission",
    "no_submission": "No recorded submission",
}


def model_factors(features: dict) -> list[dict]:
    """Return the three strongest SHAP factors for the frozen risk model.

    SHAP values are calculated in the transformed feature space used by
    the frozen LogisticRegression model.

    Positive SHAP values push the prediction toward higher modeled risk.
    Negative SHAP values push it toward lower modeled risk.
    """
    import shap

    from acadmate_ml.features import FEATURES

    with MODEL._lock:
        if MODEL._artifacts is None:
            MODEL._artifacts = MODEL._load()

        pipeline = MODEL._artifacts[0]

        imputer = pipeline.named_steps["imputer"]
        scaler = pipeline.named_steps["scaler"]
        classifier = pipeline.named_steps["classifier"]

        raw = np.asarray(
            [[
                np.nan if features[name] is None
                else features[name]
                for name in FEATURES
            ]],
            dtype=float,
        )

        # Apply the exact preprocessing from the frozen model.
        imputed = imputer.transform(raw)
        scaled = scaler.transform(imputed)

        names = imputer.get_feature_names_out(FEATURES)

        # StandardScaler centers training features around zero.
        # Use that transformed-space center as the SHAP reference.
        background = np.zeros(
            (1, scaled.shape[1]),
            dtype=float,
        )

        explainer = shap.LinearExplainer(
            classifier,
            background,
            feature_names=list(names),
        )

        explanation = explainer(scaled)

        shap_values = np.asarray(
            explanation.values[0],
            dtype=float,
        )

        base_value = float(
            np.asarray(explanation.base_values).reshape(-1)[0]
        )

    factors = []

    for name, shap_value in zip(names, shap_values):
        # Missingness indicators are legitimate model features,
        # but are implementation details rather than useful
        # advisor-facing academic explanations.
        if name.startswith("missingindicator_"):
            continue

        factors.append({
            "feature": name,
            "label": FACTOR_LABELS.get(
                name,
                name.replace("_", " ").title(),
            ),
            "direction": (
                "increases risk"
                if shap_value > 0
                else "reduces risk"
            ),
            "shap_value": round(
                float(shap_value),
                6,
            ),
            "value": features.get(name),
        })

    factors.sort(
        key=lambda factor: abs(factor["shap_value"]),
        reverse=True,
    )

    top_factors = factors[:3]

    for factor in top_factors:
        factor["base_value"] = round(
            base_value,
            6,
        )
        factor["explanation_method"] = "shap_linear"

    return top_factors

RECOMMENDATION_RULES = {
      "overdue_assessments": {
          "increases risk": {
              "title": "Catch up on overdue assessments",
              "detail": "Prioritize overdue coursework and contact the instructor if additional support is needed.",
              "action": "review_assignments",
          },
          "reduces risk": {
              "title": "Keep assignments on schedule",
              "detail": "No overdue assessments are currently contributing to academic risk.",
              "action": "review_assignments",
          },
      },

      "days_since_activity": {
          "increases risk": {
              "title": "Resume regular course activity",
              "detail": "Return to the LMS regularly and review recent course materials.",
              "action": "open_courses",
          },
          "reduces risk": {
              "title": "Maintain recent engagement",
              "detail": "Recent LMS activity is helping reduce the modeled risk.",
              "action": "open_courses",
          },
      },

      "active_days_28d": {
          "increases risk": {
              "title": "Increase weekly engagement",
              "detail": "Use the LMS more consistently throughout the week.",
              "action": "open_courses",
          },
          "reduces risk": {
              "title": "Continue consistent participation",
              "detail": "Regular activity across the last four weeks is a positive factor.",
              "action": "open_courses",
          },
      },

      "late_submission_rate": {
          "increases risk": {
              "title": "Improve submission timing",
              "detail": "Create a schedule for upcoming deadlines and submit work before the due date.",
              "action": "review_assignments",
          },
          "reduces risk": {
              "title": "Maintain on-time submissions",
              "detail": "On-time coursework is currently reducing modeled risk.",
              "action": "review_assignments",
          },
      },

      "days_since_submission": {
          "increases risk": {
              "title": "Review upcoming coursework",
              "detail": "Check upcoming assignments and make a plan for the next submission.",
              "action": "review_assignments",
          },
          "reduces risk": {
              "title": "Keep submitting regularly",
              "detail": "Recent coursework submission is a positive academic signal.",
              "action": "review_assignments",
          },
      },

      "clicks_7d": {
          "increases risk": {
              "title": "Increase recent course engagement",
              "detail": "Spend more time reviewing current course materials and announcements.",
              "action": "open_courses",
          },
          "reduces risk": {
              "title": "Maintain recent LMS activity",
              "detail": "Recent course interaction is helping reduce modeled risk.",
              "action": "open_courses",
          },
      },
  }


def recommendations_for(factors: list[dict]) -> list[dict]:
    recommendations = []

    for factor in factors:
        rule = RECOMMENDATION_RULES.get(factor["feature"], {}).get(
            factor["direction"]
        )

        if rule is None:
            continue

        recommendations.append({
            "source_feature": factor["feature"],
            "title": rule["title"],
            "detail": rule["detail"],
            "action": rule["action"],
        })

    # Always provide an advisor option for a student who wants
    # additional guidance.
    if len(recommendations) < 3:
        recommendations.append({
            "source_feature": "advisor_support",
            "title": "Meet with your advisor",
            "detail": "Discuss academic progress and next steps with your assigned advisor.",
            "action": "book_advisor",
        })

    return recommendations[:3]

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

        factors=model_factors(row["features"])
        response.update(status='scored_research_demo',research_risk_probability=scored['research_risk_probability'],top_factors=factors,recommendations=recommendations_for(factors),)
    return response

def insights(db,student_id):
    s=T['students'].c
    student=db.execute(select(s.name).where(s.student_id==student_id)).mappings().first()
    if student is None:raise MissingEnrollment()
    e,c=T['enrollments'],T['courses']
    rows=db.execute(select(e.c.enrollment_id,e.c.course_id,e.c.status,e.c.grade_points,e.c.term,c.c.course_code,c.c.credits).join(c,e.c.course_id==c.c.course_id).where(e.c.student_id==student_id)).mappings().all()
    completed=[r for r in rows if r['status']=='completed' and r['grade_points'] is not None]
    credits=sum(float(r['credits']) for r in completed)
    gpa=round(sum(float(r['credits'])*float(r['grade_points']) for r in completed)/credits,2) if credits else None
    return {'student_id':student_id,'name':student['name'],'source_kind':'synthetic_lms_demo',
        'academic_summary_scope':'Current recorded snapshot, not historical as-of GPA',
        'recorded_gpa':gpa,'completed_credits':credits,'gpa_policy':'Matches existing profile implementation; policy unconfirmed',
        'failed_courses':[r['course_code'] for r in rows if r['status']=='failed'],
        'withdrawn_courses':[r['course_code'] for r in rows if r['status']=='withdrawn'],
        'active_enrollments':[{'enrollment_id':r['enrollment_id'],'course_id':r['course_id'],'course_code':r['course_code'],'term':r['term']} for r in rows if r['status']=='in_progress']}
