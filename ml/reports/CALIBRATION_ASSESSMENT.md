# Calibration assessment — 2026-10-29

Branch: feature/academic-risk-prediction. All 28 automated ML tests pass. Calibration-fit and assessment groups share zero students. No final test feature/label files were accessed and no base models were refitted.

## Design

Keep the selected training-fitted logistic-regression pipeline fixed. Assign validation students by SHA-256 of a versioned student-ID string: 3,774 students (118,672 snapshots) fit the calibration maps; 3,761 students (117,881 snapshots) assess them. Assignment is independent of outcomes and stable across every course/week of each student. Both groups contain both target classes. Fit weights give each enrollment equal total influence, normalized for sigmoid regularization.

Compare two predefined maps with the uncalibrated model on the same assessment rows: logistic sigmoid on clipped base log-odds (C=1e6), and isotonic regression. No threshold tuning occurs. Per-week scores use one vote per active enrollment; pooled scores use inverse retained-snapshot enrollment weights.

This is retrospective, not prospective: both groups belong to 2013J, and calibration-fit final outcomes would be unavailable during early assessment weeks. The base classifier was also selected on full validation, including these assessment students. Therefore the group separation prevents fitting calibrators on their assessment labels, but does not make this an unbiased final model-selection evaluation. Freeze any eventual setup using only validation, then assess the later reserved test cohort under the documented chronology assumptions.

## Held-out calibration assessment results

| Method | Enrollment-balanced Brier (lower better) | AP | ROC-AUC | Precision at 0.5 | Recall at 0.5 |
|---|---:|---:|---:|---:|---:|
| Uncalibrated | 0.15245 | 0.84356 | 0.85731 | 0.73555 | 0.73246 |
| Sigmoid | 0.14812 | 0.84356 | 0.85731 | 0.82163 | 0.61111 |
| Isotonic | 0.14767 | 0.83908 | 0.85722 | 0.81022 | 0.62696 |

Isotonic has the lowest diagnostic Brier score, narrowly ahead of sigmoid; no uncertainty interval for that difference was computed. Brier loss reflects both calibration and discrimination, so it alone does not prove better calibration. Inspect week-specific observed rates and reliability bins. The positive sigmoid slope (0.93593) preserves the base ranking and AP/AUC on this cohort. Isotonic introduces tied scores, changing ranking metrics slightly.

These metrics use a subset of validation, so compare methods within this table, not directly against full-validation AP from earlier reports.

## Day 28: remaining early-course problem

Assessment cohort: 3,759 active enrollment rows, observed adverse-outcome rate 0.42298.

| Method | Mean predicted risk | Brier | AP | Recall at 0.5 |
|---|---:|---:|---:|---:|
| Uncalibrated | 0.62119 | 0.27171 | 0.61016 | 0.76667 |
| Sigmoid | 0.51700 | 0.24150 | 0.61016 | 0.55849 |
| Isotonic | 0.52402 | 0.24035 | 0.60205 | 0.58428 |

Both maps reduce aggregate overestimation and Brier loss, but predicted mean risk remains roughly 9–10 percentage points too high. Sigmoid cannot improve the underlying early discrimination; it changes probability interpretation and which rows cross 0.5. The recall decline is a threshold effect that must be reviewed before any outreach policy. Do not interpret the lower Brier score as intervention effectiveness.

At day 56 the observed rate is 0.40743; mean predictions are 0.54675 uncalibrated, 0.44893 sigmoid and 0.45486 isotonic. Improvements vary with week. Pooled calibration does not guarantee weekly calibration.

## Recommendation and remaining decisions

Keep both assessment results as research evidence. Sigmoid is a reasonable provisional candidate because it is simple and preserves the ranking, while isotonic's slightly better Brier loss has not been shown to be a stable advantage. No method has been frozen or adopted automatically. Do not retrain on the test set or tune thresholds against it.

Before final testing, specify whether the primary objective is ranking/outreach capacity or absolute probabilities, review the remaining early-week overestimation, and freeze the base-model hash, calibration-map hash, feature schema, reporting weights, threshold/capacity scenarios and final test procedure. If additional calibration variants are explored, label them as validation-driven development; do not claim an untouched calibration assessment thereafter. Real production still needs verified outcome/grade availability and Brightspace field mapping.

## Artifacts and checks

Local ignored outputs: ml/outputs/calibration-v1/calibration_assessment.json and calibration_maps.joblib. The JSON records input/model hashes, student-group counts, pooled and per-week metrics, reliability bins, and assumptions. Existing models and datasets are unchanged.

Tests cover deterministic outcome-independent grouping, numerical clipping, class-presence rejection, no base-model refit, no test directory requirement, and no overwrite of outputs. A small fixture initially lacked both classes in each hash group; it was corrected while retaining the fail-closed class check. All 28 tests pass after correction.

Method reference: https://scikit-learn.org/stable/modules/calibration.html . No backend code, original notebooks, academic records or database was changed. Nothing was committed, pushed, merged or imported.
