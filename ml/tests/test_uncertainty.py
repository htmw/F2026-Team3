import unittest
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
from acadmate_ml.uncertainty import Ranking,cluster_multipliers,interval


class UncertaintyTests(unittest.TestCase):
    def test_cached_metrics_match_sklearn_with_ties_and_zero_weights(self):
        y=np.array([0,1,0,1,1,0])
        p=np.array([.1,.8,.8,.8,.2,.9])
        w=np.array([1.,2.,0.,3.,.5,2.])
        ap,auc=Ranking(y,p).calculate(w)
        self.assertAlmostEqual(ap,average_precision_score(y,p,sample_weight=w))
        self.assertAlmostEqual(auc,roc_auc_score(y,p,sample_weight=w))

    def test_cluster_keeps_every_student_row_together_and_deterministic(self):
        ids=np.array(['a','a','b','a','c','c'])
        a=cluster_multipliers(ids,np.random.default_rng(42))
        b=cluster_multipliers(ids,np.random.default_rng(42))
        np.testing.assert_array_equal(a,b)
        self.assertEqual(a[0],a[1]);self.assertEqual(a[0],a[3]);self.assertEqual(a[4],a[5])
        self.assertEqual(a[0]+a[2]+a[4],3)

    def test_paired_identical_predictions_have_zero_difference(self):
        rank=Ranking(np.array([0,1,0,1]),np.array([.1,.7,.4,.9]))
        w=np.array([1.,2.,1.,2.])
        self.assertEqual(rank.calculate(w)[0]-rank.calculate(w)[0],0)

    def test_single_class_draw_is_undefined(self):
        self.assertTrue(np.isnan(Ranking(np.array([0,1]),np.array([.2,.8])).calculate(np.array([1.,0.]))).all())
        result=interval([np.nan,1,2,3],2)
        self.assertEqual(result['valid_replicates'],3)


if __name__=='__main__': unittest.main()

class UncertaintyIsolationTests(unittest.TestCase):
    def test_analysis_runs_without_test_files_or_refitting(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from test_train import TrainingTests
        from acadmate_ml.train import models,run
        from acadmate_ml.uncertainty import analyze
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); splits=root/'splits'; splits.mkdir()
            fixture=TrainingTests()
            fixture.make_partition(splits/'train',1)
            fixture.make_partition(splits/'validation',10)
            (splits/'manifest.json').write_text(json.dumps({'student_overlap_counts':{},
                'partitions':{'train':{'snapshots':8},'validation':{'snapshots':8}}}))
            with patch('acadmate_ml.train.models',return_value={'dummy_prior':models()['dummy_prior']}):
                run(splits,root/'models')
            with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('Must not refit')):
                report=analyze(splits,root/'models',root/'analysis',100)
            self.assertFalse(report['test_accessed'])
            self.assertFalse(report['model_refitted'])
            self.assertEqual(report['weekly_selected']['28']['rows'],4)
            self.assertEqual(report['validation_students'],4)
            with self.assertRaises(ValueError): analyze(splits,root/'models',root/'analysis',100)
