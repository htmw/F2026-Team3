# SHAP research prototype validation

Follow-up: stage-reference policy and optional advisor integration are now documented in [SHAP_STAGE_INTEGRATION.md](SHAP_STAGE_INTEGRATION.md). The results below preserve the original day-28 prototype checkpoint.

Status: numerically verified isolated prototype; not added to FastAPI or the advisor dashboard. Frozen model, calibration maps, configuration, historical results and existing serving environments are unchanged. No retraining, shared-schema changes, commit or push occurred.

## Scope and output meaning

The frozen pipeline has 16 original inputs, median imputation, four missing-value indicators, standard scaling and logistic regression: 20 transformed columns. SHAP 0.54.1 LinearExplainer with an Independent masker explains the classifier's **raw log-odds score**. Indicator contributions are summed into their originating feature, yielding 16 grouped contributions.

The expected raw score on the selected training background plus all contributions reconstructs the raw logistic decision score. This baseline is NOT average calibrated probability. The unchanged raw probability, clipped logit and frozen sigmoid calibration are applied separately to verify the actual displayed probability. Individual SHAP values are never described as additive percentage-point changes in calibrated probability. A toy extreme-score test explicitly checks the clipping case.

Independent masking can combine correlated features in unrealistic ways. These are model-behavior attributions relative to a particular background, not causal explanations or recommended student actions. The prototype does not establish predictive accuracy, fairness or clinical/academic decision validity.

Implementation rationale: [official LinearExplainer documentation](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html) and [Independent masker documentation](https://shap.readthedocs.io/en/latest/generated/shap.maskers.Independent.html).

## Background and data isolation

Background: 128 snapshots selected from 4,118 eligible **original training-only day-28** rows, using the smallest SHA256(seed:enrollment-key:snapshot-day) priorities. No outcome labels are consulted. Training features, split manifest and baseline report are checked against the frozen provenance before sampling. The masker retains all selected rows rather than silently subsampling.

Primary seed 42; sensitivity seed 43. Neither validation/test feature files, their labels nor the final holdout were opened by the prototype audit. Existing unit tests use temporary toy training/evaluation fixtures; they do not retrain or re-evaluate the frozen research experiment.

The audited cases comprise the three existing ready synthetic fixtures plus all 46 main-snapshot enrollments at their own **simulated day-28** cutoffs. The fourth original fixture remains unavailable and has no explanation. Main's academic snapshot fingerprint is checked before/after read-only extraction. This offline audit does not grant advisor access to the two unassigned enrollments.

## Actual results

- ML suite including explainability: **50 passed** (41 existing + nine new tests).
- Backend regression suite in the unchanged serving environment: **28 passed**, including actual artifacts and disposable PostgreSQL tests.
- Existing artifact verification/smoke: passed, with enrollment 20014 probability 0.3783828964249184 and enrollment 20044 unavailable/null.
- Isolated SHAP dependency check: passed.
- Actual audit: **49 scored explanations**, **1 unavailable case** with no explanation.
- Maximum raw-score reconstruction error: **8.88e-16**.
- Maximum grouped-contribution versus raw-feature substitution error: **1.33e-15**.
- Maximum calibrated-probability reconstruction error: **3.33e-16**.
- Second background also passed all numerical checks. Mean top-three feature overlap was **95.92%**; the baseline moved by **0.162645 log-odds**. Those are descriptive sensitivity results, not accuracy or explanation-certification metrics. Predictions stayed unchanged.
- Frozen artifact/config hashes and all original academic CSV hashes stayed identical.

Grouping was independently verified by replacing one original raw feature at a time across the background and recomputing the full pipeline decision score. This exercises imputation and missingness rather than simply comparing SHAP against the same coefficient formula. Class order, finite output, additivity and stage-matched background are checked. Tests also cover malformed inputs, all-unavailable operation without model loading, background tampering, deterministic selection, row-order invariance within floating-point tolerance, and output overwrite refusal.

## Example: synthetic main enrollment 308, day 28

Frozen calibrated probability: **0.316365**. Baseline raw score **0.404457**; actual raw score **-0.291828**.

| Input | Value at cutoff | Raw log-odds contribution |
|---|---|---|
| overdue_assessments | 1 | +0.454345 |
| late_submission_rate | 0.0 | -0.242874 |
| assessments_due | 4 | -0.186967 |
| course_progress | 0.23931623931623933 | -0.157337 |
| active_days_28d | 14 | -0.135058 |
| days_since_submission | 1 | -0.124958 |

This is a truncated ranking, so these six entries alone do not reconstruct the score. The JSON retains all 16 contributions. Positive values increase the raw score relative to this background; negative values decrease it. They do not mean that changing a student's behavior would cause the corresponding outcome change, and they are not probabilities.

## Files

- ml/src/acadmate_ml/explain.py — optional standalone explainer with trusted artifact loading and training-only background verification.
- ml/tests/test_explain.py — nine focused tests.
- ml/requirements-shap.txt — optional pinned dependencies, separate from serving requirements.
- tools/audit_shap_prototype.py — real-artifact, all-enrollment and background-sensitivity audit.
- ml/reports/SHAP_PROTOTYPE_VALIDATION.md — this report.

Generated JSON and the prototype environment are ignored under ml/outputs/shap-prototype-v1. Key outputs are audit/explanations.json, audit/background-sensitivity.json, audit/verification.json and fixture-explanations-verified.json. Existing files are never overwritten by rerun commands.

## Setup and reproduce

From the repository root, use a separate Python 3.13 environment. Create it only when absent:

```powershell
$python = '.\ml\outputs\shap-prototype-v1\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { py -3.13 -m venv ml/outputs/shap-prototype-v1/.venv }
& $python -m pip install -r backend/requirements-research-demo.txt -r ml/requirements-shap.txt
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OMP_NUM_THREADS = '2'
& $python -m unittest discover -s ml/tests -v
# Use NEW filenames/directories for each run:
& $python -m acadmate_ml.explain --output ml/outputs/shap-prototype-v1/fixture-new.json
# With the prepared isolated main database running, optional full local audit:
& $python tools/audit_shap_prototype.py --output ml/outputs/shap-prototype-v1/audit-new --main-snapshot ml/outputs/main-integration/8c4b0843368b
```

Verified optional versions: SHAP 0.54.1, pandas 2.3.3, python-dateutil 2.9.0.post0, slicer 0.0.8, tqdm 4.70.1, pytz 2026.6, six 1.17.0. The initially resolved pandas 3.1.1 build failed to import on this machine; the working pandas/dateutil versions are explicitly pinned. No Windows security controls were changed.

## Before dashboard integration

This audit validates day-28 explanations only. Main's default selected-date assessment is currently course day 38. Original training snapshots are weekly, so exact course-day-38 background sampling may be unavailable. We must explicitly choose and validate a same-week or other stage-matched reference policy before presenting explanations for arbitrary dates; do not silently substitute a reference or reuse day-28 explanations for a different cutoff.

Additional work: evaluate background sensitivity across supported weeks, preserve the explanation's background/version/unit provenance in a proposed API schema, maintain advisor assignment checks, never explain unavailable cases, and present raw-score contributions without causal or percentage-point claims. The existing evidence panel remains factual context, separate from SHAP. No dashboard/API changes are included in this prototype.
