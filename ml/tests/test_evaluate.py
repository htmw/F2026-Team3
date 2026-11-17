import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
from acadmate_ml.calibrate import fit_maps
from acadmate_ml.evaluate import freeze,evaluate
from acadmate_ml.splits import digest
from acadmate_ml.train import models,run



class FinalEvaluationTests(unittest.TestCase):
    def fixture(self,root,with_test=True):
        splits=root/'splits';splits.mkdir()
        from test_train import TrainingTests
        helper=TrainingTests()
        helper.make_partition(splits/'train',1);helper.make_partition(splits/'validation',10)
        if with_test: helper.make_partition(splits/'test',30)
        (splits/'manifest.json').write_text(json.dumps({'student_overlap_counts':{},'partitions':{
            'train':{'snapshots':8},'validation':{'snapshots':8},'test':{'snapshots':8}}}))
        with patch('acadmate_ml.train.models',return_value={'logistic_regression':models()['logistic_regression']}):
            run(splits,root/'models')
        maps=root/'maps';maps.mkdir()
        sigmoid,isotonic=fit_maps(np.array([.1,.3,.6,.9]),np.array([0,0,1,1]),np.ones(4))
        model_hash=digest(root/'models/logistic_regression.joblib')
        joblib.dump({'sigmoid':sigmoid,'isotonic':isotonic,'base_model_sha256':model_hash},maps/'calibration_maps.joblib')
        (maps/'calibration_assessment.json').write_text(json.dumps({'base_model':'logistic_regression',
            'model_sha256':model_hash,'split_manifest_sha256':digest(splits/'manifest.json')}))
        return splits,root/'models',maps

    def test_freeze_does_not_require_test_rows_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=self.fixture(root,False)
            config=freeze(*args,root/'freeze.json')
            self.assertEqual(config['threshold'],.5)
            self.assertFalse((args[0]/'test').exists())
            with self.assertRaises(ValueError):freeze(*args,root/'freeze.json')

    def test_full_evaluation_no_refit_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=self.fixture(root)
            freeze(*args,root/'freeze.json')
            with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No refit')):
                result=evaluate(*args,root/'freeze.json',root/'out')
            self.assertEqual(result['student_overlap'],0)
            self.assertEqual(result['snapshots'],8)
            self.assertFalse(result['models_refitted'])
            self.assertEqual(set(result['results']),{'sigmoid_primary','uncalibrated_comparison'})
            self.assertTrue((root/'out/EVALUATION_COMPLETED.json').exists())
            with self.assertRaises(FileExistsError):evaluate(*args,root/'freeze.json',root/'out')

    def test_changed_artifact_rejected_before_test_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=self.fixture(root,False)
            freeze(*args,root/'freeze.json')
            with (args[2]/'calibration_maps.joblib').open('ab') as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'provenance'):evaluate(*args,root/'freeze.json',root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
