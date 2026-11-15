# SHAP stage-reference and advisor integration

Status: working local research integration. No frozen model, calibration, source-hash configuration, academic records, database schema, commit, push or merge changed. Earlier day-28 prototype results remain preserved; this document records the next stage.

## Explicit research reference policy

Policy ID: preceding_weekly_training_checkpoint_v1.

For assessment day d >= 7, the reference is 7 * floor(d / 7). Thus day 38 uses original day-35 training snapshots; day 41 also uses day 35; day 42 uses day 42. The reference is never later than the assessment and is at most six course days earlier. No interpolation, future observations, invented student values, validation/test outcomes, or new academic policy is introduced.

Select 128 original training rows by outcome-independent SHA256 priority, seed 42. Hash-check their training source, split manifest and baseline report against frozen provenance. Cache the verified background by reference day, with read-only matrices. Report its policy, requested day, reference day, sample count, training hash and selection hash alongside every available explanation.

This is a research explanation reference convention, not a claim that the earlier training population is equivalent to AcadMate students. Correlated features, early-course calibration limitations and synthetic domain transfer remain limitations. A mathematically additive explanation does not validate prediction accuracy or causality.

The original exact-day standalone prototype remains strict by default. The new main adapter explicitly supplies reference-policy metadata to permit a declared preceding-week reference; unsupported or missing references are not silently substituted.

## Audit results

Scored explanations: **685** over 15 stages and 46 main enrollments. Five ended-course cases at day 84 were unscored and unexplained. All scored cases passed SHAP additivity, missing-indicator grouping against independent raw-feature substitution, and calibrated probability reconstruction under both seed-42 and seed-43 backgrounds. Predictions did not change when backgrounds changed.

Maximum raw-score reconstruction error: 1.33e-15. Maximum calibrated probability error: 4.44e-16.

| Assessment day | Reference day | Explained | Unavailable | Mean top-3 overlap across backgrounds |
|---|---|---|---|---|
| 7 | 7 | 46 | 0 | 92.8% |
| 8 | 7 | 46 | 0 | 95.7% |
| 13 | 7 | 46 | 0 | 97.8% |
| 14 | 14 | 46 | 0 | 97.8% |
| 20 | 14 | 46 | 0 | 99.3% |
| 21 | 21 | 46 | 0 | 92.8% |
| 27 | 21 | 46 | 0 | 96.4% |
| 28 | 28 | 46 | 0 | 95.7% |
| 34 | 28 | 46 | 0 | 97.8% |
| 35 | 35 | 46 | 0 | 92.0% |
| 38 | 35 | 46 | 0 | 95.7% |
| 41 | 35 | 46 | 0 | 97.1% |
| 42 | 42 | 46 | 0 | 94.9% |
| 56 | 56 | 46 | 0 | 90.6% |
| 84 | 84 | 41 | 5 | 87.0% |

These overlap measurements describe sensitivity to the reference sample, not explanation correctness or an accuracy gate. No reference was chosen to improve a holdout metric. Mathematical invariants are also checked when each explanation is generated; the cohort audit covers the listed stages, not every possible institutional calendar.

## Optional API contract

Existing authenticated main-only route:

GET /api/v1/advisor/research/enrollments/{enrollment_id}/risk-assessment?cutoff=...&include_explanation=true

Without include_explanation=true, the prior response shape is preserved. The original fixed research endpoint is untouched. All role and assignment checks execute before extraction/explanation. No additional API path is introduced.

For a scored assessment, explanation contains:

- status=available; reason=null.
- explained_output=raw_logistic_log_odds; target=failure_or_withdrawal.
- method and SHAP version.
- baseline_raw_log_odds, raw_log_odds, reconstructed_raw_log_odds, reconstructed_calibrated_probability.
- background_reference: source, policy, prediction_day, reference_day, reference_age_days, actual_size, seed, training_features_sha256 and selected_rows_sha256.
- All 16 grouped contributions: feature, original input_value (nullable), raw_log_odds_contribution, direction and missing-indicator inclusion.
- ranked_features and research limitations.

The contributions add to the **raw score**, not to the displayed calibrated probability. The unchanged logistic probability, clipped logit and frozen sigmoid map are applied separately. Positive/negative values describe raw-score changes relative to the reference, not effects of student interventions.

