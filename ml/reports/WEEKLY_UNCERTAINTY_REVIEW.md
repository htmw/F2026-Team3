# Weekly performance and uncertainty review — 2026-10-29

Branch: feature/academic-risk-prediction. All 25 automated ML tests pass. Analysis completed with 300 paired student-cluster bootstrap replicates, seed 42. Existing fitted models were reloaded without refitting; reserved test feature/label files were not accessed. Existing data and model outputs were not overwritten.

## Main finding

Retain logistic regression as the current research baseline, but do not describe its pooled AP of 0.838 as early-week performance. At day 28 its AP is 0.589 (95% pointwise interval 0.572–0.607) and AUC is 0.650 (0.637–0.661). There is signal above the 0.412 positive prevalence, but modest early discrimination and substantial probability overestimation. No intervention benefit or production readiness has been demonstrated.

## Weekly validation results for logistic regression

Unlike the earlier globally weighted week breakdowns, this table gives each active enrollment one vote within its week. These are course-relative weeks, not verified calendar-week cohorts. Multiple enrollments of the same student remain separate prediction rows; uncertainty resamples the student as one cluster.

| Snapshot day | Enrollment rows | Positive prevalence | AP (95% interval) | ROC-AUC | Mean predicted risk | Brier |
|---|---:|---:|---|---:|---:|---:|
| 28 | 7,536 | 0.412 | 0.589 (0.572–0.607) | 0.650 | 0.620 | 0.276 |
| 35 | 7,480 | 0.407 | 0.609 (0.592–0.628) | 0.689 | 0.592 | 0.253 |
| 56 | 7,325 | 0.395 | 0.681 (0.664–0.698) | 0.743 | 0.545 | 0.219 |
| 84 | 7,175 | 0.382 | 0.734 (0.719–0.750) | 0.779 | 0.606 | 0.231 |
| 112 | 6,946 | 0.362 | 0.787 (0.772–0.801) | 0.824 | 0.489 | 0.168 |
| 168 | 6,628 | 0.331 | 0.861 (0.849–0.873) | 0.887 | 0.378 | 0.109 |
| 224 | 6,434 | 0.311 | 0.894 (0.882–0.903) | 0.915 | 0.356 | 0.086 |
| 266 | 4,270 | 0.290 | 0.904 (0.891–0.917) | 0.920 | 0.415 | 0.098 |

All available snapshot days, ROC-AUC intervals and diagnostic threshold metrics are in the local JSON. Validation contains no days 7–21. AP's no-skill reference is the within-week positive prevalence, which changes with the cohort. Later weeks have different surviving enrollments, module coverage, more information and a shorter remaining horizon; this is not a controlled comparison of timing alone. Improvement is not monotonic in every metric.

At day 28, precision at diagnostic threshold 0.5 is 0.480 and recall is 0.766. Thus more than half of flagged enrollment rows do not have the combined final adverse outcome; this is not an approved outreach threshold. The day-28 Brier score 0.276 is worse than a descriptive constant equal to that week's observed prevalence (approximately 0.242). That reference is computed after seeing validation outcomes, not a deployable fitted baseline. It highlights calibration problems rather than establishing a new model.

## Pooled model uncertainty

Pooled AP uses inverse retained-snapshot weights so every enrollment has equal total weight. It differs from the within-week estimand above.

| Model | Pooled AP | 95% pointwise student-cluster interval |
|---|---:|---|
| Logistic regression | 0.8377 | 0.8273–0.8467 |
| Random forest | 0.8337 | 0.8234–0.8432 |
| Histogram gradient boosting | 0.8333 | 0.8232–0.8424 |
| Dummy prior | 0.4120 | 0.4015–0.4225 |

Paired AP differences use identical student resamples for both models; do not infer model differences from overlap of separate model intervals.

| Difference: logistic regression minus comparator | Estimate | 95% pointwise paired interval |
|---|---:|---|
| Random forest | 0.0040 | 0.0018–0.0059 |
| Histogram gradient boosting | 0.0045 | 0.0022–0.0066 |
| Dummy prior | 0.4257 | 0.4156–0.4367 |

Intervals above zero support a small conditional advantage on this observed validation cohort. They do not establish broad superiority or account for prior model selection on the same validation data. The practical benefit is small compared with the larger calibration and early-course limitations.

## Method and verification

Unique validation students are sampled with replacement; every course and snapshot of a sampled student receives the same multiplicity. The same draw is used for all models and weekly subsets. Cached score ordering and ties produce weighted AP/AUC matching scikit-learn in regression tests, including zero weights and tied predictions. Percentile endpoints use the 2.5th and 97.5th percentiles. Single-class draws are omitted for AP/AUC, with valid replicate counts saved. All reported full-run intervals have 300 valid draws.

Tests also verify deterministic student grouping, undefined single-class behavior, paired identical-score differences, no output overwrite, and analysis with no test files while any model refit is forced to fail. No new external dependencies were added. Source/model/input hashes are recorded in ml/outputs/weekly-uncertainty-v1/weekly_uncertainty.json, which is ignored by Git.

Limitations: only one validation presentation; no institution/course-level bootstrap; fixed trained models rather than retraining per draw; no multiple-comparison or winner-selection correction; pointwise intervals rather than simultaneous bands. Pooled evaluation weights depend on eventual snapshot counts and must not be interpreted as real-time week-specific prevalence. Source event-day availability and course-end final-label availability remain documented research assumptions.

## Next step

Keep logistic regression provisionally. Design independent calibration-fit and calibration-assessment groups within validation using student-disjoint groups, audit chronology, and explicitly report early-week calibration and discrimination. Do not fit and assess a calibrator on the same rows. Choose any threshold or outreach rule on validation only, then freeze the full setup before one final test evaluation. No calibrator, new thresholds, or test evaluation was introduced in this task.

Backend, original OULAD ZIP, research notebooks, synthetic academic CSVs, feature/split outputs and fitted baseline models remain unchanged. Nothing was committed, pushed, merged or imported into a database.
