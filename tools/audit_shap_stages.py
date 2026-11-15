"""Read-only cohort audit for preceding-week SHAP reference policy."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'ml/src')]


def audit(snapshot,output):
    if output.exists():raise ValueError('New output file required')
    snapshot=snapshot.resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):raise ValueError('Local main snapshot required')
    from risk_mvp.service import extract,MODEL
    from risk_mvp.main_data import snapshot as read_snapshot,fingerprint
    from risk_mvp.generate import parse
    from acadmate_ml.explain import explain,background,REFERENCE_POLICY,stage_reference_day
    from sqlalchemy import create_engine,text
    from sqlalchemy.orm import Session
    from datetime import timedelta
    from acadmate_ml.splits import digest
    manifest=json.loads((snapshot/'risk-main-manifest.json').read_text())
    engine=create_engine('postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2',isolation_level='REPEATABLE READ')
    before=fingerprint(read_snapshot(engine));assert before==manifest['academic_sha256']
    model,maps=MODEL._load();cache={};reports=[]
    protected=[ROOT/'ml/configs/FINAL_EXPERIMENT_V1.json',ROOT/'ml/outputs/baselines-v1/logistic_regression.joblib',ROOT/'ml/outputs/calibration-v1/calibration_maps.joblib']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in protected}
    opener=Path.open
    def guard(path,*args,**kwargs):
        if path.name=='labels.csv' or path.parent.name in ('test','validation'):raise AssertionError('Reserved data/labels accessed')
        return opener(path,*args,**kwargs)
    with Session(engine) as db,patch.object(Path,'open',guard),patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No refitting')),patch('sklearn.linear_model.LogisticRegression.fit',side_effect=AssertionError('No calibration refitting')):
        db.execute(text('SET TRANSACTION READ ONLY'))
        for day in [7,8,13,14,20,21,27,28,34,35,38,41,42,56,84]:
            reference_day=stage_reference_day(day)
            if reference_day not in cache:
                cache[reference_day]=[background(ROOT,reference_day,128,seed) for seed in [42,43]]
            rows=[]
            for eid,cutoffs in manifest['checkpoints'].items():
                cutoff=parse(cutoffs['28'])+timedelta(days=day-28)
                row=extract(db,int(eid),cutoff)
                rows.append(dict(enrollment_id=eid,student_id=str(row['student_id']),course_id=str(row['course_id']),
                                 as_of_day=day,case='main_stage_simulation',source_kind='synthetic_lms_demo',
                                 status=row['status'],reason=row['reason'],features=row['features']))
            document=dict(schema_version='1.0',source_kind='synthetic_lms_demo',as_of_day=day,rows=rows)
            outputs=[]
            for bg,meta in cache[reference_day]:
                reference=dict(meta,policy=REFERENCE_POLICY,prediction_day=day,reference_day=reference_day,reference_age_days=day-reference_day)
                outputs.append(explain(document,model,maps,{day:bg},reference=reference))
            assert [r['research_risk_probability'] for r in outputs[0]['rows']]==[r['research_risk_probability'] for r in outputs[1]['rows']]
            comparisons=[(a['explanation'],b['explanation']) for a,b in zip(outputs[0]['rows'],outputs[1]['rows']) if a['explanation']]
            overlaps=[len(set(a['ranked_features'][:3])&set(b['ranked_features'][:3]))/3 for a,b in comparisons]
            report={'prediction_day':day,'reference_day':reference_day,'reference_age_days':day-reference_day,
                    'primary_checks':outputs[0]['checks'],'secondary_checks':outputs[1]['checks'],
                    'unavailable_rows':len(rows)-len(comparisons),'mean_top3_overlap_fraction':sum(overlaps)/len(overlaps)}
            reports.append(report);print('CHECKED',day,'reference',reference_day,'explained',len(comparisons),flush=True)
    assert before==fingerprint(read_snapshot(engine));engine.dispose()
    assert hashes=={str(p.relative_to(ROOT)):digest(p) for p in protected}
    result={'reference_policy':REFERENCE_POLICY,'stages':reports,'academic_records_and_frozen_artifacts_unchanged':True,
            'labels_validation_test_or_holdout_read':False,'model_refitted':False,'protected_sha256':hashes,
            'interpretation':'Numerical reconstruction and background sensitivity only, not predictive or causal validation'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print('ALL STAGES PASSED',sum(r['primary_checks']['explained_rows'] for r in reports))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();audit(args.snapshot,args.output)
