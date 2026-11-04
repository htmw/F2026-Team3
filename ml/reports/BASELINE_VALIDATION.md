# Baseline training and validation — 2026-10-28

Branch: feature/academic-risk-prediction. All 20 automated ML tests pass. pip check reports no broken requirements. No test feature/label files were loaded; an end-to-end test also verifies that training succeeds with no test directory present.

## Experiment

Training: 126,402 snapshots from 4,362 enrollments (2013B). Validation: 236,553 snapshots from 7,539 enrollments (2013J), beginning at day 28. Predictors are the 16 approved engagement, submission and course-context features. Scores, grades, GPA, demographics and identity columns are excluded.

Every training enrollment receives equal total sample weight, normalized to mean snapshot weight one. Median imputation with missing indicators is fitted on training only; logistic regression also uses a training-fitted scaler. No extra class weighting, hyperparameter search, threshold tuning or probability calibration is performed. Fixed diagnostic threshold: 0.5. Selection criterion, specified in code before the run: highest enrollment-balanced validation average precision, with model-name tie breaking.

Histogram gradient boosting replaces classical GradientBoostingClassifier for this snapshot volume; internal early stopping is disabled to avoid a random snapshot validation split. Fixed seed: 42. Training CPU parallelism is limited to two threads.

## Validation results

These metrics weight each enrollment equally across its retained snapshots; they are not independent-student test results.

| Model | Average precision | ROC-AUC | Brier score | Precision at 0.5 | Recall at 0.5 | F1 at 0.5 |
|---|---:|---:|---:|---:|---:|---:|
| Dummy prior | 0.4120 | 0.5000 | 0.2539 | 0.4120 | 1.0000 | 0.5836 |
| Logistic regression | 0.8377 | 0.8579 | 0.1520 | 0.7270 | 0.7339 | 0.7304 |
| Random forest | 0.8337 | 0.8524 | 0.1601 | 0.6850 | 0.7681 | 0.7241 |
| Histogram gradient boosting | 0.8333 | 0.8519 | 0.1616 | 0.6851 | 0.7618 | 0.7214 |

Logistic regression ranks first under the chosen validation criterion. Its small AP advantage over the ensembles has not been assessed for statistical uncertainty. Random forest has higher recall at the fixed threshold; selection does not establish the best operational outreach policy.

The weighted positive prevalence is 0.4120. The dummy model learns its constant prior from training, not validation; at threshold 0.5 it flags all validation rows. AP is average precision, not trapezoidal PR-AUC.

## Interpretation and limitations

- Logistic regression AP is 0.8584 on familiar modules and 0.8058 on unseen modules. These populations have different prevalences; AP differences alone do not establish a course-generalization effect.
- Weighted recall at threshold 0.5 is 0.7527 for Fail and 0.7027 for Withdrawn. Outcomes are combined for fitting but reported separately.
- Probabilities tend to overestimate validation risk in the calibration bins. For example, the 0.5–0.6 bin has mean prediction 0.5471 versus observed rate 0.4579; the 0.8–0.9 bin has mean 0.8514 versus observed rate 0.7185. They are research scores, not calibrated operational probabilities.
- Performance varies across course weeks; pooled metrics mix stages with different remaining horizons. Week/module breakdowns are saved. Those breakdowns use the global enrollment-balancing weights, which depend on the number of retained snapshots; their weighted prevalence is not raw week-specific prevalence. Snapshot-weighted overall metrics are also saved.
- No validation data exists for days 7–21. Some evaluation courses are absent from training. Calendar chronology uses conservative month bounds and a course-end label-maturity proxy; actual final-outcome release dates remain unverified.
- Hypothetical 10%/20% outreach results deduplicate students within relative-course-week cohorts using maximum active-course probability. These are scenarios, not staffing assumptions or verified calendar-week advisor queues.
- Calibration is measured, not corrected. No student-group bootstrap intervals, independent calibration set, subgroup fairness evaluation, deployment validation, or final test evaluation has been performed.

## Reproducibility and artifacts

Python 3.13.14, numpy 2.5.4, scikit-learn 1.9.1. Exact dependencies are pinned in ml/requirements.txt. The command and definitions are in ml/README.md. Local ignored artifacts: ml/outputs/baselines-v1/validation_metrics.json and four fitted .joblib pipelines. Metrics include exact train/validation file hashes, split-manifest hash, feature list, model ranking, calibration bins, per-week/module scores, separate failure/withdrawal recall and hypothetical outreach metrics.

Original OULAD ZIP, existing feature/split outputs, research notebooks, backend and synthetic academic records are unchanged. Nothing was committed, pushed, merged or imported into a database.

Next: inspect week-specific behavior and calibration, add student-grouped uncertainty estimates, and freeze the selection/threshold/calibration policy before a single final test evaluation. Do not use test results for iterative model selection. A calibration extension needs independent chronological validation treatment; do not fit and assess a calibrator on the same rows.
