"""Retrospective student-disjoint validation calibration; test stays reserved."""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from .features import FEATURES
from .splits import digest
from .train import load_partition, metrics, calibration


def fit_group(student):
    # Outcome-independent, stable assignment shared by every course/week of a student.
    return int(hashlib.sha256(('acadmate-calibration-v1:'+student).encode()).hexdigest()[:8],16)%2==0


def logit(p):
    clipped=np.clip(p,1e-6,1-1e-6)
    return np.log(clipped/(1-clipped)).reshape(-1,1)


def fit_maps(probability,y,weights):
    if len(np.unique(y))!=2:
        raise ValueError('Calibration fit requires both classes')
    sigmoid=LogisticRegression(C=1e6,max_iter=2000,random_state=42)
    sigmoid.fit(logit(probability),y,sample_weight=weights/weights.mean())
    isotonic=IsotonicRegression(out_of_bounds='clip')
    isotonic.fit(probability,y,sample_weight=weights)
    return sigmoid,isotonic


def run(splits,artifacts,output):
    if output.exists(): raise ValueError('Output exists; refusing to overwrite')
    baseline=json.loads((artifacts/'validation_metrics.json').read_text(encoding='utf-8'))
    for name in ['features','labels']:
        if digest(splits/'validation'/(name+'.csv'))!=baseline['inputs']['validation/'+name+'.csv']:
            raise ValueError('Validation provenance mismatch')
    if digest(splits/'manifest.json')!=baseline['split_manifest_sha256']:
        raise ValueError('Split provenance mismatch')
    X,y,identities,weights,_=load_partition(splits/'validation')
    fit=np.array([fit_group(i[2]) for i in identities])
    assess=~fit
    for mask in [fit,assess]:
        if len(np.unique(y[mask]))!=2: raise ValueError('Each calibration group needs both classes')
    fit_ids={i[2] for i,m in zip(identities,fit) if m}
    assess_ids={i[2] for i,m in zip(identities,assess) if m}
    if fit_ids & assess_ids: raise ValueError('Student overlap')
    selected=baseline['selected_model']
    model_path=artifacts/(selected+'.joblib')
    artifact=joblib.load(model_path)
    if artifact['features']!=FEATURES: raise ValueError('Feature mismatch')
    with threadpool_limits(limits=2):
        raw=artifact['pipeline'].predict_proba(X)[:,1]
        sigmoid,isotonic=fit_maps(raw[fit],y[fit],weights[fit])
        predictions={'uncalibrated':raw[assess],
            'sigmoid':sigmoid.predict_proba(logit(raw[assess]))[:,1],
            'isotonic':isotonic.predict(raw[assess])}
    ay=y[assess]; aw=weights[assess]
    days=np.array([int(i[3]) for i in identities])[assess]
    group_counts={name:{'students':len(ids),'snapshots':int(mask.sum()),
        'snapshot_prevalence':float(y[mask].mean()),'enrollment_balanced_prevalence':float(np.average(y[mask],weights=weights[mask]))}
        for name,ids,mask in [('fit',fit_ids,fit),('assessment',assess_ids,assess)]}
    report={'test_accessed':False,'base_model_refitted':False,'base_model':selected,
        'assignment':'SHA256(acadmate-calibration-v1:student_id), first 8 hex digits modulo 2; even=fit',
        'student_overlap':0,'groups':group_counts,'model_sha256':digest(model_path),
        'input_sha256':{name:digest(splits/'validation'/(name+'.csv')) for name in ['features','labels']},
        'split_manifest_sha256':digest(splits/'manifest.json'),
        'sigmoid_slope':float(sigmoid.coef_[0,0]),'sigmoid_intercept':float(sigmoid.intercept_[0]),
        'assessment':{},'limitations':['Retrospective same-presentation holdout, not prospective calibration',
            'Base model was selected on full validation including assessment students; no unbiased model-selection estimate',
            'Final outcomes from calibration-fit students occur after early assessment snapshots',
            'Calibration cannot create missing early-course discrimination',
            'Pooled enrollment weights use eventual retained snapshot counts',
            'No formal uncertainty interval for calibration differences; no production probability guarantee',
            'No final method/threshold freeze or test evaluation']}
    for name,p in predictions.items():
        detail={'enrollment_balanced':metrics(ay,p,aw),'snapshot_weighted':metrics(ay,p),
            'calibration_bins':calibration(ay,p,aw),'by_week':{}}
        for day in sorted(set(days)):
            mask=days==day
            detail['by_week'][str(day)]={**metrics(ay[mask],p[mask]),'mean_probability':float(p[mask].mean())}
        report['assessment'][name]=detail
    report['diagnostic_lowest_brier']=min(predictions,key=lambda n:report['assessment'][n]['enrollment_balanced']['brier'])
    output.mkdir(parents=True)
    joblib.dump({'sigmoid':sigmoid,'isotonic':isotonic,'base_model_sha256':digest(model_path),
        'research_only':True,'fit_student_assignment':report['assignment']},output/'calibration_maps.joblib')
    (output/'calibration_assessment.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--splits',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.splits,args.artifacts,args.output)
    print(json.dumps({'groups':report['groups'],'assessment':{n:d['enrollment_balanced'] for n,d in report['assessment'].items()},
        'diagnostic_lowest_brier':report['diagnostic_lowest_brier']},indent=2))


if __name__=='__main__': main()
