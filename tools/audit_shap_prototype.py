"""Audit SHAP against actual frozen inference, without API/UI or model changes."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'ml/src')]


def main(output, main_snapshot=None):
    if output.exists():raise ValueError('NEW output directory required')
    from acadmate_ml.explain import background, explain
    from acadmate_ml.simulated_lms import build
    from services.research_predictions import PredictionService
    from acadmate_ml.splits import digest
    fixture=ROOT/'ml/fixtures/simulated_lms/events.json'
    document=build(json.loads(fixture.read_text(encoding='utf-8-sig')),ROOT/'data/synthetic')
    provenance={'fixture_sha256':digest(fixture)}
    if main_snapshot:
        main_snapshot=main_snapshot.resolve()
        if not main_snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):
            raise ValueError('Only prepared local main snapshot allowed')
        manifest=main_snapshot/'risk-main-manifest.json'
        meta=json.loads(manifest.read_text())
        from risk_mvp import service
        from risk_mvp.generate import parse
        from risk_mvp.main_data import snapshot,fingerprint
        from sqlalchemy import create_engine,text
        from sqlalchemy.orm import Session
        engine=create_engine('postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2',isolation_level='REPEATABLE READ')
        before=fingerprint(snapshot(engine))
        if before!=meta['academic_sha256']:raise ValueError('Academic provenance mismatch')
        with Session(engine) as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            for eid,cutoffs in sorted(meta['checkpoints'].items(),key=lambda item:int(item[0])):
                row=service.extract(db,int(eid),parse(cutoffs['28']))
                document['rows'].append({'enrollment_id':eid,'student_id':str(row['student_id']),
                                         'course_id':str(row['course_id']),'case':'main_day28_simulated_replay',
                                         'as_of_day':28,'source_kind':'synthetic_lms_demo',
                                         'status':row['status'],'reason':row['reason'],'features':row['features']})
        if before!=fingerprint(snapshot(engine)):raise ValueError('Academic records changed')
        engine.dispose()
        provenance.update(main_manifest_sha256=digest(manifest),academic_sha256=before)
    config=ROOT/'ml/configs/FINAL_EXPERIMENT_V1.json'
    model=ROOT/'ml/outputs/baselines-v1/logistic_regression.joblib'
    maps=ROOT/'ml/outputs/calibration-v1/calibration_maps.joblib'
    protected=[config,model,maps,*sorted((ROOT/'data/synthetic').glob('*.csv'))]
    original={str(p.relative_to(ROOT)):digest(p) for p in protected}
    pipeline,sigmoid=PredictionService()._load()
    first,ref=background(ROOT,28,128,42)
    alternative,other=background(ROOT,28,128,43)
    # This run cannot read outcomes or any reserved evaluation cohort.
    open_original=Path.open
    def guarded(path,*args,**kwargs):
        if path.name=='labels.csv' or path.parent.name in ('validation','test'):
            raise AssertionError('Labels or reserved evaluation data accessed')
        return open_original(path,*args,**kwargs)
    with patch.object(Path,'open',guarded), \
         patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No model retraining')), \
         patch('sklearn.linear_model.LogisticRegression.fit',side_effect=AssertionError('No calibration refitting')):
        result=explain(document,pipeline,sigmoid,{28:first})
        sensitivity=explain(document,pipeline,sigmoid,{28:alternative})
    assert original=={str(p.relative_to(ROOT)):digest(p) for p in protected}
    scored=[r for r in result['rows'] if r['explanation']]
    second={r['enrollment_id']:r for r in sensitivity['rows']}
    top3=[];changes=[]
    for row in scored:
        a=row['explanation'];b=second[row['enrollment_id']]['explanation']
        assert row['research_risk_probability']==second[row['enrollment_id']]['research_risk_probability']
        top3.append(len(set(a['ranked_features'][:3])&set(b['ranked_features'][:3]))/3)
        changes.append(abs(a['baseline_raw_log_odds']-b['baseline_raw_log_odds']))
    summary={'primary_checks':result['checks'],'alternative_background_checks':sensitivity['checks'],
             'explained_rows':len(scored),'unavailable_rows':len(result['rows'])-len(scored),
             'same_day_training_background':ref,'alternative_background':other,
             'mean_top3_overlap_fraction':sum(top3)/len(top3),
             'max_baseline_change_log_odds':max(changes),
             'frozen_artifacts_config_and_academic_csvs_unchanged':True,
             'labels_validation_test_or_holdout_read':False,
             'interpretation':'Numerical explanation validation only; background sensitivity is descriptive, not a pass/fail accuracy test',
             'provenance':provenance,'protected_sha256':original,'limits':result['limits']}
    output.mkdir(parents=True)
    result['background']=ref;result['provenance']=provenance
    (output/'explanations.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (output/'background-sensitivity.json').write_text(json.dumps(sensitivity,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (output/'verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--main-snapshot',type=Path)
    args=parser.parse_args();main(args.output,args.main_snapshot)
