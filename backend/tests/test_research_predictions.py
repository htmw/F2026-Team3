import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from routers.research_predictions import router
from schemas.research_predictions import ResearchPredictionResponse
from services.research_predictions import (PredictionService,DemoUnavailable,DemoEnrollmentNotFound,get_prediction_service)

ROOT=Path(__file__).resolve().parents[2]


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI();self.app.include_router(router)
        self.client=TestClient(self.app)

    def test_unavailable_real_fixture_never_loads_artifacts(self):
        service=PredictionService()
        self.app.dependency_overrides[get_prediction_service]=lambda:service
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'true'}),patch.object(service,'_load',side_effect=AssertionError('Must not load')):
            response=self.client.get('/api/v1/research/enrollments/20044/risk-prediction')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'unavailable')
        self.assertIsNone(response.json()['research_risk_probability'])
        self.assertTrue(response.json()['reason'])

    def test_disabled_missing_artifacts_unknown_and_invalid(self):
        service=PredictionService();self.app.dependency_overrides[get_prediction_service]=lambda:service
        path='/api/v1/research/enrollments/'
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'false'}):
            self.assertEqual(self.client.get(path+'20014/risk-prediction').status_code,503)
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'true'}),patch.object(service,'_load',side_effect=FileNotFoundError('private path')):
            response=self.client.get(path+'20014/risk-prediction')
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json()['error']['code'],'RESEARCH_DEMO_UNAVAILABLE')
            self.assertNotIn('private path',response.text)
            self.assertEqual(self.client.get(path+'999999/risk-prediction').status_code,404)
        for value in ['0','-1','abc']:
            self.assertEqual(self.client.get(path+value+'/risk-prediction').status_code,422)

    def test_integrity_failure_is_503_before_deserialization(self):
        service=PredictionService();self.app.dependency_overrides[get_prediction_service]=lambda:service
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'true'}), \
             patch('acadmate_ml.splits.digest',return_value='invalid'), \
             patch('joblib.load',side_effect=AssertionError('Must not deserialize')) as loader:
            with self.assertLogs('services.research_predictions',level='ERROR'):
                response=self.client.get('/api/v1/research/enrollments/20014/risk-prediction')
            self.assertEqual(response.status_code,503)
            loader.assert_not_called()

    def test_schema_rejects_inconsistent_states(self):
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'true'}):row=PredictionService().get(20044)
        row['research_risk_probability']=.5
        with self.assertRaises(ValidationError):ResearchPredictionResponse(**row)

    def test_existing_student_route_registered_without_database(self):
        fake=types.ModuleType('database')
        def no_database(): raise AssertionError('Database accessed')
        fake.get_db=no_database
        spec=importlib.util.spec_from_file_location('isolated_main',ROOT/'backend/main.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'database':fake}):spec.loader.exec_module(module)
        paths=module.app.openapi()['paths']
        self.assertIn('/api/v1/students/{student_id}/academic-profile',paths)
        self.assertIn('/api/v1/research/enrollments/{enrollment_id}/risk-prediction',paths)
        module.app.dependency_overrides[no_database]=lambda:None
        with patch.object(module.students,'get_student_profile',return_value=None):
            response=TestClient(module.app).get('/api/v1/students/101/academic-profile')
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.json()['error']['code'],'NOT_FOUND')


@unittest.skipUnless(os.getenv('RUN_RESEARCH_ARTIFACT_SMOKE')=='true','Explicit local-artifact smoke opt-in')
class ArtifactSmokeTests(unittest.TestCase):
    def test_real_pipeline_scored_response_and_cache_without_writes_or_refit(self):
        import acadmate_ml.predict as inference
        import joblib
        service=PredictionService()
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_prediction_service]=lambda:service
        client=TestClient(app)
        fixture_paths=list((ROOT/'data/synthetic').glob('*.csv'))+[ROOT/'ml/fixtures/simulated_lms/events.json']
        from acadmate_ml.splits import digest
        before={p:digest(p) for p in fixture_paths}
        with patch.dict(os.environ,{'ACADMATE_RESEARCH_DEMO_ENABLED':'true'}), \
             patch('acadmate_ml.predict.predict',wraps=inference.predict) as called, \
             patch('joblib.load',wraps=joblib.load) as loaded, \
             patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No refitting')), \
             patch('socket.create_connection',side_effect=AssertionError('No network')), \
             patch('pathlib.Path.write_text',side_effect=AssertionError('No output writes')), \
             patch('pathlib.Path.write_bytes',side_effect=AssertionError('No output writes')):
            for enrollment in [20014,20024,20034]:
                response=client.get(f'/api/v1/research/enrollments/{enrollment}/risk-prediction')
                self.assertEqual(response.status_code,200,response.text)
                data=response.json()
                self.assertEqual(data['status'],'scored_research_demo')
                self.assertTrue(0<=data['research_risk_probability']<=1)
                self.assertTrue(data['research_only']);self.assertTrue(data['warnings'])
                print('REAL ARTIFACT',enrollment,data['research_risk_probability'])
            self.assertEqual(called.call_count,3)
            self.assertEqual(loaded.call_count,2)
        self.assertEqual(before,{p:digest(p) for p in fixture_paths})
