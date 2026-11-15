import sys
from pathlib import Path
import argparse
r=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Read-only verification of shared dashboard evidence in the dedicated local demo')
parser.add_argument('--snapshot',type=Path,required=True)
s=parser.parse_args().snapshot.resolve()
sys.path.insert(0,str(r/'tools'))
from prepare_main_risk_demo import configure
configure(s)
from database import SessionLocal
from models import Advisor
from services import advisor_dashboard,advisees
from risk_mvp.main_attention import overdue_counts
from risk_mvp import service
from datetime import datetime,time,timezone
from core.time import today
from sqlalchemy import text,select
from unittest.mock import patch
with SessionLocal() as db:
 db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
 db.execute(text('SET TRANSACTION READ ONLY'))
 advisor=db.get(Advisor,201)
 with patch.object(service.MODEL,'_load',side_effect=AssertionError('Dashboard must not load a model')):
  ctx,rated=advisees.levels(db,advisor)
  e=service.T['enrollments'].c;cut=datetime.combine(today(),time.max,timezone.utc)
  checked=0
  for student,_,_ in rated:
   ids=db.scalars(select(e.enrollment_id).where(e.student_id==student.student_id,e.status=='in_progress')).all()
   extracted=[service.extract(db,eid,cut) for eid in ids]
   expected=overdue_counts(extracted)
   assert ctx.missed.get(student.student_id)==expected
   for row in extracted:
    if row['status']=='ready':assert 0<=row['evidence']['overdue_last_14_days']<=row['features']['overdue_assessments']
   checked+=len(ids)
  dashboard=advisor_dashboard.build(db,advisor)
  attention=int(next(x['value'] for x in dashboard['stats'] if x['key']=='attention'))
  assert attention==advisees.attention_count(db,advisor)
  filtered=advisees.list_for(db,advisor,'Needs attention')
  assert len(filtered['rows'])==attention
  assert next(t['count'] for t in filtered['tabs'] if t['label']=='Needs attention')==attention
  graduates=advisees.list_for(db,advisor,'Graduating')['rows']
  flagged_graduates={r['studentId'] for r in graduates if r['risk']!='Low'}
  assert flagged_graduates <= {r['studentId'] for r in filtered['rows']}
  searched=advisees.list_for(db,advisor,'Needs attention','Jonah')['rows']
  assert searched and all('jonah' in r['fullName'].lower() for r in searched)
  print('Attention filter, badge and dashboard agree; flagged graduating students included; name search verified')

 print('Shared extraction verified:',checked,'active enrollments;',len(rated),'assigned students; badge/dashboard count',attention,'; read-only; no model loading')
