import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from acadmate_ml.features import FEATURES, KEY
from acadmate_ml.calibrate import logit
from acadmate_ml.explain import explain, background, run
from acadmate_ml.splits import digest


def toy_models():
    rng=np.random.default_rng(17)
    X=rng.uniform(0,10,size=(64,len(FEATURES)))
    X[:,0]=28;X[:,1]=.25;X[:,2]=28
    for i,name in enumerate(['engagement_change','days_since_activity','late_submission_rate','days_since_submission']):
        X[i::5,FEATURES.index(name)]=np.nan
    y=(X[:,3]>5).astype(int)
    p=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),('scaler',StandardScaler()),('classifier',LogisticRegression())]).fit(X,y)
    sigmoid=LogisticRegression().fit(logit(p.predict_proba(X)[:,1]),y)
    return X,p,sigmoid


def document(X):
    return {'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':28,'rows':[
        {'enrollment_id':str(i),'student_id':'synthetic','course_id':'synthetic','case':'toy_unit_fixture','as_of_day':28,'source_kind':'synthetic_lms_demo','status':'ready','reason':None,
         'features':{f:None if np.isnan(v) else float(v) for f,v in zip(FEATURES,row)}} for i,row in enumerate(X)]}


class BackgroundTests(unittest.TestCase):
    def build_root(self,root):
        ml=root/'ml';train=ml/'outputs/oulad-splits-v1/train';train.mkdir(parents=True)
        (ml/'configs').mkdir();(ml/'outputs/baselines-v1').mkdir()
        source=train/'features.csv'
        with source.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=[*KEY,'snapshot_day',*FEATURES]);writer.writeheader()
            for i in range(10):
                row={k:str(i) for k in KEY};row.update(snapshot_day=28,**{f:28 if f=='course_day' else i for f in FEATURES});writer.writerow(row)
        manifest=train.parent/'manifest.json';manifest.write_text('{}')
        report=ml/'outputs/baselines-v1/validation_metrics.json';report.write_text(json.dumps({'inputs':{'train/features.csv':digest(source)}}))
        (ml/'configs/FINAL_EXPERIMENT_V1.json').write_text(json.dumps({'baseline_report_sha256':digest(report),'split_manifest_sha256':digest(manifest)}))
        return source

    def test_verified_deterministic_training_only_background(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.build_root(root)
            original=Path.open
            def guarded(path,*args,**kwargs):
                if path.name=='labels.csv' or path.parent.name in ('test','validation'):raise AssertionError('Holdout/labels accessed')
                return original(path,*args,**kwargs)
            with patch.object(Path,'open',guarded):
                a,meta=background(root,28,4,42);b,other=background(root,28,4,42);c,changed=background(root,28,4,43)
            np.testing.assert_equal(a,b);self.assertEqual(meta,other)
            self.assertNotEqual(meta['selected_rows_sha256'],changed['selected_rows_sha256'])
            self.assertEqual(meta['actual_size'],4)

    def test_changed_training_data_and_missing_day_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=self.build_root(root)
            with self.assertRaisesRegex(ValueError,'Insufficient'):background(root,14)
            source.write_text('tampered')
            with self.assertRaisesRegex(ValueError,'Training features hash mismatch'):background(root)

    def test_unavailable_needs_no_model_or_shap(self):
        doc={'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':28,'rows':[
            {'enrollment_id':'1','student_id':'1','course_id':'1','as_of_day':28,'case':'missing','source_kind':'synthetic_lms_demo','status':'unavailable','reason':'Incomplete coverage','features':None}]}
        result=explain(doc,None,None,{})
        self.assertIsNone(result['rows'][0]['explanation']);self.assertIsNone(result['rows'][0]['research_risk_probability'])

    def test_unavailable_cli_never_loads_artifacts_or_background(self):
        doc={'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':28,'rows':[
            {'enrollment_id':'1','student_id':'1','course_id':'1','as_of_day':28,'case':'missing','source_kind':'synthetic_lms_demo','status':'unavailable','reason':'Incomplete coverage','features':None}]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'input.json';source.write_text(json.dumps(doc))
            with patch('services.research_predictions.PredictionService._load',side_effect=AssertionError('No model load')),patch('acadmate_ml.explain.background',side_effect=AssertionError('No background read')):
                result=run(root,root/'result.json',source)
            self.assertIsNone(result['rows'][0]['explanation'])
            self.assertIsNone(result['background'])

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.json';path.write_text('preserved')
            with self.assertRaisesRegex(ValueError,'Output exists'):run(Path(d),path)
            self.assertEqual(path.read_text(),'preserved')


@unittest.skipUnless(importlib.util.find_spec('shap'), 'Optional SHAP environment required')
class ShapTests(unittest.TestCase):
    def setUp(self):self.X,self.pipeline,self.sigmoid=toy_models()

    def test_additivity_missing_indicators_and_calibration_without_fit(self):
        with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No refitting')),patch('sklearn.linear_model.LogisticRegression.fit',side_effect=AssertionError('No calibration refitting')):
            result=explain(document(self.X[:4]),self.pipeline,self.sigmoid,{28:self.X[4:]})
        self.assertEqual(result['checks']['transformed_feature_count'],20)
        self.assertLess(result['checks']['max_raw_additivity_error'],1e-9)
        self.assertLess(result['checks']['max_grouped_raw_perturbation_error'],1e-9)
        self.assertLess(result['checks']['max_calibrated_probability_error'],1e-12)
        self.assertEqual(len(result['rows'][0]['explanation']['contributions']),16)
        contribution=next(c for c in result['rows'][0]['explanation']['contributions'] if c['feature']=='engagement_change')
        self.assertIsNone(contribution['input_value']);self.assertTrue(contribution['includes_missing_indicator'])

    def test_row_order_and_background_repeatability(self):
        doc=document(self.X[:3]);a=explain(doc,self.pipeline,self.sigmoid,{28:self.X[3:]})
        rev=copy.deepcopy(doc);rev['rows'].reverse();b=explain(rev,self.pipeline,self.sigmoid,{28:self.X[3:]})
        for first,second in zip(a['rows'],reversed(b['rows'])):
            one,two=first['explanation'],second['explanation']
            self.assertEqual(one['ranked_features'],two['ranked_features'])
            np.testing.assert_allclose([one['raw_log_odds'],one['reconstructed_calibrated_probability']],
                                       [two['raw_log_odds'],two['reconstructed_calibrated_probability']],atol=1e-12,rtol=1e-12)
            np.testing.assert_allclose([v['raw_log_odds_contribution'] for v in one['contributions']],
                                       [v['raw_log_odds_contribution'] for v in two['contributions']],atol=1e-12,rtol=1e-12)

    def test_clipped_calibration_reconstructed_but_not_claimed_additive(self):
        self.pipeline[-1].coef_*=1000  # disposable toy model, never a frozen artifact
        result=explain(document(self.X[:2]),self.pipeline,self.sigmoid,{28:self.X[2:]})
        self.assertLess(result['checks']['max_calibrated_probability_error'],1e-12)
        self.assertEqual(result['explained_output'],'raw_logistic_log_odds')
        self.assertTrue(any(abs(r['explanation']['raw_log_odds'])>14 for r in result['rows']))

    def test_wrong_day_and_invalid_feature_inputs_rejected(self):
        bg=self.X.copy();bg[:,0]=14
        with self.assertRaisesRegex(ValueError,'course-day mismatch'):explain(document(self.X[:1]),self.pipeline,self.sigmoid,{28:bg})
        doc=document(self.X[:1]);doc['rows'][0]['features']['clicks_7d']=float('inf')
        with self.assertRaisesRegex(ValueError,'Invalid numeric'):explain(doc,self.pipeline,self.sigmoid,{28:self.X})


class StageReferenceTests(unittest.TestCase):
    def test_only_preceding_checkpoint_with_maximum_six_day_gap(self):
        from acadmate_ml.explain import stage_reference_day
        for day in range(7,225):
            reference=stage_reference_day(day)
            self.assertLessEqual(reference,day);self.assertLess(day-reference,7)
            self.assertEqual(reference%7,0)
        self.assertEqual(stage_reference_day(38),35)
        for bad in [6,0,-1,38.5,True]:
            with self.assertRaises(ValueError):stage_reference_day(bad)


@unittest.skipUnless(importlib.util.find_spec('shap'), 'Optional SHAP environment required')
class StageShapTests(unittest.TestCase):
    def test_day38_uses_declared_day35_without_changing_probability(self):
        from acadmate_ml.explain import REFERENCE_POLICY
        from acadmate_ml.predict import predict
        X,pipeline,sigmoid=toy_models()
        requested=X[:3].copy();requested[:,0]=38
        doc=document(requested);doc['as_of_day']=38
        for row in doc['rows']:row['as_of_day']=38
        bg=X[3:].copy();bg[:,0]=35
        reference={'policy':REFERENCE_POLICY,'prediction_day':38,'reference_day':35,'course_day':35}
        result=explain(doc,pipeline,sigmoid,{38:bg},reference=reference)
        expected=predict(doc,pipeline,sigmoid)
        np.testing.assert_allclose([r['research_risk_probability'] for r in result['rows']],
                                   [r['research_risk_probability'] for r in expected['rows']],atol=1e-12)
        self.assertEqual(result['background_reference']['reference_day'],35)
        future=dict(reference,reference_day=42,course_day=42)
        with self.assertRaisesRegex(ValueError,'stage-reference provenance'):explain(doc,pipeline,sigmoid,{38:bg},reference=future)
        with self.assertRaisesRegex(ValueError,'course-day mismatch'):explain(doc,pipeline,sigmoid,{38:bg})
