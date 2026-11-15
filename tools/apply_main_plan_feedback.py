"""Apply student feedback presentation to the isolated main export; no database writes."""
from pathlib import Path
import argparse,shutil
ROOT=Path(__file__).resolve().parents[1]
def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):raise ValueError('Isolated export required')
    path=snapshot/'backend/schemas/plan.py';text=path.read_text(encoding='utf-8')
    if '    advisor_feedback: str | None = None' not in text:
        text=text.replace('class TermOut(ApiModel):','class TermOut(ApiModel):\n    advisor_feedback: str | None = None')
    path.write_text(text,encoding='utf-8')
    path=snapshot/'backend/services/plan.py';text=path.read_text(encoding='utf-8')
    if 'from risk_mvp.plan_feedback import returned_feedback' not in text:
        text='from risk_mvp.plan_feedback import returned_feedback\n'+text
        old='out.append({"name": term.name, "tag": tag, "credits": _credits(rows), "courses": [_course_row(row) for row in rows]})'
        new='out.append({"name": term.name, "tag": tag, "credits": _credits(rows), "courses": [_course_row(row) for row in rows], "advisor_feedback": returned_feedback(db, student, term.id)})'
        if old not in text:raise ValueError('Plan output changed; review required')
        text=text.replace(old,new)
    path.write_text(text,encoding='utf-8')
    path=snapshot/'backend/services/degree_audit.py';text=path.read_text(encoding='utf-8')
    old='def graduation_status(db: Session, student: Student, groups: list[Group], warn: bool) -> str:\n'
    new=old+'    from risk_mvp.plan_feedback import has_returned_plan\n    if has_returned_plan(db, student):\n        return "Plan changes requested"\n'
    if '    if has_returned_plan(db, student):' not in text:
        if old not in text:raise ValueError('Graduation status changed; review required')
        text=text.replace(old,new)
    path.write_text(text,encoding='utf-8')
    shutil.copyfile(ROOT/'frontend/src/components/research/MainDegreePlan.jsx',snapshot/'frontend/src/pages/student/DegreePlan.jsx')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',required=True);apply(parser.parse_args().snapshot)
