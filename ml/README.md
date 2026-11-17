# Weekly LMS risk research pipeline

Read-only source: original OULAD ZIP. Standard-library Python 3.11+ only; no database, downloads, extraction, or external dependencies. Existing notebooks and academic CSVs are not modified.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m unittest discover -s ml/tests -v
.\.venv\Scripts\python.exe -m acadmate_ml.features --source C:\Users\nhesv\Downloads\OULAD.zip --output ml/outputs/oulad-weekly-v1
```

Choose a new output directory for every run; existing directories are never overwritten. Outputs are ignored by Git. The ZIP is streamed directly; daily click aggregates are retained in memory. Allow time/memory for the 10.6 million activity records.

Outputs: features.csv (identifiers plus as-of features), labels.csv (separate final outcomes), manifest.json (source hash, row counts, exclusions, feature list and limitations). Missing numeric values are empty CSV cells. Scores, GPA, demographic attributes and final outcomes never enter the feature matrix. Zero activity is an observation under the historical dataset completeness assumption, not proof that an LMS feed worked. A missing required CSV fails the build rather than fabricating zeros.

Weekly days begin at 7 and stop before the course end; only registered, not-yet-unregistered enrollments are included. The feature-building command performs no train/test split or model training; use the separate partition stage below. Partition enrollments chronologically with student-disjoint evaluation before training, and preserve all snapshots of each enrollment in its partition. This builder's all-cohort output is exploratory, not a ready-made random-split training set.

See PREDICTION_FEATURE_CONTRACT.md for definitions, score availability restrictions, and proposed Brightspace simulation scope. This implementation adds the first feature-building stage; chronological split construction is now available separately; full model evaluation remains a subsequent task.

## Chronological partitions

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.splits --source C:\Users\nhesv\Downloads\OULAD.zip --snapshots ml/outputs/oulad-weekly-v1 --output ml/outputs/oulad-splits-v1
```

This stage assigns 2013B to training, 2013J to validation, and 2014J to testing; 2014B is intentionally unused. Earlier cohorts own repeated student IDs, which are excluded from later partitions. Month-bound chronology guards delay validation until training outcomes are assumed mature under a course-end proxy. Actual final-label availability timestamps are unknown. See reports/CHRONOLOGICAL_SPLIT_VALIDATION.md for counts, assumptions, and module coverage limitations. No model is trained by this command. Keep the test cohort reserved for final evaluation.

## Baseline training (validation only)

Install ml/requirements.txt in the local virtual environment, then run:

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
$env:OMP_NUM_THREADS = '2'
.\.venv\Scripts\python.exe -m acadmate_ml.train --splits ml/outputs/oulad-splits-v1 --output ml/outputs/baselines-v1
```

This command opens only train/validation feature and label files plus the split manifest. It never loads test features or labels. It fits median imputation with missing indicators and optional scaling on training only. All four models receive equal total weight per training enrollment, normalized to mean snapshot weight one. No extra class weighting is applied in this baseline comparison.

Candidates are a prior-probability dummy, regularized logistic regression, random forest, and histogram gradient boosting (the histogram variant replaces classical GradientBoostingClassifier for this larger snapshot table). Early stopping is disabled for histogram boosting to avoid an internal random snapshot validation split. Model selection uses enrollment-balanced validation average precision. Threshold 0.5 is a diagnostic, not an approved risk band; no threshold or probability calibrator is fitted. Metrics include snapshot-weighted and enrollment-balanced scores, calibration bins, week/module coverage breakdowns, failure/withdrawal recall, and hypothetical 10%/20% student outreach. Outreach deduplicates a student within a relative-course-week cohort using maximum active-course probability; actual calendar-week scheduling still needs verified start dates. Ties use student IDs, not outcomes.

Ignored local outputs contain validation_metrics.json and fitted .joblib pipelines. Load only artifacts produced by this trusted local run; they are research models, not production-approved or Brightspace-validated. A failed run may leave partial output; use a new output path on retry. Do not repeatedly inspect test performance while choosing settings. Grouped uncertainty estimates, independent calibration, and final test evaluation remain separate follow-up tasks.

Implementation references: https://scikit-learn.org/stable/modules/generated/sklearn.impute.SimpleImputer.html and https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html .

## Weekly review and student-grouped uncertainty

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.uncertainty --splits ml/outputs/oulad-splits-v1 --artifacts ml/outputs/baselines-v1 --output ml/outputs/weekly-uncertainty-v1 --replicates 300
```

