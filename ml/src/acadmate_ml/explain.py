"""Isolated interventional SHAP audit of the unchanged frozen logistic model.

Explains raw log-odds, NOT additive calibrated probability contributions.
Never opens labels, validation, test, or holdout evaluation files.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import expit
from threadpoolctl import threadpool_limits
from .features import FEATURES, KEY
from .splits import digest
from .calibrate import logit
from .predict import predict

ROOT = Path(__file__).resolve().parents[3]
LIMITATIONS = [
    'Explains the raw logistic score in log-odds; contributions are not percentage-point effects on calibrated probability.',
    'Interventional masking does not preserve correlations among engagement and timing features.',
    'Missing-value indicator contributions are grouped with their original feature.',
    'Background is an outcome-independent sample of original training snapshots at an explicitly declared course-stage checkpoint.',
    'SHAP describes model behavior relative to a background, not causality, a diagnosis or an intervention recommendation.',
    'Synthetic explanation checks do not validate accuracy on AcadMate or Brightspace students.',
]


def background(root, day=28, size=128, seed=42):
    if not isinstance(size,int) or not 2<=size<=1024:raise ValueError('Background size must be 2..1024')
    ml=Path(root)/'ml'
    config=json.loads((ml/'configs/FINAL_EXPERIMENT_V1.json').read_text(encoding='utf-8'))
    report_path=ml/'outputs/baselines-v1/validation_metrics.json'
    if digest(report_path)!=config['baseline_report_sha256']:raise ValueError('Baseline report hash mismatch')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    folder=ml/'outputs/oulad-splits-v1'
    if digest(folder/'manifest.json')!=config['split_manifest_sha256']:raise ValueError('Split manifest hash mismatch')
    source=folder/'train/features.csv'
    if digest(source)!=report['inputs']['train/features.csv']:raise ValueError('Training features hash mismatch')
    candidates=[];seen=set()
    with source.open(newline='',encoding='utf-8') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=[*KEY,'snapshot_day',*FEATURES]:raise ValueError('Background feature schema mismatch')
        for row in reader:
            if int(row['snapshot_day'])!=day:continue
            identity=tuple(row[k] for k in [*KEY,'snapshot_day'])
            if identity in seen:raise ValueError('Duplicate background enrollment snapshot')
            seen.add(identity)
            values=[float(row[f]) if row[f] else np.nan for f in FEATURES]
            if np.isinf(values).any() or values[FEATURES.index('course_day')]!=day:raise ValueError('Invalid background values')
            priority=hashlib.sha256((str(seed)+':'+':'.join(identity)).encode()).hexdigest()
            candidates.append((priority,values))
    if len(candidates)<2:raise ValueError('Insufficient training background at requested day')
    chosen=sorted(candidates,key=lambda row:row[0])[:size]
    values=np.asarray([row[1] for row in chosen],dtype=float)
    return values,{'source':'verified_original_training_features_only','course_day':day,
                   'requested_size':size,'actual_size':len(chosen),'eligible_rows':len(candidates),'seed':seed,
                   'selection':'smallest SHA256(seed:enrollment-key:snapshot-day), without outcomes',
                   'training_features_sha256':digest(source),
                   'selected_rows_sha256':hashlib.sha256(json.dumps([p for p,_ in chosen]).encode()).hexdigest()}


REFERENCE_POLICY = 'preceding_weekly_training_checkpoint_v1'


def stage_reference_day(day):
    if type(day) is not int or day < 7:
        raise ValueError('Explanation requires integer course day 7 or later')
    return (day // 7) * 7


def stage_background(root, day, size=128, seed=42):
    reference_day=stage_reference_day(day)
    values,metadata=background(root,reference_day,size,seed)
    metadata.update(policy=REFERENCE_POLICY,prediction_day=day,reference_day=reference_day,
                    reference_age_days=day-reference_day)
    return values,metadata


def explain(document, pipeline, sigmoid, backgrounds, reference=None):
    # The unchanged inference validator remains the authority on eligibility and input schema.
    with threadpool_limits(limits=2):scored=predict(document,pipeline,sigmoid)
    ready=[(i,row) for i,row in enumerate(document['rows']) if row['status']=='ready']
    if not ready:
        return {'explained_output':'raw_logistic_log_odds','rows':[dict(row,explanation=None) for row in scored['rows']],
                'limits':LIMITATIONS,'checks':{'explained_rows':0}}
    if list(pipeline.named_steps)!=['imputer','scaler','classifier']:
        raise ValueError('Unsupported frozen preprocessing')
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    if not isinstance(pipeline[0],SimpleImputer) or not isinstance(pipeline[1],StandardScaler) or not isinstance(pipeline[-1],LogisticRegression):
        raise ValueError('Only frozen separable numeric logistic pipeline supported')
    if pipeline.classes_.tolist()!=[0,1] or sigmoid.classes_.tolist()!=[0,1]:raise ValueError('Unexpected target class ordering')
    import shap
    X=np.array([[np.nan if row['features'][f] is None else row['features'][f] for f in FEATURES] for _,row in ready],dtype=float)
    bg=np.asarray(backgrounds[document['as_of_day']],dtype=float)
    if bg.ndim!=2 or bg.shape[1]!=len(FEATURES) or len(bg)<2 or np.isinf(bg).any():raise ValueError('Invalid background matrix')
    reference_day=document['as_of_day']
    if reference is not None:
        reference_day=stage_reference_day(document['as_of_day'])
        if reference.get('policy')!=REFERENCE_POLICY or reference.get('prediction_day')!=document['as_of_day'] or reference.get('reference_day')!=reference_day or reference.get('course_day')!=reference_day:
            raise ValueError('Invalid stage-reference provenance')
    if not np.all(bg[:,FEATURES.index('course_day')]==reference_day):raise ValueError('Background course-day mismatch')
    prep=pipeline[:-1];classifier=pipeline[-1]
    with threadpool_limits(limits=2):
        Z=prep.transform(X);B=prep.transform(bg)
        names=prep.get_feature_names_out(FEATURES).tolist()
        if not np.isfinite(Z).all() or not np.isfinite(B).all():raise ValueError('Invalid transformed values')
        masker=shap.maskers.Independent(B,max_samples=len(B))
        explainer=shap.LinearExplainer(classifier,masker)
        explanation=explainer(Z)
        values=np.asarray(explanation.values)
        expected=float(explainer.expected_value)
        raw=pipeline.decision_function(X)
        reconstructed=expected+values.sum(axis=1)
        np.testing.assert_allclose(reconstructed,raw,atol=1e-9,rtol=1e-9)
        grouped=np.zeros((len(X),len(FEATURES)))
        for column,name in enumerate(names):
            original=name.removeprefix('missingindicator_')
            if original not in FEATURES:raise ValueError('Unmapped transformed feature')
            grouped[:,FEATURES.index(original)]+=values[:,column]
        # Independently replace ONE raw feature across training-background rows.
        # This also verifies missing-indicator grouping through the full preprocessing pipeline.
        baseline=pipeline.decision_function(bg).mean()
        direct=np.empty_like(grouped)
        for i,row in enumerate(X):
            for column in range(len(FEATURES)):
                hybrid=bg.copy();hybrid[:,column]=row[column]
                direct[i,column]=pipeline.decision_function(hybrid).mean()-baseline
        np.testing.assert_allclose(grouped,direct,atol=1e-9,rtol=1e-9)
        calibrated=sigmoid.predict_proba(logit(expit(reconstructed)))[:,1]
        actual=np.array([scored['rows'][i]['research_risk_probability'] for i,_ in ready])
        np.testing.assert_allclose(calibrated,actual,atol=1e-12,rtol=1e-12)
    rows=[dict(row,explanation=None) for row in scored['rows']]
    for n,(index,row) in enumerate(ready):
        contributions=[{'feature':f,'input_value':row['features'][f],
                        'raw_log_odds_contribution':float(grouped[n,column]),
                        'direction':'increases_raw_score' if grouped[n,column]>0 else 'decreases_raw_score' if grouped[n,column]<0 else 'no_change',
                        'includes_missing_indicator':('missingindicator_'+f) in names}
                       for column,f in enumerate(FEATURES)]
        rows[index]['explanation']={'explained_output':'raw_logistic_log_odds','target':'failure_or_withdrawal',
                                   'baseline_raw_log_odds':expected,'raw_log_odds':float(raw[n]),
                                   'reconstructed_raw_log_odds':float(reconstructed[n]),
                                   'reconstructed_calibrated_probability':float(calibrated[n]),
                                   'contributions':contributions,
                                   'ranked_features':[v['feature'] for v in sorted(contributions,key=lambda v:-abs(v['raw_log_odds_contribution']))]}
    return {'schema_version':'1.0','research_only':True,'explained_output':'raw_logistic_log_odds',
            'method':'shap.LinearExplainer / Independent masker','shap_version':shap.__version__,
            'features':FEATURES,'transformed_features':names,'limits':LIMITATIONS,'rows':rows,
            'background_reference':reference or {'policy':'exact_day_training','prediction_day':document['as_of_day'],'reference_day':document['as_of_day']},
            'checks':{'explained_rows':len(ready),'transformed_feature_count':len(names),
                      'max_raw_additivity_error':float(np.max(np.abs(reconstructed-raw))),
                      'max_grouped_raw_perturbation_error':float(np.max(np.abs(grouped-direct))),
                      'max_calibrated_probability_error':float(np.max(np.abs(calibrated-actual))),
                      'test_or_validation_data_accessed':False,'model_refitted':False}}


def run(root, output, input_path=None, size=128, seed=42):
    root=Path(root).resolve();output=Path(output)
    if output.exists():raise ValueError('Output exists; refusing to overwrite')
    from services.research_predictions import PredictionService
    from .simulated_lms import build
    service=PredictionService(root=root)
    if input_path:
        document=json.loads(Path(input_path).read_text(encoding='utf-8'))
    else:
        fixture=json.loads((root/'ml/fixtures/simulated_lms/events.json').read_text(encoding='utf-8-sig'))
        document=build(fixture,root/'data/synthetic')
    if all(row.get('status')=='unavailable' for row in document['rows']):
        result=explain(document,None,None,{})
        result['background']=None
        result['provenance']={'explainer_source_sha256':digest(Path(__file__))}
    else:
        # Hash-check both frozen artifacts and frozen source before trusted deserialization.
        pipeline,sigmoid=service._load()
        day=document['as_of_day'];bg,provenance=background(root,day,size,seed)
        result=explain(document,pipeline,sigmoid,{day:bg})
        result['background']=provenance
        result['provenance']={'model_sha256':digest(root/'ml/outputs/baselines-v1/logistic_regression.joblib'),
                              'maps_sha256':digest(root/'ml/outputs/calibration-v1/calibration_maps.joblib'),
                              'freeze_sha256':digest(root/'ml/configs/FINAL_EXPERIMENT_V1.json'),
                              'explainer_source_sha256':digest(Path(__file__))}
    if input_path:result['provenance']['input_sha256']=digest(Path(input_path))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--background-size',type=int,default=128)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    result=run(args.root,args.output,args.input,args.background_size,args.seed)
    print(json.dumps(result['checks'],indent=2))
