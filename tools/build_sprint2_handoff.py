"""Assemble reviewed source only; refuse existing destinations and exclude runtime/sensitive files."""
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={".py",".js",".jsx",".json",".css",".html",".md",".txt",".csv",".sql",".ps1",".svg"}
EXCLUDED={"node_modules","dist",".venv","venv","__pycache__",".git",".pytest_cache","outputs"}
SECRET=re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{40,}")

def build(snapshot,output):
    snapshot=Path(snapshot).resolve();output=Path(output).resolve()
    if not snapshot.is_relative_to(ROOT/"ml/outputs/main-integration") or not output.is_relative_to(ROOT/"ml/outputs") or output.exists():
        raise ValueError("Reviewed isolated candidate and NEW ignored destination required")
    provenance=json.loads((snapshot/"team-demo-manifest.json").read_text())
    assert provenance["state"]=="complete" and provenance["database"]=="acadmate_risk_team_review_sprint2"
    stage=output/"source";stage.mkdir(parents=True)
    origins={}
    def copy(path,target,origin):
        if path.is_symlink() or any(part in EXCLUDED for part in target.parts) or path.name.startswith(".env") or path.suffix.lower() not in ALLOWED:return
        raw=path.read_bytes()
        if SECRET.search(raw):raise ValueError("Credential-like material requires review in "+str(target))
        dest=stage/target;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        origins[target.as_posix()]=origin
    def tree(source,target,origin):
        for path in sorted(source.rglob("*")):
            if path.is_file():copy(path,target/path.relative_to(source),origin+"/"+path.relative_to(source).as_posix())
    for name in ("backend","frontend/src","frontend/public"):
        tree(snapshot/name,Path(name),"reviewed-export/"+name)
    for name in ("frontend/package.json","frontend/package-lock.json","frontend/index.html","frontend/vite.config.js"):
        copy(snapshot/name,Path(name),"reviewed-export/"+name)
    for name in ("backend/risk_mvp","backend/knowledge","backend/migrations","frontend/src/components/research","frontend/src/research","frontend/tests","ml/src","ml/configs","ml/fixtures","ml/reports","ml/tests","tests","tools","data/synthetic","data/knowledge"):
        tree(ROOT/name,Path(name),"authored/"+name)
    for path in (ROOT/"backend").glob("*.md"):copy(path,Path("backend")/path.name,"authored/backend/"+path.name)
    for path in (ROOT/"ml").glob("*.md"):copy(path,Path("ml")/path.name,"authored/ml/"+path.name)
    for path in (ROOT/"ml").glob("requirements*.txt"):copy(path,Path("ml")/path.name,"authored/ml/"+path.name)
    for name in ("backend/services/research_predictions.py","backend/routers/research_predictions.py","backend/schemas/research_predictions.py","backend/research_demo.py","frontend/src/pages/advisor/AcademicRisk.jsx"):
        copy(ROOT/name,Path(name),"authored/"+name)
    files={name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in sorted(origins)}
    config=json.loads((stage/"ml/configs/FINAL_EXPERIMENT_V1.json").read_text())
    for name,digest in config["source_sha256"].items():assert files["ml/src/acadmate_ml/"+name]==digest
    readme=r"""# AcadMate Sprint 2 reviewed source package

This source snapshot contains the tested combined React/FastAPI candidate plus authored ML/knowledge modules, tests, proposed schema, fixed synthetic CSVs, developer preparation/verification tools and current documentation. Review MANIFEST.json for per-file hashes and provenance. It includes no .git history and is not a claim that the branch has been committed, pushed or merged. Keep this package separate from another checkout until reviewing changes; do not blindly overwrite teammates' work.

## Verify and install dependencies

From the extracted source root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r ml/requirements-shap.txt
.\.venv\Scripts\python.exe -m pip check
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

The backend requirements are the reviewed combined candidate, not the older standalone backend manifest. The tested Python version is 3.13.14. This package deliberately excludes .env files, credentials, node_modules, virtual environments, generated datasets/audits, database dumps/sessions, trained binaries and original OULAD tables. Preserve the eight academic CSVs and their metadata exactly. Source tests include fake credentials and documented public synthetic demo identities, not institutional secrets. Optional frontend browser tests additionally use jsdom 30.1.3 from the existing validation environment; it is not a production dependency.

Install the separately shared, checksum-verified frozen-model ZIP and explanation-reference ZIP with tools/provision_ml_artifacts.py and tools/provision_explanation_references.py. See backend/ML_ARTIFACT_SETUP.md and backend/ML_EXPLANATION_SETUP.md. Then run:

```powershell
.\.venv\Scripts\python.exe tools/verify_clean_ml_handoff.py --smoke-repo .
```

No retraining or original training CSV is required. Do not run pack commands, training commands or reset a database to provision artifacts.

## Database and running the reviewed application

This source package does not install PostgreSQL, create a full demo database or contain a private database dump. The already prepared synthetic loopback cluster uses port 55439 and acadmate_risk_team_review_sprint2. A new machine must prepare the same guarded synthetic population/sidecars using the normal checkout preparation tools and data manifests before serving this host. Existing developer tools that require ml/outputs/main-integration exports or pinned Git objects still require that original checkout layout; they are included for review, not as commands to run blindly from this flat snapshot. Never use a shared Neon or institutional URL.

Once the named local demo DB and artifacts are prepared, run from this extracted root:

```powershell
$env:PYTHONPATH="$PWD\backend;$PWD\ml\src"
$env:DATABASE_URL='postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_team_review_sprint2'
$env:ACADMATE_RISK_MVP_ENABLED='true'
$env:ACADMATE_TODAY='2027-02-16'
$env:SESSION_COOKIE='acadmate_team_review_session'
$env:FRONTEND_ORIGIN='http://127.0.0.1:5179'
.\.venv\Scripts\python.exe -m uvicorn risk_mvp.team_host:app --host 127.0.0.1 --port 8005
```

In a separate terminal from extracted root:

```powershell
$env:API_PROXY_TARGET='http://127.0.0.1:8005'
$env:VITE_API_URL='/api/v1'
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5179 --strictPort
```

Use free ports and stop an already running local demo through its owning process before starting another. Open http://127.0.0.1:5179. Follow backend/DEMO_WALKTHROUGH.md and backend/SPRINT2_DEMO_READINESS.md. The source/artifact package pins make results reproducible; normal peer review still matters before integrating into shared branches. Historical documentation retains older fixtures and counts; start with current readiness and handoff documents.

## Evidence and limitations

433 backend tests passed with defaults enabled and real-artifact smoke. All 105 identities passed 2,777 live HTTP checks. A separate full-population test clone passed 2,000 write-workflow checks across 100 students, using an in-process identity override and blocked external mail. Frozen inference and explanations were audited for all 179 active enrollments; 621 historical courses remain unscored. The latest frontend result is 14 passed with one explicitly skipped older standalone live demo, and the production build passed. Synthetic consistency is not institutional predictive accuracy. No local report authorizes shared migrations, external messages or merges.

PowerPoint/Word originals are not included as updated deliverables until native editing/render access is available. Current manual/presentation update text is included in backend/. Model binaries must be shared separately with their trusted SHA-256 values.
"""
    (stage/"PACKAGE_README.md").write_text(readme,encoding="utf-8")
    files["PACKAGE_README.md"]=hashlib.sha256((stage/"PACKAGE_README.md").read_bytes()).hexdigest()
    manifest={"schema_version":1,"kind":"source_review_snapshot","branch":"feature/academic-risk-prediction","working_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"uncommitted_work_included":True,"main":"9dba938da14df8607c81b6f92988e8210977bf24","datta":"a0c19303afbf51eda566b705e9934f6acb157627","files":files,"origins":origins,"database_included":False,"model_binaries_included":False,"environment_files_included":False}
    (stage/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    archive=output/"AcadMate-Sprint2-Review-Source.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():z.write(path,path.relative_to(stage).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/(archive.name+".sha256")).write_text(digest+"  "+archive.name+"\n",encoding="ascii")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,expected in files.items():assert hashlib.sha256(z.read(name)).hexdigest()==expected
        assert not any(name.startswith("ml/outputs/") or any(part in EXCLUDED for part in Path(name).parts) or Path(name).name.startswith(".env") for name in z.namelist())
    print(json.dumps({"archive":str(archive),"sha256":digest,"source_files":len(files),"manifest_verified":True},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True);a=p.parse_args();build(a.snapshot,a.output)
