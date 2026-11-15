"""Apply student record refinements to the isolated main export only."""
from pathlib import Path
import argparse
import shutil
from apply_main_dashboard_review import ROOT, replace

def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'): raise ValueError('Isolated export required')
    path=snapshot/'backend/services/student_record.py'
    text=path.read_text(encoding='utf-8')
    old='    shared_ai = _shares_ai(db, student)\n    return {\n        "student": header(db, student),'
    new='    shared_ai = _shares_ai(db, student)\n    from services.advisees import risk_context, risk_for\n    _, concern = risk_for(student, risk_context(db, [student]))\n    return {\n        "concernSummary": concern,\n        "student": header(db, student),'
    text=replace(text,old,new)
    # Removed UI tile must not trigger the old lazy assignment creation path.
    if '    on_time, done, total = on_time_rate(db, student)' in text:
        start=text.index('    on_time, done, total = on_time_rate(db, student)')
        end=text.index('    graduation =', start)
        text=text[:start]+text[end:]
    text=text.replace('        on_time_tile,\n','')
    path.write_text(text,encoding='utf-8')
    path=snapshot/'backend/schemas/advisor.py'
    text=path.read_text(encoding='utf-8')
    text=replace(text,'class RecordOut(ApiModel):\n    student: RecordStudentOut','class RecordOut(ApiModel):\n    concern_summary: str | None = None\n    student: RecordStudentOut')
    path.write_text(text,encoding='utf-8')
    shutil.copyfile(ROOT/'frontend/src/components/research/MainStudentRecord.jsx',snapshot/'frontend/src/pages/advisor/StudentRecord.jsx')
    print('Student record overlay applied; database unchanged')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True,type=Path)
    apply(parser.parse_args().snapshot)
