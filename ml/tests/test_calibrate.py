import unittest
import numpy as np
from acadmate_ml.calibrate import fit_group,fit_maps,logit


class CalibrationTests(unittest.TestCase):
    def test_stable_student_grouping_without_outcome_input(self):
        groups=[fit_group(str(i)) for i in range(100)]
        self.assertEqual(groups,[fit_group(str(i)) for i in range(100)])
        self.assertIn(True,groups); self.assertIn(False,groups)
        self.assertEqual(fit_group('student'),fit_group('student'))

    def test_heldout_labels_cannot_change_fitted_maps(self):
        p=np.array([.1,.2,.3,.4,.6,.7,.8,.9])
        y=np.array([0,0,1,0,1,0,1,1])
        sigmoid,isotonic=fit_maps(p,y,np.ones(8))
        before=sigmoid.predict_proba(logit(np.array([.25,.75])))
        # Assessment data is used for prediction only, never passed to fit_maps.
        isotonic.predict(np.array([0.,1.]))
        np.testing.assert_array_equal(before,sigmoid.predict_proba(logit(np.array([.25,.75]))))
        self.assertTrue(np.isfinite(logit(np.array([0.,1.]))).all())
        with self.assertRaises(ValueError): fit_maps(p,np.zeros(8),np.ones(8))

    def test_end_to_end_without_test_files(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from test_train import TrainingTests
        from acadmate_ml.train import models,run
        from acadmate_ml.calibrate import run as calibrate
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); splits=root/'splits'; splits.mkdir()
            fixture=TrainingTests()
            fixture.make_partition(splits/'train',1)
            # Larger deterministic IDs ensure both classes in both hash groups.
            fixture.make_partition(splits/'validation',10)
            # Construct a tiny fixture with both classes in each deterministic group.
            import csv
            chosen={}
            used=set()
            for offset,wanted in enumerate([True,True,False,False]):
                candidate=next(str(i) for i in range(10,1000) if str(i) not in used and fit_group(str(i))==wanted)
                chosen[str(10+offset)]=candidate; used.add(candidate)
            for name in ['features','labels']:
                path=splits/'validation'/(name+'.csv')
                with path.open(newline='') as stream:
                    reader=csv.DictReader(stream); fields=reader.fieldnames; rows=list(reader)
                for row in rows: row['id_student']=chosen[row['id_student']]
                with path.open('w',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            (splits/'manifest.json').write_text(json.dumps({'student_overlap_counts':{},
                'partitions':{'train':{'snapshots':8},'validation':{'snapshots':8}}}))
            with patch('acadmate_ml.train.models',return_value={'dummy_prior':models()['dummy_prior']}):
                run(splits,root/'models')
            with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('Base model must stay fixed')):
                result=calibrate(splits,root/'models',root/'analysis')
            self.assertFalse(result['test_accessed']); self.assertEqual(result['student_overlap'],0)
            with self.assertRaises(ValueError): calibrate(splits,root/'models',root/'analysis')


if __name__=='__main__': unittest.main()
