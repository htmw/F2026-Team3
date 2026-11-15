# Prediction and explanation handoff

> Current checkpoint (November 14, 2026): see [SPRINT2_HANDOFF.md](SPRINT2_HANDOFF.md) for the reconciled status. Later evidence supersedes older pending/count statements below: 433 full backend passes with advisor defaults enabled; 14 full frontend passes with one older live test skipped; final plain-text UI change passed its focused test/build. Project-help retrieval is delivered for checked project guides only, with no displayed guide links. Institutional-policy retrieval, S2-08 policy approval and team release acceptance remain pending. Earlier dated evidence is retained.

Status: locally verified November 14, 2026. This extends ML_ARTIFACT_SETUP.md. No retraining, frozen hash change, shared database operation, commit or push.

## Required source and runtime

Use the reviewed academic-risk branch/source candidate, including `backend/risk_mvp/explanation_references.py`, updated `main_explanations.py`, `tools/provision_explanation_references.py`, and the existing model installer. The reference installer imports the loader module, so sharing its Python file alone is insufficient without these reviewed source changes. The live team app remains an isolated pinned export, not a merged release. Obtain the same reviewed source before teammate acceptance.

Install in the teammate's chosen Python environment from checkout root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-research-demo.txt -r ml/requirements-shap.txt
.\.venv\Scripts\python.exe -m pip check
```

The initial check reused the installed runtime. The later fresh-environment checkpoint below installed dependencies into a new isolated venv on this machine and passed actual inference/explanation checks. A teammate machine remains a separate acceptance boundary. The commands above apply to the original standalone source; use the candidate-specific commands below for the combined team app.

## Two separate trusted packages

The original model package is unchanged. It contains the logistic model, calibration maps and checksum manifest. Follow ML_ARTIFACT_SETUP.md to install it.

The new explanation package is located at:

`ml/outputs/handoff/acadmate-explanation-references-v1.zip`

SHA-256:

```text
0ae567ee6d1f5627e856209a064b80cd988b3a239b9591629558423aa4582ee2
```

It contains only references.json and manifest.json. References are the exact original outcome-independent, seed-42 samples of 128 numeric training vectors at each weekly day 7 through 112. These are derived OULAD observations, not newly generated student values. Student/enrollment identifiers, names, outcome labels, credentials, raw source tables and model binaries are absent. Per-stage metadata preserves sample selection/training hashes; frozen configuration, baseline-report and split-manifest hashes link the package to the original experiment.

The producer validates original source hashes before sampling. The recipient verifies the trusted ZIP digest, manifest, numeric schema and frozen configuration linkage. The recipient does not independently regenerate samples from the full training CSV. A trusted package checksum is therefore part of the handoff, not optional proof supplied by the ZIP itself.

From the teammate's checkout root, after the model install:

```powershell
$referenceZip = Join-Path $env:USERPROFILE 'Downloads\acadmate-explanation-references-v1.zip'
$referenceSha = '0ae567ee6d1f5627e856209a064b80cd988b3a239b9591629558423aa4582ee2'
.\.venv\Scripts\python.exe tools/provision_explanation_references.py install --bundle $referenceZip --sha256 $referenceSha
.\.venv\Scripts\python.exe tools/provision_explanation_references.py verify
.\.venv\Scripts\python.exe tools/provision_ml_artifacts.py verify --smoke
```

Installation refuses mismatched existing files, unexpected ZIP entries, invalid numeric data and configuration mismatches. All integrity checks precede installation. Installed references are under ignored ml/outputs/explanation-references-v1/. Restart the local API after provisioning; already loaded immutable references are process-cached.

When an installed reference directory exists, serving uses it and fails closed if it is invalid or lacks the requested stage. It does not silently switch to another background or invent values. The existing optional explanation layer preserves a valid prediction if explanation loading fails. Without a provisioned directory, the original hash-verified training-source path remains available for the original research environment. The preceding-week reference policy, model, calibration and mathematical explanation algorithm remain unchanged. Stages beyond the packaged range require a separately reviewed reference package; no silent extrapolation is introduced.

## Fresh-layout smoke reproduction

Use a NEW ignored output directory each time. Both bundle arguments refer to the trusted original packages, whose SHA-256 values are pinned in this verifier:

```powershell
.\.venv\Scripts\python.exe tools/verify_clean_ml_handoff.py `
  --output ml/outputs/handoff-check-new `
  --model-bundle "$env:USERPROFILE\Downloads\acadmate-frozen-artifacts-v1.zip" `
  --reference-bundle "$env:USERPROFILE\Downloads\acadmate-explanation-references-v1.zip"
```

