"""Apply scoped advisee filter and search fixes only to the isolated main export."""
from pathlib import Path
import argparse
import shutil
from apply_main_dashboard_review import ROOT, replace

def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'): raise ValueError('Isolated export required')
    path=snapshot/'backend/services/advisees.py'
    text=path.read_text(encoding='utf-8')
    text=replace(text,
        'tabs = [{"label": label, "count": len(rows) if label == "All" else sum(1 for r in rows if r["status"] == label)}',
        'tabs = [{"label": label, "count": sum(1 for r in rows if matches_filter(r, label))}')
    text=replace(text,
        '    elif status != "All":\n        shown = [r for r in shown if r["status"] == status]',
        '    elif status != "All":\n        shown = [r for r in shown if matches_filter(r, status)]')
    text=replace(text, 'attention = lambda r: r["status"] == "Needs attention"', 'attention = lambda r: r["risk"] != "Low"')
    helper = '''def matches_filter(row, status):
    # Graduation timing and attention are independent; tabs deliberately overlap.
    if status == "All": return True
    if status == "Needs attention": return row["risk"] != "Low"
    if status == "On track": return row["risk"] == "Low"
    if status == "At risk": return row["risk"] == "High"
    return row["status"] == status


'''
    if 'def matches_filter(' not in text:
        text=text.replace('def list_for(', helper+'def list_for(',1)
    path.write_text(text,encoding='utf-8')
    shutil.copyfile(ROOT/'frontend/src/components/research/MainAdvisorAdvisees.jsx',snapshot/'frontend/src/pages/advisor/Advisees.jsx')
    # The no-current-flags filter now also includes low-risk graduating students.
    test=snapshot/'backend/tests/test_advisees.py'
    text=test.read_text(encoding='utf-8')
    text=replace(text, '{"All": 8, "Needs attention": 4, "On track": 3, "Graduating": 1}', '{"All": 8, "Needs attention": 4, "On track": 4, "Graduating": 1}')
    test.write_text(text,encoding='utf-8')
    # Reports must use the same overlapping filters and actual caseload denominator.
    path=snapshot/'backend/services/advisor_reports.py'
    text=path.read_text(encoding='utf-8')
    text=replace(text, 'from services.advisees import caseload, drops_below_full_time, failed_check, last_contact', 'from services.advisees import caseload, drops_below_full_time, failed_check, last_contact, matches_filter')
    text=replace(text, 'sum(1 for row in rows if row["status"] == label)', 'sum(1 for row in rows if matches_filter(row, label))')
    path.write_text(text,encoding='utf-8')
    path=snapshot/'frontend/src/pages/advisor/Reports.jsx'
    text=path.read_text(encoding='utf-8')
    text=replace(text, '<StatusBars rows={data.byStatus} />', '<StatusBars rows={data.byStatus} total={Number(data.stats.find(s => s.label === "Advisees")?.value ?? 0)} />')
    text=replace(text, 'function StatusBars({ rows }) {\n  const total = rows.reduce((sum, row) => sum + row.count, 0)', 'function StatusBars({ rows, total }) {')
    text=replace(text, '<CardHeader title="Advisees by status" />', '<CardHeader title="Advisee overview" subtitle="Graduation can overlap with attention status." />')
    text=replace(text, '<span className="text-sm font-semibold">{row.label}</span>', '<span className="text-sm font-semibold">{row.label === "On track" ? "No current flags" : row.label}</span>')
    path.write_text(text,encoding='utf-8')
    print('Advisees overlay applied; source checkout and database unchanged')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    apply(parser.parse_args().snapshot)
