"""Apply reviewed approvals UI and expose stored nonblocking warnings in the isolated export."""
from pathlib import Path
import argparse,shutil
ROOT=Path(__file__).resolve().parents[1]
def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/'ml/outputs/main-integration'):raise ValueError('Isolated export required')
    path=snapshot/'backend/schemas/approvals.py';text=path.read_text(encoding='utf-8')
    if 'warnings: list[str]' not in text:
        text=text.replace('from pydantic import StringConstraints','from pydantic import Field, StringConstraints')
        text=text.replace('    check_short: str','    warnings: list[str] = Field(default_factory=list)\n    check_short: str')
    path.write_text(text,encoding='utf-8')
    path=snapshot/'backend/services/approvals.py';text=path.read_text(encoding='utf-8')
    needle='        "checkShort": "Pre-check passed" if ok else "Needs a look",'
    addition='        "warnings": [c["text"] for c in ((request.precheck or {}).get("checks") or []) if not c.get("ok") and not c.get("blocking") and c.get("text")],\n'
    if addition not in text:
        if needle not in text:raise ValueError('Approval row changed; review required')
        text=text.replace(needle,addition+needle)
    text=text.replace('Meets every remaining requirement.{graduation}', 'Covers the remaining course requirements.{graduation}')
    text=text.replace(' Graduation stays on track for {graduation_label(db, student)}.', ' Credit-based graduation estimate: {graduation_label(db, student)}; completion and outstanding checks still apply.')
    path.write_text(text,encoding='utf-8')
    shutil.copyfile(ROOT/'frontend/src/components/research/MainAdvisorApprovals.jsx',snapshot/'frontend/src/pages/advisor/Approvals.jsx')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',required=True);apply(parser.parse_args().snapshot)
