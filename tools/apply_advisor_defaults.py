"""Apply opt-in advisor defaults only to an isolated team export."""
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]

def apply(snapshot):
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration"):
        raise ValueError("Isolated export required")
    path=snapshot/"backend/services/meetings.py"
    text=path.read_text(encoding="utf-8")
    addition="\n# Opt-in defaults for the reviewed synthetic candidate; existing services retain booking validation.\nimport sys as _sys\nfrom risk_mvp.advisor_defaults import install as _install_advisor_defaults\n_install_advisor_defaults(_sys.modules[__name__])\n"
    if addition not in text:path.write_text(text+addition,encoding="utf-8")

    path=snapshot/"backend/services/advisor_meetings.py"
    text=path.read_text(encoding="utf-8")
    old="    for window in office_windows(db, advisor.user_id):\n        db.delete(window)"
    new="    for window in office_windows(db, advisor.user_id):\n        if window in db:  # Default windows are transient read-only values.\n            db.delete(window)"
    if new not in text:
        if text.count(old)!=1:raise ValueError("Office-hours update changed; review required")
        text=text.replace(old,new,1)
    old="    place = (location or \"\").strip() or _booking_location(db, advisor)"
    new="    from risk_mvp.advisor_defaults import mark_configured\n    mark_configured(db, advisor)\n"+old
    if new not in text:
        if text.count(old)!=1:raise ValueError("Office-hours configuration changed; review required")
        text=text.replace(old,new,1)
    old="    after = office_hours(db, advisor)"
    new='    after = office_hours(db, advisor) if days else {"days": [], "start": None, "end": None, "location": _booking_location(db, advisor), "summary": "No office hours set"}'
    if new not in text:
        if text.count(old)!=1:raise ValueError("Office-hours summary changed; review required")
        text=text.replace(old,new,1)
    path.write_text(text,encoding="utf-8")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--snapshot",required=True);apply(p.parse_args().snapshot)
