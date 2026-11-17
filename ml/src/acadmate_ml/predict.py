"""Research-only local inference for validated synthetic LMS feature records."""
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

WARNINGS=['Synthetic software demonstration; no predictive accuracy claim for these students.',
    'OULAD-trained model is not validated on Brightspace or AcadMate institutional data.',
    'Early-course probabilities may overestimate risk; no automatic advisor-alert policy.']


def predict(document,pipeline,sigmoid):
    if document.get('schema_version')!='1.0' or document.get('source_kind')!='synthetic_lms_demo':
        raise ValueError('Expected validated synthetic demo features')
    rows=[]; vectors=[]; positions=[]; seen=set()
    for row in document['rows']:
        eid=row['enrollment_id']
        if eid in seen: raise ValueError('Duplicate enrollment')
        seen.add(eid)
        if row['source_kind']!='synthetic_lms_demo' or row['as_of_day']!=document['as_of_day']:
            raise ValueError('Mixed provenance or snapshot days')
        result={field:row[field] for field in ['enrollment_id','student_id','course_id','as_of_day','case']}
        result.update(status='unavailable',research_risk_probability=None,reason=row['reason'],warnings=WARNINGS)
        if row['status']=='unavailable':
            if row['features'] is not None or not row['reason']: raise ValueError('Invalid unavailable record')
        elif row['status']=='ready':
            features=row['features']
            if not isinstance(features,dict) or set(features)!=set(FEATURES): raise ValueError('Feature schema mismatch')
            vector=[]
            for name in FEATURES:
                value=features[name]
                if value is not None and (type(value) not in [int,float] or not np.isfinite(value)):
                    raise ValueError('Invalid numeric feature '+name)
                vector.append(np.nan if value is None else value)
            if features['course_day']!=row['as_of_day']: raise ValueError('Feature/as-of day mismatch')
            positions.append(len(rows));vectors.append(vector)
        else: raise ValueError('Unknown input status')
        rows.append(result)
    if vectors:
        with threadpool_limits(limits=2):
            raw=pipeline.predict_proba(np.asarray(vectors))[:,1]
            calibrated=sigmoid.predict_proba(logit(raw))[:,1]
        if not np.isfinite(calibrated).all() or ((calibrated<0)|(calibrated>1)).any(): raise ValueError('Invalid model probability')
        for position,probability in zip(positions,calibrated):
            rows[position].update(status='scored_research_demo',research_risk_probability=float(probability),reason=None)
    return {'schema_version':'1.0','source_kind':'synthetic_lms_demo','rows':rows,
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),'model_refitted':False,
        'prediction_target':'eventual failure or subsequent withdrawal from this course',
        'warnings':WARNINGS}


def run(input_path,model_path,map_path,freeze_path,output):
    if output.exists(): raise ValueError('Output exists; refusing to overwrite')
    config=json.loads(freeze_path.read_text(encoding='utf-8'))
    if config['primary']!='logistic_regression_with_existing_sigmoid' or config['features']!=FEATURES:
        raise ValueError('Unsupported frozen specification')
    if digest(model_path)!=config['model_sha256'] or digest(map_path)!=config['maps_sha256']:
        raise ValueError('Frozen artifact hash mismatch')
    for name,expected in config['source_sha256'].items():
        if digest(Path(__file__).parent/name)!=expected: raise ValueError('Frozen research source changed')
    # Only load trusted local model artifacts after checking hashes.
    base=joblib.load(model_path);maps=joblib.load(map_path)
    if base['features']!=FEATURES or maps['base_model_sha256']!=config['model_sha256']:
        raise ValueError('Artifact feature/linkage mismatch')
    result=predict(json.loads(input_path.read_text(encoding='utf-8-sig')),base['pipeline'],maps['sigmoid'])
    result['provenance']={'input_sha256':digest(input_path),'freeze_sha256':digest(freeze_path),
        'model_sha256':config['model_sha256'],'maps_sha256':config['maps_sha256']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ['input','model','calibration','freeze','output']:parser.add_argument('--'+flag,type=Path,required=True)
    args=parser.parse_args()
    result=run(args.input,args.model,args.calibration,args.freeze,args.output)
    for row in result['rows']:
        print(row['enrollment_id'],row['case'],row['status'],row['research_risk_probability'])


if __name__=='__main__':main()
