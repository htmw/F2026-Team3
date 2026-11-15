"""Audit every record/course for one CSV-demo advisor without fitting any model."""
from pathlib import Path
import argparse,json,sys,math,urllib.request,http.cookiejar
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from prepare_csv_population_demo import bootstrap,DAY

def independent_features(start,end,cutoff,activities,assessments,versions,submissions):
    start=start.astimezone(timezone.utc);end=end.astimezone(timezone.utc);cutoff=cutoff.astimezone(timezone.utc)
    day=(cutoff.date()-start.date()).days;length=(end.date()-start.date()).days
    known={}
    for v in sorted(versions,key=lambda x:(x.known_at,x.version)):
        if v.known_at<=cutoff and assessments[v.assessment_id].kind!='Exam':known[v.assessment_id]=v
    due={aid:(v.due_at.astimezone(timezone.utc).date()-start.date()).days for aid,v in known.items()}
    latest={}
    for s in sorted(submissions,key=lambda x:(x.known_at,x.version)):
        if s.known_at<=cutoff and s.submitted_at<=cutoff:latest[s.assessment_id]=s
    observed=[(aid,(s.submitted_at.astimezone(timezone.utc).date()-start.date()).days,due[aid]) for aid,s in latest.items() if aid in due and not s.is_banked and s.status in ('submitted','graded')]
    daily=Counter()
    for a in activities:
        if start<=a.occurred_at<=cutoff and a.known_at<=cutoff:daily[(a.occurred_at.astimezone(timezone.utc).date()-start.date()).days]+=a.count
    due_ids={aid for aid,d in due.items() if 0<=d<=day};submitted_ids={aid for aid,_,_ in observed}
    active=[d for d,n in daily.items() if n>0]
    return {'course_day':day,'course_progress':day/length,'window_days_28d':min(28,day+1),
      'clicks_7d':sum(n for d,n in daily.items() if max(0,day-6)<=d<=day),
      'clicks_28d':sum(n for d,n in daily.items() if max(0,day-27)<=d<=day),
      'active_days_7d':sum(n>0 for d,n in daily.items() if max(0,day-6)<=d<=day),
      'active_days_28d':sum(n>0 for d,n in daily.items() if max(0,day-27)<=d<=day),
      'engagement_change':sum(n for d,n in daily.items() if day-6<=d<=day)-sum(n for d,n in daily.items() if day-13<=d<=day-7) if day>=13 else None,
      'days_since_activity':day-max(active) if active else None,'no_activity':int(not active),
      'assessments_due':len(due_ids),'submissions_so_far':len(submitted_ids),'overdue_assessments':len(due_ids-submitted_ids),
      'late_submission_rate':sum(s>d for _,s,d in observed)/len(observed) if observed else None,
      'days_since_submission':day-max(s for _,s,_ in observed) if observed else None,'no_submission':int(not observed)}