This analysis reloads trusted local fitted models and validation files only, verifies provenance, and does not refit models or load test rows. With seed 42 it resamples unique validation student IDs with replacement, preserving every sampled student's courses and snapshots together. The same draws are used for every model, allowing paired AP differences. Pooled metrics retain inverse-snapshot enrollment weights. Within-week metrics use equal enrollment weights, so their prevalence and performance differ from earlier globally weighted week breakdowns. AP is compared with the actual weekly positive prevalence; AUC, Brier, diagnostic threshold metrics, mean predicted risk, and sample counts are also saved.

The 95% intervals are percentile, pointwise intervals conditional on the fitted models and observed cohort. They do not quantify retraining or institutional variation, correct prior model-selection bias, or provide simultaneous multiple-comparison guarantees. Single-class bootstrap draws are omitted for AP/AUC and valid replicate counts are recorded. Generated JSON stays in ignored local outputs; the reviewed summary is under reports/.

## Calibration assessment (validation students only)

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.calibrate --splits ml/outputs/oulad-splits-v1 --artifacts ml/outputs/baselines-v1 --output ml/outputs/calibration-v1
```

A stable SHA-256 student-ID assignment creates disjoint calibration-fit and assessment groups; all courses/weeks of a student stay together. Two predefined maps are fit on the fit group only: logistic sigmoid on clipped base log-odds (C=1e6) and isotonic regression. Both use enrollment-balanced weights. Assess uncalibrated and mapped predictions on identical held-out students. No base-model refitting, threshold tuning, test-file access or final method freeze occurs. The lowest assessment Brier score is a diagnostic ranking, not automatic production adoption.

This is retrospective same-presentation calibration: fit-group final outcomes would not be available at early assessment snapshots. The base model was also selected using full validation, so the assessment is not independent of base-model selection. Do not claim prospective or unbiased final performance. Real chronology must be checked when the final setup is frozen for later-cohort testing. Brier score combines calibration and discrimination; inspect reliability bins and week-specific mean risk as well. Reference: https://scikit-learn.org/stable/modules/calibration.html .

## Frozen final test experiment

The specification is saved at configs/FINAL_EXPERIMENT_V1.json. It was created before opening the reserved test feature/label rows, and pins artifact, source-code, split-manifest and selection-report hashes. Primary: existing logistic regression plus the existing sigmoid map. Predefined comparison: identical base model uncalibrated. Diagnostic threshold: 0.5. No refit or tuning.

The final evaluation command was executed once for this real cohort:

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.evaluate evaluate --splits ml/outputs/oulad-splits-v1 --models ml/outputs/baselines-v1 --calibration ml/outputs/calibration-v1 --freeze ml/configs/FINAL_EXPERIMENT_V1.json --output ml/outputs/final-test-v1
```

Do not rerun with new settings to select a model against this cohort. The evaluator refuses an existing destination, validates frozen hashes before loading test rows, records a start marker before access, and records completion and metrics hashes. A failed attempt must be investigated and disclosed, not silently bypassed with another output name. The local test cohort is no longer untouched after this experiment. Historical validation reports describe the state at their creation.

Predefined reporting: enrollment-balanced pooled and snapshot-weighted metrics; equal-enrollment weekly metrics; per-module and familiar/unseen module metrics; separate failure/withdrawal recall; diagnostic 0.5 threshold; hypothetical 10%/20% student outreach; 300 paired student-cluster bootstrap replicates with seed 42 for pooled AP/AUC and the calibrated-minus-uncalibrated Brier difference. No isotonic or alternate base models are evaluated on test. Model artifacts remain ignored local files.

## Synthetic LMS MVP input

Brightspace remains the intended architectural source. The MVP exercises a platform-neutral simulated input using separate event fixtures linked to existing academic IDs, with no live connector. See SIMULATED_LMS_INPUT_CONTRACT.md and fixtures/simulated_lms/events.json. Run `python -m acadmate_ml.simulated_lms` with the documented input/academic/output arguments to validate the linkages and produce the existing 16 as-of features. This stage does not run model inference or modify any original CSV, model, backend or historical evaluation output.

## Local research-only inference demo

The fixture flow now continues from ready features to the frozen model using `python -m acadmate_ml.predict`. See reports/LOCAL_INFERENCE_DEMO.md for the exact command, outputs and limitations. Unavailable records remain unscored; no automatic alerts or risk bands are introduced. Frozen artifact/code hashes are checked before inference. The command loads trusted local joblib artifacts only, does not refit, and never reads held-out evaluation rows. Generated predictions remain ignored by Git.
