# Final frozen test evaluation — 2026-10-30

Branch: feature/academic-risk-prediction. Status: completed once on the reserved 2014J test cohort. The cohort is now consumed for final evaluation; it must not be reused as an untouched holdout for further model selection.

## Frozen setup and verification

Primary: existing training-fitted logistic regression plus the existing sigmoid calibration map. Predefined comparison: the same model uncalibrated. No model or calibrator was refitted, no threshold was tuned, and no alternate models or isotonic map were assessed on test.

The experiment was frozen at 2026-10-30 13:38:14 UTC before test feature/label rows were read. The specification is ml/configs/FINAL_EXPERIMENT_V1.json and pins feature order, model/map/report/split-manifest/source-code hashes, threshold 0.5, evaluation weights, bootstrap seed 42 and 300 replicates. Freeze/evaluation safeguards passed along with all previous ML tests: 31 unique automated tests passed. Start/completion markers and metrics hashes exist in ignored local output ml/outputs/final-test-v1/.

Test coverage: 8,846 students, 9,269 enrollments, 284,765 weekly snapshots. Actual student overlap with training/validation is zero. IDs are grouping metadata, not predictors. No backend or source data was modified.

## Primary and predefined comparison

Pooled metrics weight each enrollment equally across its retained snapshots. They are not independent snapshot observations or early-week-only performance. Positive prevalence under this weighting is 0.44892.

| Method | AP | ROC-AUC | Brier loss | Precision at 0.5 | Recall at 0.5 | F1 at 0.5 |
|---|---:|---:|---:|---:|---:|---:|
| Sigmoid primary | 0.83876 | 0.85348 | 0.15386 | 0.77148 | 0.71744 | 0.74348 |
| Uncalibrated comparison | 0.83876 | 0.85348 | 0.16225 | 0.70058 | 0.81525 | 0.75358 |

Student-cluster percentile 95% pointwise intervals for the primary model: AP 0.83017–0.84767; ROC-AUC 0.84728–0.85936. Same student draws preserve all courses/snapshots and are paired across the two methods. Brier difference (primary minus comparison) is -0.00839, interval -0.00984 to -0.00694, supporting lower Brier loss on this fixed cohort. Brier includes calibration and discrimination, not calibration alone. Intervals are conditional on fixed models and this cohort, do not cover retraining uncertainty, and are not corrected for multiple comparisons.

The positive sigmoid map preserves ranking, hence identical AP/AUC. It improves pooled probability loss and precision at 0.5 while reducing recall. The diagnostic threshold is not an approved advisor-alert policy, and the comparison's higher F1 does not change the frozen primary model.

Primary weighted mean predicted risk is 0.45266 versus observed 0.44892. Similar aggregate means do not imply calibration within each week or module.

## Weekly primary results

Within each course-relative week, every active enrollment gets one vote. Multiple enrollments of one student remain separate prediction rows. Later-week populations differ because of withdrawals and course lengths; stage differences are not a controlled timing experiment.

| Day | Enrollment rows | Observed rate | Mean predicted risk | AP | ROC-AUC | Brier |
|---|---:|---:|---:|---:|---:|---:|
| 7 | 9,227 | 0.44857 | 0.64340 | 0.60526 | 0.67179 | 0.26578 |
| 14 | 8,488 | 0.39951 | 0.61506 | 0.55807 | 0.66235 | 0.26947 |
| 28 | 8,388 | 0.39115 | 0.53355 | 0.59799 | 0.66905 | 0.24077 |
| 56 | 8,106 | 0.36985 | 0.46099 | 0.67131 | 0.74701 | 0.19800 |
| 112 | 7,632 | 0.33071 | 0.38951 | 0.72785 | 0.79195 | 0.16160 |
| 224 | 6,994 | 0.26966 | 0.28340 | 0.84922 | 0.89619 | 0.09054 |

Early overestimation remains material. At day 7 mean risk is 0.64340 against observed 0.44857; at day 28 it is 0.53355 against 0.39115. Validation had no days 7–21, so these first test findings must be reported as a limitation rather than used to tune this experiment. Ranking is modest early and generally stronger later. Pooled AP 0.83876 must not be advertised as day-7 performance or proof of useful intervention outcomes.

## Course-level primary results

Metrics below are enrollment-balanced within module. Prevalences differ, so AP comparisons are descriptive rather than controlled module effects.

| Module | AP | ROC-AUC | Brier |
|---|---:|---:|---:|
| AAA | 0.60477 | 0.77405 | 0.16345 |
| BBB | 0.84693 | 0.86337 | 0.14624 |
| CCC | 0.82860 | 0.80434 | 0.17889 |
| DDD | 0.84283 | 0.83637 | 0.17489 |
| EEE | 0.86276 | 0.89789 | 0.12848 |
| FFF | 0.90441 | 0.90807 | 0.13033 |
| GGG | 0.81016 | 0.85163 | 0.16767 |

Familiar training modules (BBB, DDD, FFF) pooled AP is 0.86112; unseen modules (AAA, CCC, EEE, GGG) pooled AP is 0.82142. Module composition and temporal differences coexist. This does not establish transfer to a new institution or to Brightspace.

Primary recall at 0.5 differs by eventual outcome: Fail 0.63005; Withdrawn 0.78119. The combined target therefore has uneven coverage. Full pooled/snapshot-weighted results, weekly and module tables, calibration bins, failure/withdrawal recall and predefined hypothetical 10%/20% student outreach scenarios are in ml/outputs/final-test-v1/final_test_metrics.json. Outreach cohorts use relative course weeks and deduplicate students; actual calendar-week advisor scheduling still needs verified course dates.

## Research conclusion and limits

The frozen LMS research pipeline demonstrates predictive signal and improved pooled Brier loss from sigmoid mapping on a later student-disjoint cohort. It remains an offline prototype: early probabilities overestimate risk, course coverage varies, the training set includes only three modules, and no advisor-capacity or intervention-benefit policy is validated.

Chronology still assumes outcome availability by a conservative course-end proxy rather than a verified final-result release timestamp. Source event-day availability is assumed; delivery latency is unknown. Score/GPA features remain excluded. Brightspace access and event-field equivalence have not been verified. This is not deployment approval or evidence that the model works on actual AcadMate students.

Next work can package these fixed findings and demonstrate a simulated LMS adapter/inference flow with explicit coverage and as-of metadata. Any model improvements motivated by these test findings are a new experiment requiring a new independent evaluation source or clearly labeled development evaluation; do not claim this test remains untouched.

All model, calibration and feature choices were retained after seeing results. No commit, push, merge, backend change or database import occurred. Original ZIP, notebooks, synthetic academic records, earlier feature/split outputs and fitted artifacts remain unchanged.
