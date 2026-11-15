"""Apply scoped admin presentation fixes to an isolated team export."""
from pathlib import Path
import argparse
ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise ValueError(f"Source changed; review required: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply(snapshot):
    snapshot = Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT / "ml/outputs/main-integration"):
        raise ValueError("Isolated export required")
    path = snapshot / "backend/services/admin_overview.py"
    replace_once(path, "from collections import Counter", "from collections import Counter\nfrom risk_mvp.admin_display import email_health, workload_percent")
    replace_once(path, "mail_status, mail_detail = mailer.health()", "mail_status, mail_detail = email_health(db)")
    replace_once(path, 'min(100, round(count / capacity * 100)) if capacity else 100', 'workload_percent(count, capacity)')
    path = snapshot / "frontend/src/pages/admin/Catalog.jsx"
    replace_once(path, '{shown.length === 0 ? <Empty>', '<p className="text-sm text-ink-muted">Course availability for {nextTerm?.name ?? "the next term"}. Offered and not offered labels apply to this term.</p>\n            {shown.length === 0 ? <Empty>')


    # Seed SMTP is disconnected. A degraded test must explicitly enable it first.
    path = snapshot / "backend/tests/test_admin_overview.py"
    replace_once(path, 'assert rows["mail"]["status"] == "Healthy"', 'assert rows["mail"]["status"] == "Off"')
    replace_once(path, 'def test_overview_shows_mail_degraded(client):', 'def test_overview_shows_mail_degraded(client, db):')
    replace_once(path, '    mailer.record_failure()\n    try:', '    from models import Integration\n    row = db.get(Integration, "mail")\n    previous = row.enabled\n    row.enabled = True\n    db.commit()\n    mailer.record_failure()\n    try:')
    replace_once(path, '        mailer._failures.clear()', '        mailer._failures.clear()\n        row.enabled = previous\n        db.commit()')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    apply(parser.parse_args().snapshot)
