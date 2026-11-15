"""Prepare a pinned, isolated team-code review export. Never connects to a database."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from prepare_main_risk_demo import ROOT, export

MAIN = "9dba938da14df8607c81b6f92988e8210977bf24"
DATTA = "a0c19303afbf51eda566b705e9934f6acb157627"
BASE = "8c4b0843368b679ac3f3353f6332c73356888b14"

def source(ref, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ref}:{path}"])

def apply_degree_ui(snapshot):
    relative = "frontend/src/pages/student/DegreePlan.jsx"
    text = (ROOT/"frontend/src/components/research/MainTeamDegreePlan.jsx").read_text(encoding="utf-8")
    for marker in ("/students/me/degree-progress", "term.advisorFeedback", "'Changes requested'", "course.planStatus : courseStatusLabel(course)"):
        if marker not in text:raise ValueError(f"Combined degree page lost required behavior: {marker}")
    (snapshot/relative).write_text(text,encoding="utf-8")
    # Share the existing projection explanation without replacing approval-aware status.
    schema=snapshot/"backend/schemas/plan.py"
    contents=schema.read_text(encoding="utf-8")
    if "    estimate_note: str | None = None" not in contents:
        old="class GraduationOut(ApiModel):\n    label: str\n    status: str"
        if contents.count(old)!=1:raise ValueError("Graduation schema changed; review required")
        contents=contents.replace(old,old+"\n    estimate_note: str | None = None",1)
        schema.write_text(contents,encoding="utf-8")
    service=snapshot/"backend/services/degree_audit.py"
    contents=service.read_text(encoding="utf-8")
    old='"graduation": {"label": graduation_label(db, student) or "\u2014", "status": tiles[3]["note"]}'
    new='"graduation": {"label": graduation_label(db, student) or "\u2014", "status": tiles[3]["note"], "estimate_note": graduation_note(db, student)}'
    if new not in contents:
        if contents.count(old)!=1:raise ValueError("Graduation output changed; review required")
        contents=contents.replace(old,new,1)
        service.write_text(contents,encoding="utf-8")

    test=snapshot/"backend/tests/test_plan.py"
    contents=test.read_text(encoding="utf-8")
    old='assert data["graduation"] == {"label": "May 2027", "status": "Pending capstone approval"}'
    new='assert data["graduation"] == {"label": "May 2027", "status": "Pending capstone approval", "estimateNote": "Estimate assumes successful completion of current courses and 9 credits each Spring/Fall; required courses and approvals still apply."}'
    if new not in contents:
        if contents.count(old)!=1:raise ValueError("Graduation response assertion changed; review required")
        test.write_text(contents.replace(old,new,1),encoding="utf-8")


def apply_admin_regressions(snapshot):
    """Fix two tests reproduced unchanged on pinned main; do not change admin behavior."""
    path=snapshot/"backend/tests/test_admin_advisors.py"
    text=path.read_text(encoding="utf-8")
    old='    assert set(kim) == {"id", "userId", "name", "dept", "load", "cap", "pending", "resp", "status", "active",'
    new='    assert "temporaryPassword" not in kim  # List service never exposes a password.\n    from schemas.admin import AdminAdvisorRow\n    kim = AdminAdvisorRow.model_validate(kim).model_dump(by_alias=True)\n'+old
    if new not in text:
        if text.count(old)!=1: raise ValueError("Advisor test changed; manual review required")
        text=text.replace(old,new,1)
    path.write_text(text,encoding="utf-8")
    path=snapshot/"backend/tests/test_admin_users.py"
    text=path.read_text(encoding="utf-8")
    old='def test_reset_password(db, sent, make_user):\n    admin = db.get(User, ADMIN_ID)\n    user = make_user("student")'
    new='def test_reset_password(db, sent, make_user):\n    admin = db.get(User, ADMIN_ID)\n    user = db.get(User, make_user("student").user_id)  # Attach the fixture user to this test session.'
    if new not in text:
        if text.count(old)!=1: raise ValueError("Password reset test changed; manual review required")
        text=text.replace(old,new,1)
    path.write_text(text,encoding="utf-8")

def prepare(snapshot):
    snapshot = Path(snapshot).resolve()
    if not snapshot.is_relative_to(ROOT / "ml/outputs/main-integration") or snapshot.exists():
        raise ValueError("A new isolated output directory is required")
    # Datta adds routes to the same student router. Refuse to overwrite newer team edits.
    router = "backend/routers/students.py"
    if source(BASE, router) != source(MAIN, router):
        raise ValueError("Latest student router changed; manual integration required")
    export(snapshot, MAIN)
    adopted = [router, "backend/services/degree_progress.py", "backend/schemas/degree_progress.py", "backend/tests/test_degree_progress.py"]
    for name in adopted:
        (snapshot/name).write_bytes(source(DATTA, name))
    # Apply authored UI/service patches only in this disposable export.
    from apply_main_dashboard_review import apply as dashboard
    from apply_main_advisees_review import apply as advisees
    from apply_main_student_record_review import apply as record
    from apply_main_record_coverage_review import apply as coverage
    from apply_main_graduation import apply as graduation
    from apply_main_approvals_review import apply as approvals
    from apply_main_plan_feedback import apply as feedback
    for patch in (dashboard, advisees, record, coverage, graduation, approvals, feedback):
        patch(snapshot)
    dest = snapshot / "frontend/src/components/research/MainResearchRisk.jsx"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/"frontend/src/components/research/MainResearchRisk.jsx", dest)
    # Keep Datta's degree-progress UI delta AND our feedback/approved-status behavior.
    apply_degree_ui(snapshot)
    apply_admin_regressions(snapshot)
    from apply_main_admin_display import apply as admin_display
    admin_display(snapshot)
    from apply_advisor_defaults import apply as advisor_defaults
    advisor_defaults(snapshot)
    from apply_project_help import apply as project_help
    project_help(snapshot)
    for test in (ROOT/"backend/tests").glob("test_main_*.py"):
        shutil.copyfile(test, snapshot/"backend/tests"/test.name)
    report = {"main_commit": MAIN, "datta_commit": DATTA, "adopted_files": adopted,
              "dataset_policy": "No CSV copied or changed; dataset reconciliation pending",
              "database_operations": False, "li_published_version": "Not yet identified",
              "combined_degree_plan_sha256": hashlib.sha256((snapshot/"frontend/src/pages/student/DegreePlan.jsx").read_bytes()).hexdigest()}
    (snapshot/"team-review-manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    prepare(parser.parse_args().snapshot)
