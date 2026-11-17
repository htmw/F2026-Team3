import unittest
from risk_mvp.audit import summarize

class AuditTests(unittest.TestCase):
    def test_probability_summary_and_empty_cohort(self):
        self.assertEqual(summarize([]),{'count':0})
        s=summarize([.1,.9,.3,.5])
        self.assertEqual(s['count'],4);self.assertEqual(s['min'],.1);self.assertEqual(s['max'],.9)
        self.assertAlmostEqual(s['mean'],.45);self.assertAlmostEqual(s['median'],.4)
