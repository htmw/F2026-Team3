"""Academic schema regressions with isolated SQLite and opt-in disposable PostgreSQL."""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from risk_mvp import service
from risk_mvp.models import Link
from risk_mvp.router import router, read_db


class SchemaCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool,
                                    connect_args={'check_same_thread': False})
        self.addCleanup(self.engine.dispose)
        # Intentionally create only the academic columns consumed by this service.
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE students (student_id INTEGER PRIMARY KEY, name TEXT)'))
            conn.execute(text('CREATE TABLE courses (course_id INTEGER PRIMARY KEY, course_code TEXT, credits INTEGER)'))
            conn.execute(text('CREATE TABLE enrollments (enrollment_id INTEGER PRIMARY KEY, student_id INTEGER, course_id INTEGER, status TEXT, grade_points REAL, term TEXT)'))
            conn.execute(text("INSERT INTO students VALUES (1, 'Synthetic Student')"))
            conn.execute(text("INSERT INTO courses VALUES (10, 'CS10', 3), (11, 'CS11', 3)"))
            conn.execute(text("INSERT INTO enrollments VALUES (100,1,10,'completed',4,'Fall'), (101,1,11,'in_progress',NULL,'Spring'), (102,1,10,'failed',0,'Fall'), (103,1,11,'withdrawn',NULL,'Fall')"))
        Link.__table__.create(self.engine)
        metadata = MetaData()
        tables = {}
        for name in ('students', 'courses', 'enrollments'):
            tables[name] = Table(name, metadata, autoload_with=self.engine)
            # Mirrors main additions without altering the physical demo schema.
            tables[name].append_column(Column('main_only_column', Integer))
        tables['enrollments'].append_column(Column('section_id', Integer))
        self.patch = patch.object(service, 'T', tables)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)

    def test_insights_preserve_academic_summary_with_newer_metadata(self):
        result = service.insights(self.db, 1)
        self.assertEqual(result['name'], 'Synthetic Student')
        self.assertEqual(result['recorded_gpa'], 4.0)
        self.assertEqual(result['completed_credits'], 3.0)
        self.assertEqual(result['failed_courses'], ['CS10'])
        self.assertEqual(result['withdrawn_courses'], ['CS11'])
        self.assertEqual(result['active_enrollments'], [
            {'enrollment_id':101, 'course_id':11, 'course_code':'CS11', 'term':'Spring'}])

    def test_extraction_preserves_missing_offering_and_unknown_enrollment(self):
        cutoff = datetime(2027, 2, 8, 23, 59, 59, 999999, tzinfo=timezone.utc)
        with patch.object(service.MODEL, '_load', side_effect=AssertionError('No model needed')):
            result = service.assessment(self.db, 101, cutoff)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['reason'], 'No dated course offering')
        self.assertIsNone(result['research_risk_probability'])
        with self.assertRaises(service.MissingEnrollment):
            service.extract(self.db, 999, cutoff)
        with self.assertRaises(service.MissingEnrollment):
            service.insights(self.db, 999)

    def test_http_queries_do_not_return_503_for_unrelated_missing_columns(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[read_db] = lambda: self.db
        with TestClient(app) as client:
            response = client.get('/api/v1/research/database/students/1/insights')
            self.assertEqual(response.status_code, 200, response.text)
            response = client.get('/api/v1/research/database/enrollments/101/risk-assessment',
                                  params={'cutoff':'2027-02-08T23:59:59.999999Z'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'unavailable')
            self.assertEqual(client.get('/api/v1/research/database/students/999/insights').status_code, 404)


@unittest.skipUnless(os.getenv('RUN_RISK_DB_TESTS') == 'true', 'Disposable PostgreSQL test opt-in')
class PostgreSQLSchemaCompatibilityTests(unittest.TestCase):
    def test_real_score_and_features_unchanged_with_new_main_columns(self):
        from sqlalchemy import select
        from risk_mvp.database import engine
        cutoff = datetime(2027, 2, 8, 23, 59, 59, 999999, tzinfo=timezone.utc)
        metadata = MetaData()
        tables = {name: service.T[name].to_metadata(metadata)
                  for name in ('students', 'enrollments', 'courses')}
        for table in tables.values():
            table.append_column(Column('main_only_column', Integer))
        tables['enrollments'].append_column(Column('section_id', Integer))
        with Session(engine()) as db:
            enrollment = next(link.enrollment_id for link in db.scalars(select(Link))
                              if service.extract(db, link.enrollment_id, cutoff)['status'] == 'ready')
            original = service.extract(db, enrollment, cutoff)
            student_id = original['student_id']
            before_summary = service.insights(db, student_id)
            with patch('sklearn.pipeline.Pipeline.fit', side_effect=AssertionError('No retraining')):
                before = service.assessment(db, enrollment, cutoff)
                with patch.object(service, 'T', tables):
                    self.assertEqual(service.extract(db, enrollment, cutoff), original)
                    self.assertEqual(service.insights(db, student_id), before_summary)
                    after = service.assessment(db, enrollment, cutoff)
            self.assertEqual(after['status'], 'scored_research_demo')
            self.assertEqual(before['research_risk_probability'], after['research_risk_probability'])
            print('SCHEMA COMPATIBILITY REAL ARTIFACT', enrollment, after['research_risk_probability'])


class ValidationDependencyTests(unittest.TestCase):
    def test_real_dependency_preserves_request_validation_errors(self):
        from unittest.mock import MagicMock
        app = FastAPI()
        app.include_router(router)
        with patch.dict(os.environ, {'ACADMATE_RISK_MVP_ENABLED':'true'}), \
             patch('risk_mvp.router.session', side_effect=lambda: iter([MagicMock()])), \
             patch('risk_mvp.router.assessment', side_effect=AssertionError('Invalid input must not invoke inference')), \
             TestClient(app) as client:
            for value in ['0', '-1', 'abc']:
                response = client.get(f'/api/v1/research/database/enrollments/{value}/risk-assessment',
                                      params={'cutoff':'2027-02-08T23:59:59.999999Z'})
                self.assertEqual(response.status_code, 422, response.text)
            response = client.get('/api/v1/research/database/enrollments/101/risk-assessment',
                                  params={'cutoff':'not-a-date'})
            self.assertEqual(response.status_code, 422, response.text)
