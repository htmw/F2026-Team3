# Frozen ML artifact setup for teammates

The runtime intentionally excludes trained model files from Git. A fresh checkout can run database/student routes but cannot score a ready enrollment until the exact frozen artifacts are installed. A 503 can also mean a disabled demo, source-hash mismatch or incompatible runtime, so keep the integrity checks intact and inspect server logs when needed.

## Required files and frozen SHA-256

The expected paths are established by backend/services/research_predictions.py; hashes are recorded in ml/configs/FINAL_EXPERIMENT_V1.json. The sigmoid is inside calibration_maps.joblib, not a separate sigmoid file.

| File relative to checkout | SHA-256 |
|---|---|
| ml/outputs/baselines-v1/logistic_regression.joblib | 93cab4b90d3fc755b087be6343673b47ec3b163f4d4a8d3aace93e356fcb0020 |
| ml/outputs/calibration-v1/calibration_maps.joblib | d9ef14cad9c5d0cc8731e68b02633bb831ebed7a8ba6bb255bef2513f7be88e7 |

Only use the trusted package matching this experiment. The ZIP contains exactly those two files plus artifact-manifest.json. It contains no datasets, student records, credentials, environment or source code. Model serialization is unsafe for untrusted files; the installer checks the ZIP, manifest, both artifacts and frozen source before installation. It does not deserialize or train anything.

## Existing verified package

Local handoff location:

C:\Users\nhesv\Documents\AcadMate-Team\ml\outputs\handoff\acadmate-frozen-artifacts-v1.zip

ZIP SHA-256:

```text
0cedcdb50402612df878415360cf13e1423063d595b4b2cb15ba5a097a5a9c30
```

The checksum is also in acadmate-frozen-artifacts-v1.zip.sha256 beside the package. This is a newly prepared minimal package; do not confuse it with the earlier dated handoff ZIP that also contained instructions/scripts and therefore has a different checksum.

## Exact installation commands for Li

Run from the root of your own feature/academic-risk-prediction checkout. Place the supplied ZIP in Downloads, or adjust $artifactZip below. Keep an existing virtual environment; create one only if absent.

The new tools/provision_ml_artifacts.py and this document are currently LOCAL UNCOMMITTED changes. Until an approved commit makes the tool available remotely, share the Python tool separately alongside the ZIP and place it at tools/provision_ml_artifacts.py, or run it by absolute path with --repo pointing to your checkout. The ZIP deliberately contains only artifacts and their manifest. No package has been sent automatically.

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-research-demo.txt
$artifactZip = Join-Path $env:USERPROFILE 'Downloads\acadmate-frozen-artifacts-v1.zip'
$artifactSha = '0cedcdb50402612df878415360cf13e1423063d595b4b2cb15ba5a097a5a9c30'
if ((Get-FileHash -LiteralPath $artifactZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifactSha) { throw 'Artifact ZIP checksum mismatch' }
.\.venv\Scripts\python.exe tools/provision_ml_artifacts.py install --bundle $artifactZip --sha256 $artifactSha
.\.venv\Scripts\python.exe tools/provision_ml_artifacts.py verify --smoke
```

The verify --smoke step, unlike installation, loads the verified trusted artifacts and runs real fixture inference. Expected result: passed=true, enrollment 20014 probability 0.3783828964249184, enrollment 20044 unavailable with null probability. No database is contacted. Use the pinned runtime environment, including scikit-learn 1.9.1 and numpy 2.5.4. No model training is invoked.

Restart the backend after provisioning:

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:ACADMATE_RESEARCH_DEMO_ENABLED = 'true'
.\.venv\Scripts\python.exe -m uvicorn research_demo:app --host 127.0.0.1 --port 8001
```

In another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/v1/research/enrollments/20014/risk-prediction
Invoke-RestMethod http://127.0.0.1:8001/api/v1/research/enrollments/20044/risk-prediction
```

Use backend/RISK_MVP.md for the PostgreSQL-backed route and its flags. Its generated event inputs differ from the older fixed fixture, so it is not expected to produce the same numeric score for an identically numbered enrollment.

## Installation behavior and troubleshooting

- Only two fixed whitelisted paths are written; no general ZIP extraction occurs.
- The ZIP digest is required. Extra/duplicate entries, oversized entries, changed artifacts, incorrect manifests and changed frozen source are rejected.
- Existing correct files are retained and verified. Existing mismatched files are never overwritten; investigate them rather than weakening checks.
- Source mismatches: check branch/commit and the byte-preserving ml/.gitattributes rule. Do not change FINAL_EXPERIMENT_V1.json or normalize frozen source to make checks pass.
- Missing Python packages/version errors: install the pinned requirements into the interpreter running the backend.
- A copied model without calibration_maps.joblib is insufficient. Both hashes must match.
- The package does not supply historical train/test data or make retraining necessary.
- The binaries remain ignored. Provisioning never creates or modifies a database schema or network account.

## Package creation and tests

For the artifact owner, using a NEW destination filename:

```powershell
.\.venv\Scripts\python.exe tools/provision_ml_artifacts.py pack --bundle ml/outputs/handoff/frozen-artifacts-new.zip
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The pack command verifies local frozen files first and writes a ZIP plus a SHA-256 sidecar. Installation and package verification use only the Python standard library; --smoke additionally requires the pinned ML/backend dependencies. Full local validation included installation into a temporary clean checkout and genuine inference, not merely a hash check.

## Explanation provisioning follow-up

For optional SHAP explanations, the two-model ZIP is not sufficient by itself. See ML_EXPLANATION_SETUP.md for the separate identifier-free numeric reference package, runtime dependencies, clean-file-layout smoke and reproducible full-population audit commands. The original model ZIP and hashes remain unchanged.
