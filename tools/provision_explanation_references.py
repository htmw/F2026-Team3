"""Package/install original verified SHAP references; no model fitting or database access."""
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"backend"),str(ROOT/"ml/src"),str(ROOT/"tools")]
from risk_mvp.explanation_references import RELATIVE, POLICY, digest, validate, load
from provision_ml_artifacts import configuration
MAX_BYTES=8*1024*1024


def pack(repo,bundle):
    repo=Path(repo).resolve();bundle=Path(bundle)
    if bundle.exists() or bundle.with_suffix(bundle.suffix+".sha256").exists():
        raise ValueError("New package destination required")
    config=configuration(repo)
    from acadmate_ml.explain import background
    from acadmate_ml.splits import digest as file_digest
    report=repo/"ml/outputs/baselines-v1/validation_metrics.json"
    if file_digest(report)!=config["baseline_report_sha256"]:
        raise ValueError("Baseline hash mismatch")
    refs={}
    # Fixed demo offering length is 112 days. Do not silently synthesize later stages.
    for day in range(7,113,7):
        values,metadata=background(repo,day,128,42)
        import numpy as np
        refs[str(day)]={"metadata":metadata,"values":[[None if np.isnan(v) else float(v) for v in row] for row in values],
            "baseline_report_sha256":config["baseline_report_sha256"],"split_manifest_sha256":config["split_manifest_sha256"]}
    payload={"schema_version":"1.0","policy":POLICY,"config_sha256":digest((repo/"ml/configs/FINAL_EXPERIMENT_V1.json").read_bytes()),"features":config["features"],"references":refs}
    validate(repo,payload)
    raw=json.dumps(payload,allow_nan=False,sort_keys=True,separators=(",",":")).encode()
    manifest=json.dumps({"schema_version":"1.0","references_sha256":digest(raw),"bytes":len(raw)}).encode()
    bundle.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle,"x",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("references.json",raw);archive.writestr("manifest.json",manifest)
    checksum=digest(bundle.read_bytes())
    bundle.with_suffix(bundle.suffix+".sha256").write_text(checksum+"  "+bundle.name+"\n",encoding="utf-8")
    return {"zip_sha256":checksum,"reference_days":list(refs),"contains_identifiers":False,"contains_outcomes":False}


def install(repo,bundle,checksum):
    repo=Path(repo).resolve();configuration(repo)
    package=Path(bundle).read_bytes()
    if digest(package)!=checksum.lower():raise ValueError("ZIP checksum mismatch")
    if len(package)>MAX_BYTES:raise ValueError("Package too large")
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        if sorted(archive.namelist()) != ["manifest.json","references.json"]:raise ValueError("Unexpected package entries")
        if any(x.file_size>MAX_BYTES for x in archive.infolist()):raise ValueError("Entry too large")
        raw=archive.read("references.json");manifest=json.loads(archive.read("manifest.json"))
    if manifest.get("schema_version")!="1.0" or manifest["references_sha256"]!=digest(raw) or manifest["bytes"]!=len(raw):raise ValueError("Manifest mismatch")
    validate(repo,json.loads(raw))
    folder=repo/RELATIVE
    if not folder.resolve().is_relative_to(repo):raise ValueError("Target escapes checkout")
    receipt=json.dumps({"references_sha256":digest(raw),"trusted_zip_sha256":checksum.lower()},sort_keys=True).encode()
    for name,data in (("references.json",raw),("receipt.json",receipt)):
        target=folder/name
        if target.exists() and target.read_bytes()!=data:raise ValueError("Refuse mismatched installed references")
    folder.mkdir(parents=True,exist_ok=True)
    for name,data in (("references.json",raw),("receipt.json",receipt)):
        target=folder/name
        if not target.exists():
            with target.open("xb") as stream:stream.write(data)
    return verify(repo)


def verify(repo):
    repo=Path(repo)
    payload=json.loads((repo/RELATIVE/"references.json").read_text(encoding="utf-8"))
    validate(repo,payload)
    for day in payload["references"]:load(repo,int(day))
    return {"passed":True,"reference_days":list(payload["references"]),"training_csv_required":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["pack","install","verify"])
    parser.add_argument("--repo",type=Path,default=ROOT);parser.add_argument("--bundle",type=Path);parser.add_argument("--sha256")
    args=parser.parse_args()
    if args.action!="verify" and args.bundle is None:parser.error("--bundle required")
    if args.action=="install" and not args.sha256:parser.error("--sha256 required")
    try:
        result=pack(args.repo,args.bundle) if args.action=="pack" else install(args.repo,args.bundle,args.sha256) if args.action=="install" else verify(args.repo)
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as exc:parser.exit(1,"Reference setup failed: "+str(exc)+"\n")
    print(json.dumps(result,indent=2))