The verifier copies only required source, frozen config and existing synthetic fixtures into a new layout, installs the verified packages, and starts a separate smoke process. It does not copy the original OULAD training/validation/test tables. It forbids training and calibration fits and table access during smoke. It invokes actual inference and SHAP through the provisioned runtime reference loader. It does not connect to PostgreSQL or a network service.

Actual local result: passed. Original scored fixture 20014 remained 0.3783828964249184; fixture 20044 remained unavailable/null. One explained row, 16 grouped contributions, 20 transformed columns; maximum raw reconstruction error 1.67e-16 and calibrated reconstruction error 0.0. Evidence layout: ml/outputs/handoff-check-v1/. This is file-layout isolation using the existing runtime, not a full deployment or fresh dependency installation.

## Recreate full-population narrative acceptance inputs

Requires the verified 100-student team-review clone and API on localhost:8005, as documented in TEAM_INTEGRATION_REVIEW.md. The command is intentionally limited to this local synthetic target, not arbitrary shared databases. Authentication adds ordinary local login audit/session records; academic reads use read-only transactions. No academic import, generation or mutation occurs.

```powershell
.\.venv\Scripts\python.exe tools/verify_population_narratives.py `
  --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930 `
  --output ml/outputs/population-narrative-check-new
```

This sequentially recreates all four advisor audit JSON files in a new ignored directory, then runs the real frontend narrative assertions against those fresh files. ACADMATE_MAIN_SNAPSHOT and ACADMATE_ADVISOR_AUDIT_DIR are set by the runner. It does not reuse saved audit files or silently skip the narrative test. Existing output destinations are refused; failed runs retain partial evidence and must use a new destination on retry.

The audit compares all 16 extracted features with independent calculations, verifies real frozen-model and SHAP reconstruction, checks identities, academic concern/count consistency, historical unavailable results and unchanged academic fingerprints. Model outputs are not compared with invented synthetic outcome labels.

Actual run: ml/outputs/population-narrative-check-v1/.

| Advisor | Students | All enrollments | Active scored/explained | Historical unscored | Needs attention |
|---|---:|---:|---:|---:|---:|
| Sarah | 25 | 202 | 44 | 158 | 22 |
| Rowan | 25 | 202 | 44 | 158 | 20 |
| Sage | 25 | 198 | 44 | 154 | 20 |
| Quinn | 25 | 198 | 47 | 151 | 23 |
| Total | 100 | 800 | 179 | 621 | 85 |

Frontend population narrative assertion: 1 passed, 0 failed, 0 skipped. Includes 27 resource-count-only counterpoints that remain neutral, factual overdue/late wording and no jargon/guaranteed outcomes. Maximum raw-score reconstruction error across advisors: 4.44e-16. All four academic fingerprints before/after equal 7aa14cfe2e488d1c6de389d2eec6c686b60f632d31a0e64e3a6ca0b35f885d7c. These are software consistency checks, not predictive accuracy or intervention effectiveness.

## Regression evidence and boundaries

- Existing model provisioning tests: 6 passed.
- New reference provisioning/fail-closed tests: 7 passed (including matrix/config/provenance rejection, unexpected ZIP paths, tamper/overwrite refusal and no invalid-reference fallback).
- Existing ML suite: 52 passed. Training tests fit only temporary toy fixtures; the frozen research model was not retrained and the consumed holdout was not reevaluated.
- Existing optional-explanation failure tests: 3 passed.
- Clean-file-layout real inference/SHAP smoke: passed.
- Four-advisor population audit and frontend narrative assertion: passed as above.
- pip check: no broken requirements.

No complete latest-main regression suite, fresh-machine dependency installation or new visual review was run in this handoff iteration. The full-population audit assumes complete synthetic coverage at the fixed demo date; separate missing-coverage and authorization tests remain required acceptance gates. Keep source/artifact packages, generated JSON, model binaries and local environment files out of Git. Share only the reviewed source through the team's normal review process and trusted artifact packages separately.


## Fresh-environment and full regression checkpoint - November 14, 2026

Created `ml/outputs/handoff-venv-v1` with Python 3.13.14 and `include-system-site-packages = false`. Installed dependencies successfully using the combined candidate's backend requirements plus `ml/requirements-shap.txt`. No existing environment or application dependency pins were changed.

