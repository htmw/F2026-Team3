# AcadMate Sprint 2: prediction and feature contract

Status: working contract v0.3; updated with agreed prototype scope. Remaining production decisions require team review. This document defines the research prototype; it does not introduce a production API or change backend policy.

## Prediction objective

Predict the probability of unsuccessful completion (Fail or Withdrawn) for an ongoing student-course enrollment. Predictions refresh weekly and support advisor outreach. They are not a diagnosis, a causal explanation, or an automatic academic decision.

Unit: one student, module, presentation, and snapshot day. OULAD key: (id_student, code_module, code_presentation, snapshot_day). IDs identify rows and splits; they are not model inputs. This is course-level risk, not an overall student GPA or graduation prediction.

## Snapshot and label rules

- Use days relative to course start. Initial schedule: days 7, 14, 21, ... through the presentation's recorded length. A snapshot includes events through the end of that day. There is no fixed day-35 limit.
- Include students registered on or before the snapshot and not unregistered on or before it. Missing registration dates require a documented exclusion or sensitivity policy; never silently assume eligibility. Use studentRegistration for this selection.
- Do not score an enrollment already known to be completed or otherwise terminal. OULAD lacks a general completion-availability timestamp: use presentation length as an explicit research proxy for course end, document the limitation, and exclude the end-of-presentation snapshot. Production must use actual lifecycle events.
- Label 1 for final_result in {Fail, Withdrawn}; label 0 for {Pass, Distinction}. Reject unknown labels. A withdrawal already effective at the snapshot excludes that row, rather than becoming a prediction target.
- Final outcomes may be joined only into the label table. Unregistration dates may determine cohort eligibility and withdrawal outcomes; they must never enter the feature matrix.
- Every feature must use information observable by the snapshot. Known future assessment schedules may define context; future submissions, grades, outcomes, and activity may not define predictors.
- Keep failure and withdrawal separately in reporting even when combined for training. Risk probabilities refer to the remainder of the course, so their horizon changes with snapshot week.

## Candidate feature definitions

Windows are inclusive: recent 7 days = [snapshot_day-6, snapshot_day]; preceding 7 days = [snapshot_day-13, snapshot_day-7]; recent 28 days = [snapshot_day-27, snapshot_day]. Truncate windows at day 0. Exclude negative-day activity from v1 and report that choice. Add observed window length when fewer than 28 days have elapsed.

| Feature | Definition | Source / availability rule |
|---|---|---|
| course_day, course_progress | Snapshot day and day divided by presentation length | courses; length must be known at prediction time |
| clicks_7d, clicks_28d | Sum of sum_click within each window | studentVle.date <= snapshot |
| active_days_7d, active_days_28d | Distinct days with positive click totals | studentVle, aggregate daily first |
| engagement_change | clicks_7d minus preceding-7-day clicks | Only enable once both complete windows exist; otherwise missing |
| days_since_activity | Snapshot minus most recent positive-click day | No activity: missing plus no_activity flag; not zero |
| assessments_due | Count of scheduled, non-exam assessments due from day 0 through snapshot | assessments; schedule assumed known |
| submissions_so_far | Count of distinct non-banked, non-exam assessment submissions observed by snapshot | studentAssessment joined to assessments |
| overdue_assessments | Due assessments without an observed submission by snapshot | Start with eligible roster x scheduled assessments, not submissions alone |
| late_submission_rate | Observed submissions with date_submitted > due date / observed submissions with known due date | Submission date <= snapshot; missing if denominator zero |
| days_since_submission | Snapshot minus latest observed submission date | Missing plus no_submission flag when absent |
| score_mean_so_far | Mean available non-exam score, on OULAD's original score scale | Future timestamp-enabled feature only; excluded from OULAD v1 |
| scored_assessment_count | Number of available non-null scores | Same score availability rule |
| recent_score_change | Mean of latest two available scores minus mean of preceding two | Order by availability then assessment ID; missing until four scores exist |

Use the module/presentation from assessments to attach each submission to its course. Validate many-to-one assessment joins and unique enrollment keys. Count submissions independently of score presence. Preserve true zeros; do not replace missing scores with zero. Add missingness indicators and fit any learned imputers/scalers on training data only. Treat is_banked=1 separately: exclude it from current-submission and score features in v1 and document coverage. Missing assessment due dates cannot establish overdue or lateness features.

### Grade availability limitation

