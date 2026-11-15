"""Apply shared read-only graduation estimates to the isolated main export."""
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def apply(snapshot):
    snapshot = Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT / "ml/outputs/main-integration"):
        raise ValueError("Isolated export required")
    names = ("dashboard", "student_record", "degree_audit", "advisees", "advisor_dashboard", "advisor_reports", "users", "approvals")
    for name in names:
        path = snapshot / f"backend/services/{name}.py"
        text = path.read_text(encoding="utf-8")
        if "student.expected_graduation" in text:
            text = text.replace("student.expected_graduation", "graduation_label(db, student)")
            text = 'from risk_mvp.graduation import graduation_label, graduation_note\n' + text
        if name in ("dashboard", "student_record", "degree_audit"):
            text = text.replace('"label": "Estimated graduation"', '"label": "Expected graduation"')
        if name == "advisees":
            text = text.replace('    parts = (value or "").split()\n    return f', '    if value == "Credits complete": return value\n    parts = (value or "").split()\n    return f')
        if name == "dashboard":
            text = text.replace('"pill": "Planned", "tone": "indigo", "pct": credits["pct"]', '"pill": "Estimate", "tone": "indigo", "pct": credits["pct"]')
            text = text.replace('"note": f"{remaining:g} credits to go"', '"note": graduation_note(db, student)')
        if name == "student_record":
            start = text.index('    graduation =')
            end = text.index('    return [', start)
            text = text[:start] + '    graduation = {"tag": "Estimate", "tone": "indigo", "note": graduation_note(db, student)}\n' + text[end:]
        if name == "degree_audit":
            text = text.replace('"note": graduation_note(db, student)', '"note": graduation_status(db, student, groups, warn)')
        path.write_text(text, encoding="utf-8")
    # Update only the two legacy expectations changed by this projection overlay.
    replacements = {
        "test_advisor_dashboard.py": (
            'assert data["graduation"] == [{"n": 3, "label": "Dec 2026"}, {"n": 3, "label": "May 2027"}, {"n": 2, "label": "Later"}]',
            'assert data["graduation"] == [{"n": 1, "label": "Dec 2026"}, {"n": 1, "label": "May 2027"}, {"n": 6, "label": "Later"}]'),
        "test_student_record.py": (
            'assert (stats["Expected graduation"]["tag"], stats["Expected graduation"]["note"]) == ("Pending", "If this plan is approved")',
            'assert stats["Expected graduation"]["value"] == "May 2027"\n    assert stats["Expected graduation"]["tag"] == "Estimate"\n    assert stats["Expected graduation"]["note"] == "Estimate assumes successful completion of current courses and 9 credits each Spring/Fall; required courses and approvals still apply."'),
    }
    for name, (old, new) in replacements.items():
        path = snapshot / "backend/tests" / name
        text = path.read_text(encoding="utf-8")
        if old not in text and new not in text:
            raise ValueError(f"Graduation assertion changed; review required: {name}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    import shutil
    shutil.copyfile(ROOT / "backend/tests/test_main_graduation_regression.py",
                    snapshot / "backend/tests/test_main_graduation_regression.py")
    print("Shared graduation estimates applied; no database or CSV writes")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    apply(parser.parse_args().snapshot)
