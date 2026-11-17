"""Freeze an experiment before consuming reserved test rows; evaluate once."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

from .calibrate import logit
from .features import FEATURES
from .splits import digest
from .train import load_partition, metrics, calibration, outreach
from .uncertainty import Ranking, cluster_multipliers, interval


def freeze(splits,models,maps,path):
    if path.exists(): raise ValueError('Freeze file exists; refusing to overwrite')
    baseline=json.loads((models/'validation_metrics.json').read_text(encoding='utf-8'))
    assessment=json.loads((maps/'calibration_assessment.json').read_text(encoding='utf-8'))
    if baseline['selected_model']!='logistic_regression' or assessment['base_model']!='logistic_regression':
        raise ValueError('Expected previously selected logistic regression')
    model_hash=digest(models/'logistic_regression.joblib')
    if assessment['model_sha256']!=model_hash:
        raise ValueError('Calibration/base-model provenance mismatch')
    split_hash=digest(splits/'manifest.json')
    if baseline['split_manifest_sha256']!=split_hash or assessment['split_manifest_sha256']!=split_hash:
        raise ValueError('Split provenance mismatch')
    frozen={'version':1,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'primary':'logistic_regression_with_existing_sigmoid', 'comparison':'same_model_uncalibrated',
        'features':FEATURES,'threshold':0.5,'threshold_role':'diagnostic only',
        'pooled_weights':'one total vote per retained enrollment', 'weekly_weights':'one vote per active enrollment',
        'bootstrap_replicates':300,'bootstrap_seed':42,'outreach_fractions':[0.1,0.2],
        'model_sha256':model_hash,'maps_sha256':digest(maps/'calibration_maps.joblib'),
        'split_manifest_sha256':split_hash,
        'baseline_report_sha256':digest(models/'validation_metrics.json'),
        'calibration_report_sha256':digest(maps/'calibration_assessment.json'),
        'source_sha256':{name:digest(Path(__file__).parent/name) for name in ['evaluate.py','features.py','train.py','calibrate.py','uncertainty.py','splits.py']},
        'policy':'No refitting, new candidate models, calibration selection, or threshold tuning after test access',
        'limits':['Course-end final-label maturity proxy; actual availability unverified',
            'No validation evidence for days 7-21', 'Research prototype; no verified Brightspace mapping']}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(frozen,stream,indent=2);stream.write('\n')
    return frozen


def evaluate(splits,models,maps,freeze_path,output):
    config=json.loads(freeze_path.read_text(encoding='utf-8'))
    if config['features']!=FEATURES or config['threshold']!=0.5 or config['primary']!='logistic_regression_with_existing_sigmoid':
        raise ValueError('Unsupported frozen specification')
    files=[(models/'logistic_regression.joblib','model_sha256'),(maps/'calibration_maps.joblib','maps_sha256'),
        (splits/'manifest.json','split_manifest_sha256'),(models/'validation_metrics.json','baseline_report_sha256'),
        (maps/'calibration_assessment.json','calibration_report_sha256')]
    for path,field in files:
        if digest(path)!=config[field]: raise ValueError('Frozen provenance mismatch: '+field)
    for name,expected in config['source_sha256'].items():
        if digest(Path(__file__).parent/name)!=expected: raise ValueError('Frozen implementation changed')
    manifest=json.loads((splits/'manifest.json').read_text(encoding='utf-8'))
    if any(manifest['student_overlap_counts'].values()): raise ValueError('Student overlap in manifest')
    base=joblib.load(models/'logistic_regression.joblib')
    mapping=joblib.load(maps/'calibration_maps.joblib')
    if base['features']!=FEATURES or mapping['base_model_sha256']!=config['model_sha256']:
        raise ValueError('Artifact linkage mismatch')
    # Atomic marker exists before test rows are read; failed attempts remain visible.
    output.mkdir(parents=True,exist_ok=False)
    marker=output/'EVALUATION_STARTED.json'
    marker.write_text(json.dumps({'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'freeze_sha256':digest(freeze_path),'status':'STARTED; do not silently rerun on failure'},indent=2),encoding='utf-8')
    X,y,ids,weights,outcomes=load_partition(splits/'test')
    if len(y)!=manifest['partitions']['test']['snapshots']: raise ValueError('Test row-count mismatch')
    test_ids={i[2] for i in ids}
    known_students=set(); familiar=set()
    for partition in ['train','validation']:
        # Read identity metadata only for independent overlap audit.
        import csv
        with (splits/partition/'features.csv').open(newline='',encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                known_students.add(row['id_student'])
                if partition=='train': familiar.add(row['code_module'])
    if test_ids & known_students: raise ValueError('Actual test student overlap')
    with threadpool_limits(limits=2):
        raw=base['pipeline'].predict_proba(X)[:,1]
        mapped=mapping['sigmoid'].predict_proba(logit(raw))[:,1]
    predictions={'sigmoid_primary':mapped,'uncalibrated_comparison':raw}
    days=np.array([int(i[3]) for i in ids]); modules=np.array([i[0] for i in ids])
    result={'frozen_at_utc':config['frozen_at_utc'],'freeze_sha256':digest(freeze_path),
        'evaluated_at_utc':datetime.now(timezone.utc).isoformat(),'models_refitted':False,
        'students':len(test_ids),'enrollments':len({i[:3] for i in ids}),'snapshots':len(y),
        'student_overlap':0,'test_input_sha256':{n:digest(splits/'test'/(n+'.csv')) for n in ['features','labels']},
        'results':{},'limitations':config['limits']+['Single 2014J cohort, not institution-level replication',
            'Bootstrap conditional on fixed models, not retraining uncertainty',
            'Pointwise percentile intervals; no multiple comparison correction',
            'No retuning permitted using these test results']}
    ranks={name:Ranking(y,p) for name,p in predictions.items()}
    draws={name:[] for name in predictions}; briers={name:[] for name in predictions}
    rng=np.random.default_rng(config['bootstrap_seed'])
    student_array=np.array([i[2] for i in ids])
    for repeat in range(config['bootstrap_replicates']):
        w=weights*cluster_multipliers(student_array,rng)
        for name,p in predictions.items():
            draws[name].append(ranks[name].calculate(w))
            briers[name].append(float(np.average((p-y)**2,weights=w)))
        if (repeat+1)%50==0: print(f'Test bootstrap {repeat+1}/{config["bootstrap_replicates"]}',flush=True)
    for name,p in predictions.items():
        detail={'enrollment_balanced':metrics(y,p,weights),'snapshot_weighted':metrics(y,p),
            'weighted_mean_probability':float(np.average(p,weights=weights)),
            'calibration_bins':calibration(y,p,weights),'by_week':{},'by_module':{},'by_module_coverage':{},
            'outcome_recall_at_0_5':{outcome:float(np.average(p[outcomes==outcome]>=0.5,weights=weights[outcomes==outcome]))
                                    for outcome in ['Fail','Withdrawn'] if (outcomes==outcome).any()},
            'hypothetical_student_outreach':outreach(ids,y,p),
            'pooled_intervals':{metric:interval(np.array(draws[name])[:,j],detail_point)
                for j,(metric,detail_point) in enumerate(zip(['average_precision','roc_auc'],ranks[name].calculate(weights)))}}
        for day in sorted(set(days)):
            mask=days==day
            detail['by_week'][str(day)]={**metrics(y[mask],p[mask]),'mean_probability':float(p[mask].mean())}
        for module in sorted(set(modules)):
            mask=modules==module
            detail['by_module'][module]=metrics(y[mask],p[mask],weights[mask])
        for group,mask in [('familiar',np.isin(modules,list(familiar))),('unseen',~np.isin(modules,list(familiar)))]:
            if mask.any(): detail['by_module_coverage'][group]=metrics(y[mask],p[mask],weights[mask])
        result['results'][name]=detail
    differences=np.array(briers['sigmoid_primary'])-np.array(briers['uncalibrated_comparison'])
    result['paired_brier_primary_minus_comparison']=interval(differences,
        result['results']['sigmoid_primary']['enrollment_balanced']['brier']-result['results']['uncalibrated_comparison']['enrollment_balanced']['brier'])
    (output/'final_test_metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (output/'EVALUATION_COMPLETED.json').write_text(json.dumps({'completed_at_utc':datetime.now(timezone.utc).isoformat(),
        'metrics_sha256':digest(output/'final_test_metrics.json'),'freeze_sha256':digest(freeze_path)},indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','evaluate'])
    parser.add_argument('--splits',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--calibration',type=Path,required=True)
    parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='freeze':
        freeze(args.splits,args.models,args.calibration,args.freeze)
        print('Experiment frozen; test files not opened')
    else:
        if args.output is None: parser.error('--output required for evaluate')
        result=evaluate(args.splits,args.models,args.calibration,args.freeze,args.output)
        print(json.dumps({name:d['enrollment_balanced'] for name,d in result['results'].items()},indent=2))


if __name__=='__main__':main()
