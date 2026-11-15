"""Apply reviewed dashboard clarity changes to the isolated main export only.
No database writes, model changes, or changes to approval decisions.
"""
from pathlib import Path
import argparse
import shutil
ROOT = Path(__file__).resolve().parents[1]

def replace(text, old, new):
    if new in text: return text
    if text.count(old) != 1: raise ValueError('Main source changed; review dashboard patch before applying')
    return text.replace(old, new, 1)

def apply(snapshot):
    snapshot = Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT / 'ml/outputs/main-integration'):
        raise ValueError('Isolated main export required')
    path = snapshot / 'backend/services/advisees.py'
    text = path.read_text(encoding='utf-8')
    text = replace(text,
        'return "Medium", f"{first} hasn\'t signed in for {INACTIVE_DAYS}+ days and has no plan for next term."',
        'return "Medium", (f"No sign-in history is recorded for {first}, and no plan for next term is recorded." if last is None else f"{first} hasn\'t signed in to AcadMate for {INACTIVE_DAYS}+ days and has no plan for next term.")')
    text = replace(text, 'Meeting.status.in_(("confirmed", "completed")))', 'Meeting.status == "completed")')
    text = replace(text, 'Latest past meeting or direct message between the advisor and each student, as a school-time date.', 'Latest completed meeting or recorded direct message, as a school-time date; not proof of a reply.')
    # A future-dated message is unknown evidence, not contact at the current time.
    text = replace(text, 'at = min(at, current)', 'if at is None or at > current:\n            continue')
    text = replace(text, '    return ctx\n\n\ndef _failed_check',
        '    from risk_mvp.main_attention import align_context\n    align_context(db, students, ctx)\n    return ctx\n\n\ndef _failed_check')
    text = replace(text, 'f"{first} missed {missed} deadlines in the last two weeks."',
        'f"{first} has {missed} overdue assessments with deadlines in the last two weeks."')
    text = replace(text, '    return "Low", None',
        '    from risk_mvp.main_attention import course_review_reason\n    course_reason = course_review_reason(student.student_id, ctx)\n    if course_reason: return "Medium", course_reason\n    return "Low", None')
    text = text.replace('    if level == "High":\n        return risk_flag', '    if risk_flag:\n        return risk_flag', 1)
    path.write_text(text, encoding='utf-8')
    shutil.copyfile(ROOT / 'frontend/src/components/research/MainAdvisorDashboard.jsx', snapshot / 'frontend/src/pages/advisor/Dashboard.jsx')
    path = snapshot / 'frontend/src/components/layout/Sidebar.jsx'
    text = path.read_text(encoding='utf-8')
    text = text.replace('{badge}{role === "advisor" && item.badgeKey === "advisees" ? " to review" : ""}', '{badge}')
    text = replace(text, '{badge && <span className="ml-auto text-xs font-bold text-sun">{badge}</span>}',
        '{badge && <span className="ml-auto text-xs font-bold text-sun" aria-label={role === "advisor" && item.badgeKey === "advisees" ? `${badge} students to review` : undefined}>{badge}</span>}')
    path.write_text(text, encoding='utf-8')
    print('Dashboard overlay applied; source checkout and database unchanged')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    apply(parser.parse_args().snapshot)
