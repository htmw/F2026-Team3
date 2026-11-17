# Local synthetic LMS inference demonstration — 2026-11-02

Branch: feature/academic-risk-prediction. All 41 ML tests pass. Three ready feature records were scored with the unchanged frozen logistic-regression pipeline and existing sigmoid map. The unavailable-feed record remains unscored.

| Enrollment | Case | Research-only output | Status |
|---|---|---:|---|
| 20014 | Steady participation | 0.37838 | scored_research_demo |
| 20024 | Recent activity gap | 0.84841 | scored_research_demo |
| 20034 | Confirmed zero activity | 0.97278 | scored_research_demo |
| 20044 | Activity feed unavailable | null | unavailable |

These are deterministic model outputs for hand-authored input cases, not validated probabilities for actual AcadMate students. The synthetic scenarios have no ground-truth risk labels. Differences between cases do not demonstrate causality or calibrated domain transfer. OULAD model accuracy cannot be inferred from this demonstration; early-course overestimation remains a known limitation. No risk bands, advisor alerts or automatic decisions are generated.

Before loading trusted local joblib artifacts, the CLI verifies frozen model/map hashes and frozen research-module hashes. Feature names/order, as-of consistency, finite numeric values and missing-feed states are checked. Only ready vectors are submitted for inference. All-unavailable input never calls the model. No retraining, recalibration, database call, live LMS access or real held-out test reevaluation occurs.

Output: ml/outputs/simulated-lms-v1/predictions.json (ignored by Git), containing per-record source/as-of identifiers, research-only warnings, model/map/freeze/input hashes and generation time. Original features remain unchanged. Existing output files are never overwritten.

## Reproduce with a new output filename

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.predict --input ml/outputs/simulated-lms-v1/features.json --model ml/outputs/baselines-v1/logistic_regression.joblib --calibration ml/outputs/calibration-v1/calibration_maps.joblib --freeze ml/configs/FINAL_EXPERIMENT_V1.json --output ml/outputs/simulated-lms-v1/predictions-new.json
```

Backend/frontend integration is not included in this step. Brightspace remains the intended architectural source; the MVP uses separate synthetic event fixtures. Original academic records, notebooks, model artifacts and frozen research modules are unchanged. Nothing was committed, pushed, merged or imported.