OULAD records submission dates but does not establish when each score became visible. A submission before the snapshot is necessary but not sufficient to establish score availability. The primary conservative baseline uses engagement, submission, and schedule features without scores. Do not assume any grade-release delay. Grade-based features require a recorded grade_available_at timestamp on or before the snapshot. Without that timestamp, exclude scores from time-sensitive training and prediction features. Existing OULAD scores may support separately labeled descriptive exploration, but not verified as-of model evaluation. Never include a submission after the snapshot, regardless of its due date. Production score features require grade_available_at.

## Inputs and provenance

Required original OULAD inputs: studentInfo.csv, studentRegistration.csv, courses.csv, assessments.csv, studentAssessment.csv, studentVle.csv. vle.csv is optional for later resource-type features. Preserve original files, record source/version and SHA-256 hashes, and fail clearly on missing files or columns. Do not automatically delete, extract over, download, or regenerate source data.

Existing research notebooks remain in Downloads and must not be overwritten. Their Google Drive data path must be located before a full-data run. No original OULAD CSVs were found during the initial local search; this is not proof that none exist elsewhere.

## Training and evaluation

1. Partition original enrollments before generating snapshots. All snapshots of an enrollment must stay in one partition.
2. Primary evaluation: train on earlier presentations, tune on a separate later validation cohort, and reserve a subsequent presentation cohort for one final test. Select the exact cohorts after checking date coverage and class counts. Use presentation dates, not lexical presentation codes.
3. For the primary student-disjoint evaluation, remove cross-partition students from later partitions using IDs only and report exclusions and sample sizes. Also report a separately identified realistic temporal evaluation if repeated students are retained. No final outcome from a future or unfinished enrollment may be available to training at the chosen training date; explicitly audit this chronology before calling a split prospective.
4. Keep module/presentation identifiers as grouping/context metadata initially, not predictors. Report held-out module performance where enough data exists; do not claim generalization from a random row split.
5. Compare DummyClassifier, regularized LogisticRegression, RandomForestClassifier, and HistGradientBoostingClassifier (histogram variant for the larger snapshot table; internal early stopping disabled). Fit imputation and scaling in pipelines. Choose models, thresholds, and calibration with training/validation only.
6. Report average precision, ROC-AUC, precision, recall, F1, Brier score, calibration, prevalence, and counts by snapshot week and module. Report undefined metrics explicitly for single-class strata. Select an outreach capacity with advisors; report recall and precision among the top K active enrollments per weekly cohort. Do not invent a capacity or risk-band threshold.
7. Prevent long-running enrollments dominating training by evaluating enrollment-balanced sample weights (each enrollment's snapshots sum to one). Report performance by week; use student-grouped uncertainty estimates when feasible rather than treating correlated snapshots as independent.
8. Retain demographics outside the predictor matrix for a separately governed fairness audit, where lawful and appropriate. Do not infer causality from feature importance. Global model importance alone is not an individual explanation.

Historical notebook metrics are exploratory and must be rerun after correcting leakage and splits. Synthetic AcadMate scenario labels are integration fixtures, not evidence of predictive performance.

## LMS prototype scope

Brightspace is the intended LMS. Direct access is unavailable because of institutional access restrictions. The architecture retains Brightspace as the intended data source. The MVP validates the integration flow using separate, explicitly synthetic LMS event fixtures linked to the existing synthetic academic dataset. Original OULAD records remain the research model training/evaluation source; see SIMULATED_LMS_INPUT_CONTRACT.md. It does not connect to Brightspace or claim that its events/API fields have been verified.

LMS integration is a confirmed project requirement. Actual feed access is a future integration dependency, not a prerequisite for the research prototype. The OULAD research adapter must preserve source values and provenance. Additional synthetic MVP events are explicitly labeled and isolated under ml/fixtures/simulated_lms/; they must never be presented as observed institutional/OULAD records, added to the fixed academic CSVs, or used as evidence of predictive accuracy. No grades, release delays or outcome labels are invented for these fixtures. OULAD clicks are research engagement measures, not verified Brightspace-equivalent events.

Weekly snapshots are the initial research cadence. Any daily data-delivery schedule remains an optional simulation assumption rather than a fact about Brightspace. Updating predictions does not require retraining models weekly. Source arrival/availability times must be honored where recorded; historical OULAD experiments must disclose that event-day availability is a research assumption for activity/submission records, not proof of real delivery latency.

## AcadMate integration boundary

The inspected backend stores students, programs, courses, credits, enrollment terms/statuses, final grades, and grade points. Its profile service derives GPA/completed credits. It lacks VLE logs, assessment schedules, submission timestamps, grade availability times, course start/end dates, withdrawal events, and historical snapshots. None of the seven original OULAD features is directly reproducible from the current schema. Final course grades must not substitute for early assessment scores.

Potential future backend-only features include prior completed-course GPA, prior failed/repeated courses, earned credits, and current course load. These require reliable chronological enrollment history and separate suitable training data; they are not interchangeable with OULAD assessment/LMS features. GPA and repeat-derived academic-history features are excluded from v1. Before adding them, obtain the applicable institutional catalog/handbook and advisor or registrar clarification, or have the team and supervisor approve an explicitly labeled demonstration policy. Record policy source/version, grades included in GPA, failed-attempt treatment, repeat replacement rules, withdrawal/incomplete treatment, and credit-earning thresholds. The current backend calculation is implementation behavior, not an approved policy. Resolving these rules does not block the LMS-only prototype.

A future prediction record should identify enrollment, as-of timestamp, model/feature-contract versions, probability of unsuccessful completion, data coverage, and explanation scope. Missing required feeds must produce an explicit unavailable/insufficient-data result rather than fabricated zero activity. Do not implement an endpoint or database migration in this phase.

## Proposed project layout

```text
ml/
  PREDICTION_FEATURE_CONTRACT.md
  README.md
  requirements.txt
  configs/
  notebooks/                 # Preserved research copies, if authorized later
  src/acadmate_ml/
    data.py
    features.py
    splits.py
    train.py
    evaluate.py
    predict.py
  tests/
  reports/
  artifacts/                 # Generated models; ignore when introduced

data/oulad/
  README.md                  # Source, local paths, checksums and assumptions
  raw/                       # Original data; ignore when introduced
  processed/                 # Generated snapshots; ignore when introduced
```

Implementation progress: a file-based OULAD loader and weekly feature builder, focused tests, README, scoped output ignore rules, and validation report now exist under ml/. Generated snapshots and separate labels are local ignored outputs. No original datasets or notebooks were changed. Chronological student-disjoint split assignment is implemented separately with explicit month-bound chronology gates and a course-end label-availability proxy. See reports/CHRONOLOGICAL_SPLIT_VALIDATION.md. Four fixed baseline models have now been trained on training data and compared on validation only. See reports/BASELINE_VALIDATION.md. Weekly validation review and paired student-cluster uncertainty estimates are now recorded in reports/WEEKLY_UNCERTAINTY_REVIEW.md. Retrospective sigmoid/isotonic calibration assessment on disjoint validation student groups is recorded in reports/CALIBRATION_ASSESSMENT.md; no method is frozen. Early-course calibration remains a concern. The logistic-regression plus sigmoid experiment was frozen before final test access and evaluated once; see configs/FINAL_EXPERIMENT_V1.json and reports/FINAL_TEST_EVALUATION.md. This test cohort is now consumed and must not guide further selection as an untouched holdout.

## First implementation task and acceptance criteria

Implement a pure, file-based weekly snapshot builder alongside the original notebooks, after locating the source OULAD data. No database dependency or backend changes.

- Deterministic unique student/module/presentation/day rows; validated joins and explicit eligibility exclusions.
- Adding any post-snapshot activity/submission must leave features unchanged.
- Changing final outcomes must leave features unchanged.
- Already-withdrawn and not-yet-registered enrollments must be absent.
- All snapshots of an enrollment must remain in one split; the primary split has disjoint student IDs.
- Test no activity versus unavailable feed, zero versus missing score, missing due dates, banked assessments, late submissions, day-boundary events, and presentations without early assessments.
- Produce a coverage/exclusion report and feature manifest before training. Validate with small purpose-built test fixtures first; never regenerate or alter the fixed AcadMate academic CSVs.

Current direction: Brightspace is the intended LMS; use an OULAD-backed simulated integration while direct institutional access is unavailable. Weekly updates and a combined failure/withdrawal target remain working research defaults, with separate outcome reporting. No invented grade-release delays are permitted; score features require recorded availability timestamps. GPA and repeat-derived features are excluded from v1. Remaining team decisions: eventual feed fields and access, production refresh cadence, combined versus separate outcome models, advisor outreach capacity, and an academic policy before introducing GPA/repeat features. These research choices do not establish institutional production policy.