If SHAP is not installed, a reference cannot be verified, or explanation checks fail, the endpoint still returns the valid scored assessment with explanation.status=unavailable and a safe generic reason. An unscored enrollment never invokes SHAP and receives an unavailable explanation. Internal paths/errors are logged only on the server. Missing model artifacts still prevent the underlying prediction normally; that separate case remains HTTP 503.

## Advisor presentation

The main-only panel requests explanations explicitly and displays a collapsed **How the model scored this course** section for scored results. It shows:

- Largest contributors to higher and lower raw model scores, using readable feature names.
- Signed log-odds values, never percentages for contributions.
- Assessment/reference day and sample count.
- Explicit warnings against causal/action/percentage-point interpretations.
- All 16 contributions and baseline/raw score in an advanced disclosure.

The existing descriptive evidence/coverage section is separate. Explanation failure leaves the probability and evidence intact. No risk bands, automatic alerts, student-facing predictions or model retraining were added.

## Actual verification

- ML suite: **52 passed** (41 existing, nine prototype, two stage-reference tests).
- Backend suite in original inference environment: **31 passed**, including three new optional-explanation failure tests.
- Main authenticated API: **44 authorized explanations** verified against unchanged scores, **94 cross-assignment denials**, student/admin denials, explicit day-38/reference-35 verification and simulated reference failure preserving HTTP 200 and probability. Two unassigned enrollments remain inaccessible to advisors.
- Live React/JSDOM through main Vite proxy, real authentication, PostgreSQL and frozen model: **2 passed**. Covers selected-date and replay references, raw-score wording, zero versus missing evidence, partial request failure and unavailable explanation retaining the score.
- Main frontend production build: passed, with existing chunk-size warning.
- Isolated main dependency check and frozen artifact/smoke verification: passed. Original 20014 fixture remains 0.3783828964249184; 20044 remains unavailable/null.
- Final manual Chrome inspection was interrupted by repeated concurrent-user-input detection. The new explanation panel is verified by live DOM integration, but its new expanded layout still needs a manual browser check. The earlier panel's desktop review is recorded separately in MAIN_RISK_INTEGRATION.md.

## Files and reproducible commands

New backend layer: backend/risk_mvp/main_explanations.py. Updated main-only router, panel, ML explainer, ML/backend/component tests and main verification tool. New read-only cohort audit: tools/audit_shap_stages.py. No generated records or environment files belong in Git.

Install the optional requirements in the isolated MAIN environment to enable the panel (never alter the original research environment just to test SHAP):

```powershell
$repo = 'C:\Users\nhesv\Documents\AcadMate-Team'
Set-Location $repo
$snapshot = Join-Path $repo 'ml\outputs\main-integration\8c4b0843368b'
$python = Join-Path $snapshot '.venv\Scripts\python.exe'
& $python -m pip install -r ml/requirements-shap.txt
& $python tools/prepare_main_risk_demo.py frontend --snapshot $snapshot
& $python tools/verify_main_risk_demo.py --snapshot $snapshot --with-explanations
```

Restart the owned loopback API with MAIN_RISK_INTEGRATION.md's commands after code/dependency changes. Open http://127.0.0.1:5177/advisor/advisees/101, click Assess all enrollments, then open How the model scored this course. For the default cutoff, the assessment is day 38 and the reference is day 35.

Reproduce numerical auditing with a NEW output filename:

```powershell
$env:PYTHONPATH = "$repo\backend;$repo\ml\src"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OMP_NUM_THREADS = '2'
$shapPython = Join-Path $repo 'ml\outputs\shap-prototype-v1\.venv\Scripts\python.exe'
& $shapPython -m unittest discover -s ml/tests -v
& $shapPython tools/audit_shap_stages.py --snapshot $snapshot --output ml/outputs/shap-prototype-v1/stage-validation-new.json
```

## Handoff limitation

The original two-file model ZIP does **not** include explanation backgrounds. A teammate currently needs the hash-matching original training feature file, split manifest and baseline report in the documented ignored output paths to build references. Never put the raw training dataset into Git merely to enable explanations. Without those sources the score still works and the explanation is safely unavailable. Packaging a small verified, de-identified derived reference bundle is a separate handoff improvement before team-wide rollout.

Manual visual review, team review of the reference convention and eventual reference provisioning remain open. This local implementation is not a production deployment or proof of institutional predictive validity.
