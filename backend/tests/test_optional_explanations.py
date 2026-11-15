import unittest
from unittest.mock import patch
from risk_mvp.main_explanations import attach


class OptionalExplanationTests(unittest.TestCase):
    def test_unscored_never_loads_explanation_or_background(self):
        result={'status':'unavailable','research_risk_probability':None}
        with patch('risk_mvp.main_explanations.training_background',side_effect=AssertionError('No background read')):
            response=attach(result,None,1,None)
        self.assertIsNone(response['research_risk_probability'])
        self.assertEqual(response['explanation']['status'],'unavailable')

    def test_missing_background_preserves_score_and_hides_internal_path(self):
        result={'status':'scored_research_demo','research_risk_probability':.4,'as_of_day':38}
        with patch('risk_mvp.main_explanations.training_background',side_effect=FileNotFoundError('private-path')),self.assertLogs('risk_mvp.main_explanations',level='ERROR'):
            response=attach(result,None,1,None)
        self.assertEqual(response['research_risk_probability'],.4)
        self.assertEqual(response['status'],'scored_research_demo')
        self.assertEqual(response['explanation']['status'],'unavailable')
        self.assertNotIn('private-path',str(response['explanation']))

    def test_unsupported_stage_preserves_prediction(self):
        result={'status':'scored_research_demo','research_risk_probability':.4,'as_of_day':6}
        with self.assertLogs('risk_mvp.main_explanations',level='ERROR'):
            response=attach(result,None,1,None)
        self.assertEqual(response['research_risk_probability'],.4)
        self.assertEqual(response['explanation']['status'],'unavailable')
