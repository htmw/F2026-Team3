import copy
import json
import unittest
from pathlib import Path
import numpy as np
from acadmate_ml.predict import predict
from acadmate_ml.simulated_lms import build

ML=Path(__file__).resolve().parents[1]

class FakePredictor:
    def __init__(self):self.calls=[]
    def predict_proba(self,X):
        self.calls.append(X.copy())
        return np.tile([.4,.6],(len(X),1))

class PredictionTests(unittest.TestCase):
    def setUp(self):
        source=json.loads((ML/'fixtures/simulated_lms/events.json').read_text(encoding='utf-8-sig'))
        self.document=build(source,ML.parent/'data/synthetic')

    def test_only_ready_vectors_scored_and_order_preserved(self):
        base=FakePredictor();sigmoid=FakePredictor()
        result=predict(self.document,base,sigmoid)
        self.assertEqual(base.calls[0].shape,(3,16))
        self.assertEqual([r['enrollment_id'] for r in result['rows']],['20014','20024','20034','20044'])
        self.assertEqual(result['rows'][0]['research_risk_probability'],.6)
        self.assertIsNone(result['rows'][3]['research_risk_probability'])
        self.assertEqual(result['rows'][3]['status'],'unavailable')
        self.assertFalse(result['model_refitted'])
        self.assertTrue(result['warnings'])

    def test_all_unavailable_never_calls_model(self):
        self.document['rows']=[self.document['rows'][-1]]
        base=FakePredictor();sigmoid=FakePredictor()
        predict(self.document,base,sigmoid)
        self.assertEqual(base.calls,[]);self.assertEqual(sigmoid.calls,[])

    def test_invalid_features_and_mixed_days_rejected(self):
        bad=copy.deepcopy(self.document);bad['rows'][0]['features']['grade']=4
        with self.assertRaisesRegex(ValueError,'schema'):predict(bad,FakePredictor(),FakePredictor())
        bad=copy.deepcopy(self.document);bad['rows'][0]['features']['clicks_7d']=float('inf')
        with self.assertRaisesRegex(ValueError,'numeric'):predict(bad,FakePredictor(),FakePredictor())
        self.document['rows'][0]['as_of_day']=35
        with self.assertRaisesRegex(ValueError,'snapshot'):predict(self.document,FakePredictor(),FakePredictor())

if __name__=='__main__':unittest.main()
