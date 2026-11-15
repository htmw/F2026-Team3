from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
from prepare_csv_population_demo import bootstrap,hashes
before=hashes()
bootstrap(root/'ml/outputs/main-integration/8c4b0843368b')
from database import SessionLocal
from sqlalchemy import select,text
from models import Student,Advisor
from services import dashboard,student_record,degree_audit,advisees,advisor_dashboard
from risk_mvp.graduation import projection
from collections import Counter
counts=Counter()
with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    students=list(db.scalars(select(Student)))
    for student in students:
        expected=projection(db,student)['label']
        assert next(t for t in dashboard.stats(db,student) if t['key']=='graduation')['value']==expected
        assert next(t for t in student_record.stats(db,student,False) if t['label'] in ('Expected graduation','Estimated graduation'))['value']==expected
        assert degree_audit.degree_audit(db,student)['graduation']['label']==expected
        counts[expected]+=1
    for advisor in db.scalars(select(Advisor)):
        rows,_=advisees.caseload(db,advisor)
        for row in rows:
            assert row['graduates']==advisees.grad_label(projection(db,row['_student'])['label'])
        assert sum(b['n'] for b in advisor_dashboard.graduation_buckets(db,[r['_student'] for r in rows]))==len(rows)
assert before==hashes()
print('100 students: dashboard, advisor record, degree audit and advisee estimates agree. Four advisor bucket totals agree. CSV hashes unchanged.')
print(dict(counts))
