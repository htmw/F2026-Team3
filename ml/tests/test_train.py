import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from acadmate_ml.features import FEATURES, KEY
from acadmate_ml.train import models, metrics, outreach, load_partition, run


class TrainingTests(unittest.TestCase):
    def test_preprocessor_fits_training_only(self):
        model=models()['logistic_regression']
        X=np.array([[1.,np.nan],[3.,2.],[5.,4.],[7.,6.]])
        model.fit(X,np.array([0,0,1,1]),classifier__sample_weight=np.ones(4))
        before=model.named_steps['imputer'].statistics_.copy()
        model.predict_proba(np.array([[9999.,np.nan]]))
        np.testing.assert_array_equal(before,model.named_steps['imputer'].statistics_)
        self.assertEqual(before[0],4.)

    def test_single_class_auc_explicitly_undefined(self):
        result=metrics(np.array([0,0]),np.array([.1,.2]))
        self.assertIsNone(result['roc_auc'])
        self.assertIsNone(result['average_precision'])

    def test_weekly_outreach_deduplicates_student(self):
        identities=[('AAA','2013J','1','28'),('BBB','2013J','1','28'),('AAA','2013J','2','28')]
        result=outreach(identities,np.array([0,1,0]),np.array([.2,.9,.5]))
        self.assertEqual(result['0.1']['28']['students'],2)
        self.assertEqual(result['0.1']['28']['recall'],1)

    def make_partition(self,folder,base):
        folder.mkdir()
        for name,fields in [('features',[*KEY,'snapshot_day',*FEATURES]),('labels',[*KEY,'snapshot_day','final_result','at_risk'])]:
            with (folder/(name+'.csv')).open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
                for offset in range(4):
                    for day in [28,35]:
                        row=dict(zip(KEY,['AAA','2013J',str(base+offset)])); row['snapshot_day']=day
                        if name=='features':
                            row.update({f:float(offset+1) for f in FEATURES})
                            row['course_day']=day
                            row['days_since_activity']=''
                        else:
                            row['final_result']='Fail' if offset%2 else 'Pass'
                            row['at_risk']=offset%2
                        writer.writerow(row)

    def test_end_to_end_without_test_partition(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); splits=root/'splits'; splits.mkdir()
            self.make_partition(splits/'train',1); self.make_partition(splits/'validation',10)
            (splits/'manifest.json').write_text(json.dumps({'student_overlap_counts':{'train_validation':0},
                'partitions':{'train':{'snapshots':8},'validation':{'snapshots':8}}}))
            # No test directory exists: any test-file access would fail this run.
            with patch('acadmate_ml.train.models',return_value={'dummy_prior':models()['dummy_prior']}):
                report=run(splits,root/'out')
            self.assertFalse(report['test_accessed'])
            self.assertEqual(report['selected_model'],'dummy_prior')
            X,y,ids,w,_=load_partition(splits/'train')
            self.assertEqual(X.shape,(8,len(FEATURES)))
            self.assertTrue(np.allclose(w,.5))
            self.assertTrue(np.isnan(X[:,FEATURES.index('days_since_activity')]).all())
            with self.assertRaises(ValueError): run(splits,root/'out')

    def test_actual_student_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.make_partition(root/'train',1); self.make_partition(root/'validation',1)
            (root/'manifest.json').write_text(json.dumps({'student_overlap_counts':{}}))
            with self.assertRaisesRegex(ValueError,'overlap'): run(root,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__': unittest.main()
