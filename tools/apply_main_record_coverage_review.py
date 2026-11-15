"""Mark absent enrollment records in the isolated demo; never creates data."""
from pathlib import Path
import argparse
from apply_main_dashboard_review import ROOT, replace

def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'): raise ValueError('Isolated export required')
    p=snapshot/'backend/services/advisees.py';s=p.read_text(encoding='utf-8')
    s=replace(s,'TABS = ("All", "Needs attention", "On track", "Graduating")','TABS = ("All", "Needs attention", "On track", "Graduating", "No academic records")')
    s=replace(s,'    credits = _credits(db, ids) if ids else {}','    recorded_ids = {sid for sid, in db.query(Enrollment.student_id).filter(Enrollment.student_id.in_(ids)).distinct()}\n    credits = _credits(db, ids) if ids else {}')
    s=replace(s,'"status": status_for(level, graduating), "risk": level,','"status": status_for(level, graduating) if student.student_id in recorded_ids else "No academic records", "risk": level,')
    s=replace(s,'if status == "On track": return row["risk"] == "Low"','if status == "On track": return row["risk"] == "Low" and row["status"] != "No academic records"')
    s=replace(s, '            for label in TABS]', '            for label in TABS if label != "No academic records" or any(row["status"] == label for row in rows)]')
    p.write_text(s,encoding='utf-8')
    for name in ['backend/schemas/advisor.py','backend/routers/advisor.py']:
        p=snapshot/name;s=p.read_text(encoding='utf-8')
        if name.endswith('schemas/advisor.py'):
            s=s.replace('Literal["accent", "amber", "violet"]','Literal["accent", "amber", "violet", "slate"]')
            s=s.replace('Literal["All", "Needs attention", "On track", "Graduating"]','Literal["All", "Needs attention", "On track", "Graduating", "No academic records"]')
            s=s.replace('Literal["On track", "Needs attention", "Graduating"]','Literal["On track", "Needs attention", "Graduating", "No academic records"]')
            s=replace(s,'class RecordOut(ApiModel):','class RecordOut(ApiModel):\n    has_academic_records: bool = True')
        else:s=replace(s,'Literal["All", "Needs attention", "On track", "Graduating", "At risk"]','Literal["All", "Needs attention", "On track", "Graduating", "At risk", "No academic records"]')
        p.write_text(s,encoding='utf-8')
    p=snapshot/'backend/services/student_record.py';s=p.read_text(encoding='utf-8')
    if 'from models import Enrollment\n' not in s: s='from models import Enrollment\n'+s
    s=replace(s,'        "concernSummary": concern,','        "hasAcademicRecords": db.query(Enrollment.enrollment_id).filter(Enrollment.student_id == student_id).first() is not None,\n        "concernSummary": concern,')
    p.write_text(s,encoding='utf-8')
    p=snapshot/'backend/services/advisor_reports.py';s=p.read_text(encoding='utf-8')
    s=replace(s,'("Graduating", "violet"))','("Graduating", "violet"), ("No academic records", "slate"))')
    s=replace(s, '            for label, tone in STATUS_TONES]', '            for label, tone in STATUS_TONES if label != "No academic records" or any(row["status"] == label for row in rows)]')
    p.write_text(s,encoding='utf-8')
    s=s.replace('row["status"], row["risk"],', 'row["status"], "" if row["status"] == "No academic records" else row["risk"],')
    p.write_text(s,encoding='utf-8')
    p=snapshot/'frontend/src/pages/advisor/Reports.jsx';s=p.read_text(encoding='utf-8')
    s=replace(s, "violet: 'var(--color-violet)' }", "violet: 'var(--color-violet)', slate: 'var(--color-muted)' }")
    p.write_text(s,encoding='utf-8')
    print('Applied absent-academic-records state; no database writes.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);apply(p.parse_args().snapshot)
