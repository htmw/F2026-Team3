"""Shared evidence regression tests; no database or frozen artifacts required."""
import unittest
from risk_mvp.main_attention import overdue_counts

class AttentionTests(unittest.TestCase):
    def test_complete_counts_include_real_zero(self):
        rows=[{'status':'ready','evidence':{'overdue_last_14_days':n}} for n in (0,1,3)]
        self.assertEqual(overdue_counts(rows),4)
    def test_unknown_is_not_zero_or_partial_total(self):
        ready={'status':'ready','evidence':{'overdue_last_14_days':3}}
        for row in ({'status':'unavailable','evidence':{}}, {'status':'ready','evidence':{'overdue_last_14_days':None}}, {'status':'ready','evidence':{}}):
            self.assertIsNone(overdue_counts([ready,row]))
        self.assertIsNone(overdue_counts([]))

    def test_outstanding_work_uses_full_course_window(self):
        from types import SimpleNamespace
        from risk_mvp.main_attention import course_review_reason
        rows=[{'status':'ready','evidence':{'overdue_last_14_days':0,'overdue_assignments':3}}]
        self.assertEqual(overdue_counts(rows),0)
        self.assertEqual(overdue_counts(rows,'overdue_assignments'),3)
        context=SimpleNamespace(course_overdue={101:3,102:0})
        self.assertIn('3 assessments remain overdue',course_review_reason(101,context))
        self.assertIsNone(course_review_reason(102,context))
        self.assertIsNone(course_review_reason(999,context))
        self.assertIsNone(course_review_reason(101,SimpleNamespace()))

    def test_incomplete_course_total_does_not_fabricate_clearance(self):
        rows=[{'status':'ready','evidence':{'overdue_assignments':2}},
              {'status':'unavailable','evidence':{}}]
        self.assertIsNone(overdue_counts(rows,'overdue_assignments'))


class ReviewDatabaseScopeTests(unittest.TestCase):
    def test_team_clone_uses_course_evidence_instead_of_legacy_counts(self):
        from datetime import date
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from sqlalchemy import Table,Column,Integer,String,MetaData
        from sqlalchemy.engine import make_url
        import sys,risk_mvp
        from risk_mvp.main_attention import align_context,course_review_reason
        table=Table("enrollments",MetaData(),Column("student_id",Integer),Column("enrollment_id",Integer),Column("status",String))
        extract=Mock(return_value={"status":"ready","evidence":{"overdue_last_14_days":0,"overdue_assignments":2}})
        fake=SimpleNamespace(T={"enrollments":table},extract=extract)
        db=Mock()
        db.get_bind.return_value.url=make_url("postgresql://demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2")
        db.execute.return_value.mappings.return_value=[SimpleNamespace(student_id=101,enrollment_id=303)]
        context=SimpleNamespace(missed={101:99})
        with patch.dict("os.environ",{"ACADMATE_RISK_MVP_ENABLED":"true"}),patch.object(risk_mvp,"service",fake,create=True),patch.dict(sys.modules,{"risk_mvp.service":fake,"core.time":SimpleNamespace(today=lambda:date(2027,2,16))}):
            align_context(db,[SimpleNamespace(student_id=101)],context)
        self.assertEqual(context.missed,{101:0})
        self.assertEqual(context.course_overdue,{101:2})
        self.assertIn("2 assessments remain overdue",course_review_reason(101,context))
        extract.assert_called_once()

    def test_remote_or_unapproved_database_never_reads_demo_sources(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        from sqlalchemy.engine import make_url
        from risk_mvp.main_attention import align_context
        for url in ("postgresql://demo@remote.example/acadmate_risk_team_review_sprint2","postgresql://demo@127.0.0.1/production"):
            db=Mock();db.get_bind.return_value.url=make_url(url)
            context=SimpleNamespace(missed={101:99})
            with patch.dict("os.environ",{"ACADMATE_RISK_MVP_ENABLED":"true"}):align_context(db,[SimpleNamespace(student_id=101)],context)
            db.execute.assert_not_called()
            self.assertEqual(context.missed,{101:99})
