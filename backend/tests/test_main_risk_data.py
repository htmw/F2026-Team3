"""Pure deterministic generation tests; no external database."""
import copy
import unittest
from datetime import date
from risk_mvp.main_data import generate, fingerprint


def records():
    return {'students':[{'student_id':1,'name':'Demo'}],
            'courses':[{'course_id':10}],
            'terms':[{'name':'Fall','start_date':date(2026,8,24),'end_date':date(2026,12,18)}],
            'advisor_student_assignments':[],
            'enrollments':[{'enrollment_id':i,'student_id':1,'course_id':10,'term':'Fall',
                            'status':status,'grade':None,'grade_points':None}
                           for i,status in enumerate(['in_progress','completed','failed','withdrawn'],1)]}


class MainDataTests(unittest.TestCase):
    def test_all_enrollments_determinism_and_original_preserved(self):
        data=records();before=copy.deepcopy(data);a=generate(data);b=generate(data)
        self.assertEqual(a,b);self.assertEqual(data,before)
        self.assertEqual(a['manifest']['enrollment_count'],4)
        for table in ['risk_enrollment_offerings','risk_activity_events','risk_submission_versions','risk_source_coverage','risk_enrollment_history']:
            self.assertEqual({row['enrollment_id'] for row in a['tables'][table]},{1,2,3,4})
        for cutoffs in a['manifest']['checkpoints'].values():self.assertEqual(set(cutoffs),{'7','14','28'})

    def test_outcomes_and_names_do_not_determine_activity(self):
        a=records();b=copy.deepcopy(a)
        b['students'][0]['name']='Other synthetic name'
        for e in b['enrollments']:e.update(status='failed',grade='F',grade_points=0)
        one=generate(a);two=generate(b)
        self.assertNotEqual(fingerprint(a),fingerprint(b))
        for name in ['risk_activity_events','risk_assessments','risk_submission_versions','risk_source_coverage']:
            self.assertEqual(one['tables'][name],two['tables'][name])

    def test_invalid_links_duplicates_and_missing_calendar_rejected(self):
        for field,value in [('student_id',99),('course_id',99),('term','Unknown'),('status','unknown')]:
            data=records();data['enrollments'][0][field]=value
            with self.assertRaises(ValueError):generate(data)
        data=records();data['enrollments'].append(data['enrollments'][0])
        with self.assertRaises(ValueError):generate(data)

    def test_daily_coverage_including_nonweekly_cutoff_and_terminal_history(self):
        bundle=generate(records());rows=bundle['tables']['risk_source_coverage']
        self.assertTrue(all(row['complete'] for row in rows))
        self.assertTrue(any(row['through_at'].startswith('2026-10-01') for row in rows))
        history=bundle['tables']['risk_enrollment_history']
        for row in history:
            self.assertIsNone(row['grade']);self.assertIsNone(row['grade_points'])
        self.assertEqual(len(history),7)
