import copy
import hashlib
import json
import unittest
from pathlib import Path
from acadmate_ml.simulated_lms import build

ML=Path(__file__).resolve().parents[1]
ACADEMIC=ML.parent/'data/synthetic'


class SimulatedLmsTests(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads((ML/'fixtures/simulated_lms/events.json').read_text(encoding='utf-8-sig'))

    def test_linked_cases_and_feature_values(self):
        result=build(self.doc,ACADEMIC)
        rows={r['enrollment_id']:r for r in result['rows']}
        steady=rows['20014']['features']
        self.assertEqual(steady['clicks_7d'],75)
        self.assertEqual(steady['clicks_28d'],150)
        self.assertEqual(steady['submissions_so_far'],2)
        self.assertEqual(steady['overdue_assessments'],0)
        self.assertEqual(rows['20024']['features']['days_since_activity'],10)
        self.assertEqual(rows['20024']['features']['late_submission_rate'],1)
        self.assertFalse(result['model_inference_performed'])

    def test_zero_observation_differs_from_missing_feed(self):
        rows=build(self.doc,ACADEMIC)['rows']
        self.assertEqual(rows[2]['status'],'ready')
        self.assertEqual(rows[2]['features']['no_activity'],1)
        self.assertEqual(rows[2]['features']['overdue_assessments'],2)
        self.assertEqual(rows[3]['status'],'unavailable')
        self.assertIsNone(rows[3]['features'])

    def test_future_and_late_arrival_invariance(self):
        before=build(self.doc,ACADEMIC)['rows']
        self.doc['activity'][-1]['activity_count']=999999
        self.doc['activity'][-2]['activity_count']=999999
        self.doc['submissions'].append({'submission_id':'future','enrollment_id':'20024',
            'assessment_id':'demo-task-2','submitted_day':30,'available_day':30})
        self.assertEqual(before,build(self.doc,ACADEMIC)['rows'])

    def test_bad_link_and_duplicates_rejected(self):
        bad=copy.deepcopy(self.doc);bad['enrollments'][0]['student_id']='wrong'
        with self.assertRaisesRegex(ValueError,'linkage'):build(bad,ACADEMIC)
        self.doc['activity'].append(copy.deepcopy(self.doc['activity'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):build(self.doc,ACADEMIC)

    def test_coverage_must_be_known_as_of_snapshot(self):
        self.doc['coverage'][0]['available_day']=29
        self.assertEqual(build(self.doc,ACADEMIC)['rows'][0]['status'],'unavailable')

    def test_score_and_impossible_availability_rejected(self):
        bad=copy.deepcopy(self.doc);bad['submissions'][0]['score']=100
        with self.assertRaisesRegex(ValueError,'Score'):build(bad,ACADEMIC)
        self.doc['activity'][0]['available_day']=0
        with self.assertRaisesRegex(ValueError,'before event'):build(self.doc,ACADEMIC)

    def test_original_academic_csvs_unchanged(self):
        paths=sorted(ACADEMIC.glob('*.csv'))
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        build(self.doc,ACADEMIC)
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


if __name__=='__main__':unittest.main()