def audit(snapshot,advisor_id,output=None,team_review=False):
    import os
    snap=Path(snapshot).resolve()
    if not snap.is_relative_to(ROOT/'ml/outputs/main-integration'):
        raise ValueError('Isolated snapshot required')
    destination=Path(output).resolve() if output else snap/f'advisor-{advisor_id}-audit.json'
    if not destination.is_relative_to(ROOT/'ml/outputs') or destination.exists():
        raise ValueError('New output under ignored ml/outputs required; previous audits are preserved')
    if team_review:
        marker=json.loads((snap/'team-demo-manifest.json').read_text())
        if marker.get('state')!='complete' or marker.get('database')!='acadmate_risk_team_review_sprint2':
            raise ValueError('Verified local team-demo clone required')
        url='postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2'
        os.environ.update(DATABASE_URL=url,ACADMATE_RISK_DATABASE_URL=url,ACADMATE_TODAY=DAY,ACADMATE_RISK_MVP_ENABLED='true',OMP_NUM_THREADS='2')
        os.chdir(snap/'backend')
        sys.path[:0]=[str(snap/'backend'),str(ROOT/'backend'),str(ROOT/'ml/src')]
        import services
        services.__path__.append(str(ROOT/'backend/services'))
    else:
        snap=bootstrap(snapshot)
    from database import SessionLocal
    import models as m
    from sqlalchemy import select,text
    from risk_mvp import service
    from risk_mvp.models import Link,Offering,Assessment,AssessmentVersion,Submission,Activity
    from seed_data import DEMO_PASSWORD
    from acadmate_ml.features import FEATURES
    import numpy as np
    from scipy.special import expit,logit
    cutoff=datetime.fromisoformat(DAY+'T23:59:59.999999+00:00')
    pipeline,sigmoid=service.MODEL._load()
    with SessionLocal() as db:
        db.connection(execution_options={'isolation_level':'REPEATABLE READ'});db.execute(text('SET TRANSACTION READ ONLY'))
        from risk_mvp.main_data import snapshot as academic_snapshot, fingerprint
        before=fingerprint(academic_snapshot(db.get_bind()))
        advisor=db.get(m.Advisor,advisor_id);email=db.get(m.User,advisor.user_id).email
        ids=set(db.scalars(select(m.AdvisorStudentAssignment.student_id).where(m.AdvisorStudentAssignment.advisor_id==advisor_id)))
        assert len(ids)==25
        enrollments=db.scalars(select(m.Enrollment).where(m.Enrollment.student_id.in_(ids))).all()
        eids={e.enrollment_id for e in enrollments}
        links={x.enrollment_id:x for x in db.scalars(select(Link).where(Link.enrollment_id.in_(eids)))}
        offs={x.id:x for x in db.scalars(select(Offering).where(Offering.id.in_({l.offering_id for l in links.values()})))}
        tasks={x.id:x for x in db.scalars(select(Assessment).where(Assessment.offering_id.in_(offs)))}
        versions=list(db.scalars(select(AssessmentVersion).where(AssessmentVersion.assessment_id.in_(tasks))))
        subs=list(db.scalars(select(Submission).where(Submission.enrollment_id.in_(eids))))
        events=list(db.scalars(select(Activity).where(Activity.enrollment_id.in_(eids))))
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base='http://127.0.0.1:'+('8005' if team_review else '8004')+'/api/v1'
        op.open(urllib.request.Request(base+'/auth/login',data=json.dumps({'email':email,'password':DEMO_PASSWORD}).encode(),headers={'Content-Type':'application/json'})).read()
        def get(path):return json.load(op.open(base+path))
        listing=get('/advisor/advisees');assert {r['studentId'] for r in listing['rows']}==ids
        records=[];counts=Counter();future_ignored=0;max_error=0;probabilities=[]
        for row in sorted(listing['rows'],key=lambda r:r['studentId']):
            sid=row['studentId'];record=get('/advisor/advisees/'+str(sid));insights=get('/advisor/research/students/'+str(sid)+'/insights')
            assert record['student']['id']==sid and record['student']['fullName']==row['fullName']
            if row['risk']!='Low':assert row['flag']==record['concernSummary']
            assert {e['enrollment_id'] for e in insights['enrollments']}=={e.enrollment_id for e in enrollments if e.student_id==sid}
            courses=[]
            for e in sorted([e for e in enrollments if e.student_id==sid],key=lambda e:e.enrollment_id):
                counts['enrollments']+=1
                if e.status!='in_progress':
                    historical=service.assessment(db,e.enrollment_id,cutoff)
                    assert historical['status']=='unavailable' and historical['research_risk_probability'] is None
                    counts['historical_unscored']+=1;continue
                off=offs[links[e.enrollment_id].offering_id]
                a={aid:x for aid,x in tasks.items() if x.offering_id==off.id}
                v=[x for x in versions if x.assessment_id in a];ss=[x for x in subs if x.enrollment_id==e.enrollment_id];aa=[x for x in events if x.enrollment_id==e.enrollment_id]
                expected=independent_features(off.starts_at,off.ends_at,cutoff,aa,a,v,ss)
                extracted=service.extract(db,e.enrollment_id,cutoff);assert extracted['status']=='ready'
                assert extracted['features']==expected,(sid,e.enrollment_id,extracted['features'],expected)
                future_ignored+=sum(x.known_at>cutoff or x.occurred_at>cutoff for x in aa)+sum(x.known_at>cutoff or x.submitted_at>cutoff for x in ss)
                result=get('/advisor/research/enrollments/'+str(e.enrollment_id)+'/risk-assessment?cutoff='+insights['demo_cutoff']+'&include_explanation=true&force_refresh=true')
                assert result['status']=='scored_research_demo' and result['student_id']==sid
                explanation=result['explanation'];assert explanation['status']=='available'
                cs=explanation['contributions'];assert len(cs)==16 and {x['feature'] for x in cs}==set(FEATURES)
                assert {x['feature']:x['input_value'] for x in cs}==expected
                assert result['evidence']['received_submissions']==expected['submissions_so_far']
                assert result['evidence']['late_submissions']==round(expected['late_submission_rate']*expected['submissions_so_far']) if expected['late_submission_rate'] is not None else result['evidence']['late_submissions']==0
                x=np.array([[np.nan if expected[f] is None else expected[f] for f in FEATURES]])
                raw=float(pipeline.decision_function(x)[0]);prob=float(sigmoid.predict_proba(np.array([[logit(expit(raw))]]))[0,1])
                reconstructed=explanation['baseline_raw_log_odds']+sum(c['raw_log_odds_contribution'] for c in cs)
                assert math.isclose(raw,reconstructed,abs_tol=1e-9)
                assert math.isclose(prob,result['research_risk_probability'],abs_tol=1e-12)
                assert math.isclose(prob,explanation['reconstructed_calibrated_probability'],abs_tol=1e-12)
                again=get('/advisor/research/enrollments/'+str(e.enrollment_id)+'/risk-assessment?cutoff='+insights['demo_cutoff']+'&include_explanation=true')
                assert again['research_risk_probability']==result['research_risk_probability']
                max_error=max(max_error,abs(raw-reconstructed));probabilities.append(prob);counts['current_scored']+=1;counts['explanations']+=1
                courses.append({'enrollment_id':e.enrollment_id,'course':next(z['course_code'] for z in insights['enrollments'] if z['enrollment_id']==e.enrollment_id),'probability':prob,'features':expected,'evidence':result['evidence'],'explanation':explanation})
            records.append({'student_id':sid,'name':row['fullName'],'status':row['status'],'flag':row['flag'],'gpa':row['gpa'],'courses':courses,'enrollments':len([e for e in enrollments if e.student_id==sid])})
            print('Checked',sid,row['fullName'],'current courses',len(courses),flush=True)
        dashboard=get('/advisor/dashboard');reports=get('/advisor/reports')
        attention=sum(r['risk']!='Low' for r in listing['rows'])
        assert int(next(s['value'] for s in dashboard['stats'] if s['key']=='attention'))==attention
        assert int(next(s['value'] for s in reports['stats'] if s['label']=='Need attention'))==attention
        for preview in dashboard['attention']:assert preview['flag']==next(r for r in listing['rows'] if r['studentId']==preview['studentId'])['flag']
        assert fingerprint(academic_snapshot(db.get_bind()))==before
        database_name=db.get_bind().url.database
    result={'provenance':{'snapshot':str(snap),'database':database_name,'cutoff':cutoff.isoformat(),'academic_sha256':before},'passed':True,'advisor_id':advisor_id,'students':len(records),'counts':dict(counts),'attention':attention,'future_events_or_submissions_excluded':future_ignored,'max_raw_reconstruction_error':max_error,'mean_current_probability':sum(probabilities)/len(probabilities),'records':records,'limits':['No measured synthetic-student accuracy; no outcome truth assigned to synthetic activity','Frozen model and calibration unchanged; no fitting or threshold selection','Existing final OULAD results reviewed, not rerun for model selection']}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--advisor-id',type=int,default=201);p.add_argument('--output');p.add_argument('--team-review',action='store_true');a=p.parse_args();audit(a.snapshot,a.advisor_id,a.output,a.team_review)
