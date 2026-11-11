"""Read-only synthetic inference audit. Never trains or measures accuracy."""
import argparse,json,math,statistics,time
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from .database import engine
from .models import Base,Link
from .service import extract,assessment


def summarize(values):
    if not values:return {'count':0}
    return {'count':len(values),'min':min(values),'max':max(values),'mean':statistics.mean(values),'median':statistics.median(values)}

def audit(db,cutoff):
    start=time.perf_counter();e=Base.metadata.tables['enrollments']
    enrollments=db.execute(select(e).where(e.c.status=='in_progress').order_by(e.c.enrollment_id)).mappings().all()
    rows=[];groups=defaultdict(list);submission_groups=defaultdict(list);errors=[]
    for enrollment in enrollments:
        eid=enrollment['enrollment_id'];features=extract(db,eid,cutoff);result=assessment(db,eid,cutoff)
        link=db.get(Link,eid)
        row={'enrollment_id':eid,'student_id':enrollment['student_id'],'pattern':link.pattern if link else None,
            'status':result['status'],'probability':result['research_risk_probability'],'reason':result['reason'],
            'coverage':result['coverage'],'features':features['features'],'evidence':result['evidence']}
        if row['probability'] is not None:
            p=row['probability']
            if not math.isfinite(p) or not 0<=p<=1:errors.append(f'{eid}: invalid probability')
            groups[row['pattern']].append(p)
            f=row['features']
            label='overdue work present' if f['overdue_assessments'] else 'no overdue work'
            submission_groups[label].append(p)
            label='observed late submissions' if f['late_submission_rate'] is not None and f['late_submission_rate']>0 else 'no observed late submissions' if f['late_submission_rate'] is not None else 'no submissions'
            submission_groups[label].append(p)
            if f['overdue_assessments']>f['assessments_due']:errors.append(f'{eid}: overdue count exceeds due count')
            if f['active_days_7d']>7 or f['active_days_28d']>28:errors.append(f'{eid}: invalid active-day counts')
            if any(v is not None and not math.isfinite(v) for v in f.values()):errors.append(f'{eid}: nonfinite feature')
        rows.append(row)
    scored=[r for r in rows if r['probability'] is not None];probabilities=[r['probability'] for r in scored]
    bins=Counter(min(int(p*10),9) for p in probabilities)
    equal=Counter(r['probability'] for r in scored)
    signatures=Counter(tuple(r['features'].items()) for r in scored)
    missing=Counter(k for r in scored for k,v in r['features'].items() if v is None)
    report={'cutoff':cutoff.isoformat(),'source_kind':'synthetic_lms_demo','total_evaluated':len(rows),
        'scored':len(scored),'not_scored':len(rows)-len(scored),
        'unscored_reasons':dict(Counter(r['reason'] for r in rows if r['probability'] is None)),
        'unscored_missing_sources':dict(Counter(s for r in rows if r['probability'] is None for s,c in r['coverage'].items() if not c['complete'])),
        'probabilities':summarize(probabilities),
        'distribution':[{'lower_inclusive':i/10,'upper':(i+1)/10,'upper_inclusive':i==9,'count':bins[i]} for i in range(10)],
        'by_generation_pattern':{k:summarize(v) for k,v in sorted(groups.items())},
        'by_observed_submission_pattern':{k:summarize(v) for k,v in sorted(submission_groups.items())},
        'anomalies':{'invalid_features':errors,'exact_zero_or_one':sum(p in [0,1] for p in probabilities),
            'duplicate_probability_groups':[{'probability':p,'count':n} for p,n in equal.items() if n>1],
            'duplicate_feature_groups':sum(n>1 for n in signatures.values()),'null_feature_counts':dict(missing)},
        'elapsed_seconds':time.perf_counter()-start,'rows':rows,
        'limitations':['Generated patterns are not outcomes; comparisons are descriptive, not causal or accuracy evidence',
            'Submission groupings overlap; histogram bins are report bins, not risk thresholds',
            'Only active synthetic enrollments at this cutoff; domain transfer not validated']}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cutoff',type=datetime.fromisoformat,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Output exists')
    with Session(engine()) as db:
        db.execute(text('SET TRANSACTION READ ONLY'));report=audit(db,args.cutoff)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
