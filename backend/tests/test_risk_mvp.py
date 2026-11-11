import json,os,unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError,InternalError
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient
from risk_mvp.models import Base,Activity,Coverage,Submission,AssessmentVersion,Link
from risk_mvp.generate import generate
from risk_mvp.database import engine
from risk_mvp.service import extract,assessment,insights,normalize,InvalidCutoff
from risk_mvp.router import router

ROOT=Path(__file__).resolve().parents[2]
CUT=datetime.fromisoformat('2027-02-08T23:59:59.999999+00:00')

class GeneratorTests(unittest.TestCase):
    def test_determinism_valid_links_and_original_hashes(self):
        a=generate();b=generate()
        self.assertEqual(a,b)
        self.assertEqual(a['manifest']['counts']['risk_enrollment_offerings'],800)
        ids={r['enrollment_id'] for r in a['tables']['risk_source_coverage']}
        self.assertEqual(len(ids),179)
        self.assertGreater(a['manifest']['counts']['risk_activity_events'],1000)

    def test_cutoff_validation(self):
        with self.assertRaises(InvalidCutoff):normalize(datetime(2027,2,8))
        with self.assertRaises(InvalidCutoff):normalize(CUT.replace(hour=12))

@unittest.skipUnless(os.getenv('RUN_RISK_DB_TESTS')=='true','Disposable PostgreSQL test opt-in')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db=Session(engine())
        self.eligible=next(l.enrollment_id for l in self.db.scalars(select(Link).where(Link.pattern!='feed_gap')) if extract(self.db,l.enrollment_id,CUT)['status']=='ready')
    def tearDown(self):self.db.rollback();self.db.close()

    def test_real_inference_and_descriptive_evidence(self):
        with patch('sklearn.pipeline.Pipeline.fit',side_effect=AssertionError('No retraining')):
            result=assessment(self.db,self.eligible,CUT)
        self.assertEqual(result['status'],'scored_research_demo')
        self.assertTrue(0<=result['research_risk_probability']<=1)
        self.assertEqual(extract(self.db,self.eligible,CUT)['features']['course_day'],28)
        from services.students import get_student_profile
        self.assertEqual(insights(self.db,101)['recorded_gpa'],get_student_profile(101,self.db)['student']['gpa'])
        self.assertEqual(insights(self.db,101)['completed_credits'],get_student_profile(101,self.db)['student']['completed_credits'])

    def test_future_events_late_arrivals_grades_and_schedule_revisions_do_not_leak(self):
        before=extract(self.db,self.eligible,CUT)['features']
        self.db.add(Activity(enrollment_id=self.eligible,source_event_id='testfuture',occurred_at=CUT+timedelta(days=1),known_at=CUT+timedelta(days=1),count=999999,event_type='synthetic_resource_interaction'))
        self.db.add(Activity(enrollment_id=self.eligible,source_event_id='testlate',occurred_at=CUT-timedelta(days=1),known_at=CUT+timedelta(days=1),count=999999,event_type='synthetic_resource_interaction'))
        s=self.db.scalar(select(Submission).where(Submission.enrollment_id==self.eligible))
        if s:s.score=0
        a=self.db.scalar(select(AssessmentVersion).join(__import__('risk_mvp.models',fromlist=['Assessment']).Assessment).where(__import__('risk_mvp.models',fromlist=['Assessment']).Assessment.offering_id==self.db.get(Link,self.eligible).offering_id))
        self.db.add(AssessmentVersion(assessment_id=a.assessment_id,version=999,due_at=CUT+timedelta(days=100),max_score=100,known_at=CUT+timedelta(days=1)))
        self.db.flush()
        self.assertEqual(before,extract(self.db,self.eligible,CUT)['features'])

    def test_missing_feed_preserves_summary_without_scoring(self):
        from risk_mvp.models import Offering
        link=self.db.scalar(select(Link).join(Offering,Link.offering_id==Offering.id).where(Link.pattern=='feed_gap',Offering.term=='Spring 2027'))
        with patch('risk_mvp.service.MODEL._load',side_effect=AssertionError('No model load')):
            result=assessment(self.db,link.enrollment_id,CUT)
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['research_risk_probability'])
        self.assertIsNone(result['evidence']['clicks_7d'])
        self.assertIsNotNone(result['evidence']['assessments_due'])

    def test_hand_calculated_7_14_28_day_features(self):
        from risk_mvp.models import Offering,Assessment,History
        from datetime import timezone
        start=datetime(2028,1,1,tzinfo=timezone.utc)
        old=self.db.get(Link,self.eligible)
        original=self.db.get(Offering,old.offering_id)
        off=Offering(course_id=original.course_id,term='Synthetic test only',starts_at=start,ends_at=start+timedelta(days=112),timezone='UTC',known_at=start)
        self.db.add(off);self.db.flush()
        old.offering_id=off.id;old.registered_at=start;old.known_at=start
        self.db.add(History(enrollment_id=self.eligible,status='in_progress',effective_at=start,known_at=start))
        aa=[]
        for due in [7,14,35]:
            a=Assessment(offering_id=off.id,label='Test task',kind='TMA');self.db.add(a);self.db.flush()
            self.db.add(AssessmentVersion(assessment_id=a.id,version=1,due_at=start+timedelta(days=due),max_score=100,known_at=start));aa.append(a.id)
        for event_day,count in [(1,1),(7,2),(8,3),(14,4),(28,5)]:
            when=start+timedelta(days=event_day,hours=12)
            self.db.add(Activity(enrollment_id=self.eligible,source_event_id=f'golden-{event_day}',occurred_at=when,known_at=when,count=count,event_type='synthetic_resource_interaction'))
        for aid,d in zip(aa,[7,17]):
            when=start+timedelta(days=d,hours=12)
            self.db.add(Submission(enrollment_id=self.eligible,assessment_id=aid,version=1,submitted_at=when,known_at=when,status='submitted',is_banked=False))
        for checkpoint in [7,14,28]:
            cut=start+timedelta(days=checkpoint+1)-timedelta(microseconds=1)
            for source in ['activity','schedule','submissions']:
                self.db.add(Coverage(enrollment_id=self.eligible,source=source,starts_at=start,through_at=cut,known_at=cut,complete=True))
        self.db.flush()
        # Isolate the new offering: prior old-offering submissions are outside its time span.
        # They are not valid records for this test link, so remove them inside this rolled-back transaction.
        from sqlalchemy import delete
        self.db.execute(delete(Submission).where(Submission.enrollment_id==self.eligible,Submission.assessment_id.not_in(aa)))
        def features(d):return extract(self.db,self.eligible,start+timedelta(days=d+1)-timedelta(microseconds=1))['features']
        day7=features(7);day14=features(14);day28=features(28)
        self.assertEqual(day7['clicks_7d'],3);self.assertEqual(day14['clicks_7d'],7)
        self.assertEqual(day28['clicks_7d'],5);self.assertEqual(day28['clicks_28d'],15)
        self.assertEqual(day28['active_days_28d'],5);self.assertEqual(day28['engagement_change'],5)
        self.assertEqual(day28['days_since_submission'],11);self.assertEqual(day28['late_submission_rate'],.5)
        self.assertEqual(day14['overdue_assessments'],1);self.assertEqual(day28['overdue_assessments'],0)

    def test_fk_and_database_read_only(self):
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(Activity(enrollment_id=99999999,source_event_id='orphan',occurred_at=CUT,known_at=CUT,count=1,event_type='synthetic_resource_interaction'));self.db.flush()
        self.db.rollback()
        self.db.execute(text('SET TRANSACTION READ ONLY'))
        with self.assertRaises(InternalError):self.db.execute(text("DELETE FROM risk_activity_events WHERE id=-1"))

    def test_api_student_selection_insights_cutoffs_and_actual_model(self):
        app=FastAPI();app.include_router(router)
        with patch.dict(os.environ,{'ACADMATE_RISK_MVP_ENABLED':'true'}),TestClient(app) as client:
            r=client.get('/api/v1/research/database/students');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['students']),100)
            r=client.get('/api/v1/research/database/students/101/insights');self.assertEqual(r.status_code,200)
            r=client.get(f'/api/v1/research/database/enrollments/{self.eligible}/risk-assessment',params={'cutoff':CUT.isoformat()})
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'scored_research_demo')
            self.assertEqual(client.get('/api/v1/research/database/enrollments/999999/risk-assessment',params={'cutoff':CUT.isoformat()}).status_code,404)
            self.assertEqual(client.get(f'/api/v1/research/database/enrollments/{self.eligible}/risk-assessment',params={'cutoff':'2027-02-08T12:00:00Z'}).status_code,422)
    def test_schedule_gap_masks_dependent_evidence(self):
        row=self.db.scalar(select(Coverage).where(Coverage.enrollment_id==self.eligible,Coverage.source=='schedule',Coverage.known_at==CUT))
        row.complete=False;self.db.flush()
        result=extract(self.db,self.eligible,CUT)
        self.assertEqual(result['status'],'unavailable')
        for field in ['submissions','late_submission_rate','assessment_completion_rate','overdue_assignments']:
            self.assertIsNone(result['evidence'][field])
        self.assertIsNotNone(result['evidence']['clicks_7d'])
        self.assertIn('schedule',result['reason'])

    def test_ineligible_cutoff_does_not_calculate_features(self):
        from risk_mvp.models import Offering
        offering=self.db.get(Offering,self.db.get(Link,self.eligible).offering_id)
        from datetime import timezone
        for d,reason in [(2,'day 7'),(113,'ended')]:
            cutoff=offering.starts_at.astimezone(timezone.utc)+timedelta(days=d+1)-timedelta(microseconds=1)
            with patch('acadmate_ml.features.snapshot',side_effect=AssertionError('Must not extract')):
                result=extract(self.db,self.eligible,cutoff)
            self.assertEqual(result['status'],'unavailable');self.assertIn(reason,result['reason'])
            self.assertEqual(result['evidence'],{})

    def test_multiple_active_courses_through_api(self):
        from sqlalchemy import func
        from risk_mvp.models import Offering
        e=Base.metadata.tables['enrollments']
        student=self.db.scalar(select(e.c.student_id).join(Link,e.c.enrollment_id==Link.enrollment_id).where(e.c.status=='in_progress',Link.pattern!='feed_gap').group_by(e.c.student_id).having(func.count()>1))
        self.assertIsNotNone(student)
        app=FastAPI();app.include_router(router)
        with patch.dict(os.environ,{'ACADMATE_RISK_MVP_ENABLED':'true'}),TestClient(app) as client:
            summary=client.get(f'/api/v1/research/database/students/{student}/insights').json()
            self.assertGreater(len(summary['active_enrollments']),1)
            for enrollment in summary['active_enrollments']:
                response=client.get(f'/api/v1/research/database/enrollments/{enrollment["enrollment_id"]}/risk-assessment',params={'cutoff':CUT.isoformat()})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['status'],'scored_research_demo')

    def test_completion_rate_excludes_work_not_yet_due(self):
        from risk_mvp.models import Assessment
        before=extract(self.db,self.eligible,CUT)
        assessment_id=self.db.scalar(select(AssessmentVersion.assessment_id).join(Assessment).where(Assessment.offering_id==self.db.get(Link,self.eligible).offering_id,AssessmentVersion.due_at>CUT).order_by(AssessmentVersion.due_at))
        self.db.add(Submission(enrollment_id=self.eligible,assessment_id=assessment_id,version=999,submitted_at=CUT,known_at=CUT,status='submitted',is_banked=False))
        self.db.flush();after=extract(self.db,self.eligible,CUT)
        self.assertEqual(before['evidence']['assessment_completion_rate'],after['evidence']['assessment_completion_rate'])
        self.assertEqual(after['features']['submissions_so_far'],before['features']['submissions_so_far']+1)
