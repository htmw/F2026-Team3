"""Clean-file-layout inference/explanation smoke. Reuses the installed Python runtime."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
MODEL_SHA="0cedcdb50402612df878415360cf13e1423063d595b4b2cb15ba5a097a5a9c30"
REFERENCE_SHA="0ae567ee6d1f5627e856209a064b80cd988b3a239b9591629558423aa4582ee2"


def prepare(destination,model_bundle,reference_bundle):
    destination=Path(destination).resolve()
    if not destination.is_relative_to(ROOT/"ml/outputs") or destination.exists():
        raise ValueError("New isolated handoff verification directory required")
    files=["ml/configs/FINAL_EXPERIMENT_V1.json","ml/fixtures/simulated_lms/events.json","backend/models.py",
        "backend/services/research_predictions.py","backend/risk_mvp/__init__.py","backend/risk_mvp/main_explanations.py",
        "backend/risk_mvp/explanation_references.py","backend/risk_mvp/service.py","backend/risk_mvp/models.py"]
    files += [str(p.relative_to(ROOT)) for p in (ROOT/"data/synthetic").glob("*.csv")]
    files += [str(p.relative_to(ROOT)) for p in (ROOT/"ml/src/acadmate_ml").glob("*.py")]
    for name in files:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable,str(ROOT/"tools/provision_ml_artifacts.py"),"install","--repo",str(destination),"--bundle",str(Path(model_bundle).resolve()),"--sha256",MODEL_SHA],env=env,check=True)
    subprocess.run([sys.executable,str(ROOT/"tools/provision_explanation_references.py"),"install","--repo",str(destination),"--bundle",str(Path(reference_bundle).resolve()),"--sha256",REFERENCE_SHA],env=env,check=True)
    env.pop("PYTHONPATH",None)
    subprocess.run([sys.executable,str(Path(__file__).resolve()),"--smoke-repo",str(destination)],env=env,check=True,cwd=destination)


def smoke(repo):
    # New main models import settings even for database-free inference. Never require a real DB for this check.
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://127.0.0.1:1/artifact_smoke_only")
    repo=Path(repo).resolve();sys.path[:0]=[str(repo/"backend"),str(repo/"ml/src")]
    from unittest.mock import patch
    from sqlalchemy.engine import Engine
    from sklearn.pipeline import Pipeline
    from sklearn.linear_model import LogisticRegression
    from services.research_predictions import PredictionService
    from acadmate_ml.simulated_lms import build
    from acadmate_ml.explain import explain
    from risk_mvp.main_explanations import training_background
    import services.research_predictions as module
    assert Path(module.__file__).resolve().is_relative_to(repo)
    assert not (repo/"ml/outputs/oulad-splits-v1").exists()
    os.environ["ACADMATE_RESEARCH_DEMO_ENABLED"]="true"
    service=PredictionService(repo)
    original_open=Path.open
    def guard(path,*args,**kwargs):
        if path.name in ("features.csv","labels.csv") or path.parent.name in ("validation","test"):
            raise AssertionError("Training/evaluation table access forbidden")
        return original_open(path,*args,**kwargs)
    with patch.object(Engine,"connect",side_effect=AssertionError("Artifact smoke must not connect to a database")), patch.object(Path,"open",guard), patch.object(Pipeline,"fit",side_effect=AssertionError("No training")), patch.object(LogisticRegression,"fit",side_effect=AssertionError("No calibration fitting")):
        scored=service.get(20014);missing=service.get(20044)
        assert abs(scored["research_risk_probability"]-.3783828964249184)<1e-12
        assert missing["status"]=="unavailable" and missing["research_risk_probability"] is None
        doc=build(json.loads((repo/"ml/fixtures/simulated_lms/events.json").read_text(encoding="utf-8-sig")),repo/"data/synthetic")
        doc["rows"]=[row for row in doc["rows"] if row["enrollment_id"]=="20014"]
        bg,metadata=training_background(str(repo),28)
        output=explain(doc,*service._artifacts,{28:bg})
        assert output["checks"]["explained_rows"]==1
        assert abs(output["rows"][0]["research_risk_probability"]-scored["research_risk_probability"])<1e-12
        assert len(output["rows"][0]["explanation"]["contributions"])==16
    print(json.dumps({"passed":True,"probability":scored["research_risk_probability"],"explanation_checks":output["checks"],"training_tables_present":False,"environment":"existing pinned runtime; fresh artifact/source file layout"},indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output");p.add_argument("--model-bundle");p.add_argument("--reference-bundle");p.add_argument("--smoke-repo")
    a=p.parse_args()
    if a.smoke_repo:smoke(a.smoke_repo)
    elif a.output and a.model_bundle and a.reference_bundle:prepare(a.output,a.model_bundle,a.reference_bundle)
    else:p.error("Provide output and both bundles")