Important distinction: the original standalone `backend/requirements-research-demo.txt` pins SQLAlchemy 2.1.1, psycopg 3.3.8 and tzdata 2026.6. The pinned combined candidate requires SQLAlchemy 2.1.4, psycopg 3.3.6 and tzdata 2026.5. Do not combine these two backend manifests in a single install. For the reviewed combined candidate, the successfully tested setup is:

```powershell
python -m venv ml/outputs/handoff-venv-new
$python = '.\ml\outputs\handoff-venv-new\Scripts\python.exe'
$snapshot = 'ml/outputs/main-integration/team-review-9dba938-a0c1930'
& $python -m pip install -r "$snapshot/backend/requirements.txt" -r ml/requirements-shap.txt
& $python -m pip check
& $python tools/verify_clean_ml_handoff.py --output ml/outputs/handoff-check-fresh-new --model-bundle ml/outputs/handoff/acadmate-frozen-artifacts-v1.zip --reference-bundle ml/outputs/handoff/acadmate-explanation-references-v1.zip
```

Use a new destination for each venv/layout check and the supplied trusted package locations on a teammate's computer. The export must already be prepared from the reviewed pinned sources. When integrating into a normal team checkout, use that candidate's reviewed backend requirements, not the local ignored export path.

Results in this new environment:

- `pip check`: no broken requirements.
- Fresh source/artifact layout with actual frozen inference and SHAP: passed. No original OULAD tables copied, no model/calibrator fit, prediction 0.3783828964249184 unchanged. Evidence layout: ml/outputs/handoff-check-fresh-env-v1/.
- Full combined-candidate backend suite: **418 passed, 0 failed, 0 errors, 0 skipped**, 116.70 seconds. RUN_TEAM_RISK_SMOKE=true and RUN_RESEARCH_ARTIFACT_SMOKE=true. Only the guarded `acadmate_risk_demo_main_sprint2_test` database was rebuilt; no working demo or shared schema was changed. JUnit evidence: ml/outputs/handoff-check-fresh-env-v1/backend-results.xml.
- ML regressions: **52 passed**. Provisioning: **13 passed**. Optional explanation-failure regressions: **3 passed**. Toy-fixture training inside existing tests does not retrain the frozen model or reevaluate the original final holdout.
- Frontend suite: **13 passed, 0 failed, 1 skipped**. The skipped case targets the older standalone live demo on 5175, which was not started. The current combined app live panel through 5179 passed, including automatic inference for Santos's eight enrollments. Production build passed; existing >500 kB bundle warning remains.

The frontend run initially exposed an old hardcoded Amara identity and duplicate React installation in the test harness. `main-research-risk.test.js` now loads React/ReactDOM from the same candidate app as Vite, and accepts explicit expected identity via MAIN_DEMO_STUDENT_ID/MAIN_DEMO_STUDENT_NAME. Identity assertions remain strict. The combined test requires VITE_API_URL=/api/v1; otherwise Vite's test runtime defaults to /api and calls the wrong route. No production component was modified to accommodate the tests.

Reproduce the frontend suite from repository root while the combined local app is running:

```powershell
$env:ACADMATE_MAIN_SNAPSHOT = Join-Path $PWD 'ml/outputs/main-integration/team-review-9dba938-a0c1930'
$env:ACADMATE_EXPECT_DEGREE_PROGRESS = 'true'
$env:ACADMATE_ADVISOR_AUDIT_DIR = Join-Path $PWD 'ml/outputs/population-narrative-check-v1'
$env:RUN_MAIN_RISK_UI_TEST = 'true'
$env:MAIN_RISK_FRONTEND_URL = 'http://127.0.0.1:5179'
$env:MAIN_DEMO_EMAIL = 'sarah.smith@pac.edu'
$env:MAIN_DEMO_PASSWORD = 'Acadmate!2026' # Existing public synthetic-demo password only
$env:MAIN_DEMO_STUDENT_ID = '101'
$env:MAIN_DEMO_STUDENT_NAME = 'Santos Shel'
$env:VITE_API_URL = '/api/v1'
node --test frontend/tests/*.test.js
npm.cmd --prefix ml/outputs/main-integration/team-review-9dba938-a0c1930/frontend run build
```

Create fresh population audit inputs first if that directory is absent, using the earlier runner command. These synthetic login details must never be used for institutional deployment. The tests verify the named dataset; they do not rename Amara or change the original fixture identity.

The checkpoint closes fresh-local-environment setup and full candidate backend regression gates. Teammate machine confirmation, exact final submission source/dataset agreement and product-owner acceptance remain separate. No commit, push, merge or shared database operation occurred.
