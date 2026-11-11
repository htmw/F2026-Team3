# Chronological split validation — 2026-10-28

Branch: feature/academic-risk-prediction. All 15 ML tests passed, including the seven feature tests. The full 897,750-snapshot input was processed successfully. No model has been trained or selected.

| Partition | Presentation | Students | Enrollments | Snapshots |
|---|---|---:|---:|---:|
| Training | 2013B | 4,360 | 4,362 | 126,402 |
| Validation | 2013J | 7,535 | 7,539 | 236,553 |
| Test | 2014J | 8,846 | 9,269 | 284,765 |

All three pairwise student intersections are zero. Every retained enrollment belongs to one partition, with all its eligible snapshots kept together apart from the documented chronology exclusion. Student ownership uses IDs only, before reading outcome labels: earlier selected cohorts own repeated students, including enrollments that produce no snapshots. No class balancing or outcome-based partition selection is performed. Both target classes occur in every partition.

## Chronology policy and assumptions

The official OULAD overview identifies B as February and J as October: https://research.stem.open.ac.uk/ouanalyse/dataset/ . Exact start days are not present in courses.csv. The implementation therefore uses the first day of the month as the earliest possible snapshot origin, and the last day plus course length as the latest possible outcome-maturity proxy.

Training outcomes are assumed mature after 2013-10-26. Validation snapshots must fall strictly after that date even under the earliest start bound; 22,860 early validation snapshots are excluded, so validation begins at day 28. Before final testing, training and validation outcomes are assumed mature after 2014-07-26. All retained 2014J test weeks pass this guard. This is a conservative calendar check under a course-end proxy, not verified prospective evaluation: actual final-result release times are absent. No seven-day or fourteen-day grade-release lag is invented, and score features remain excluded.

2014B is intentionally unused in this initial experiment, avoiding the overlapping adjacent-presentation sequence. Another 227,170 input snapshots are unassigned because of the unselected presentation or repeated-student exclusion. These counts plus 22,860 chronology exclusions and 647,720 retained snapshots account for all 897,750 inputs. Repeated-student exclusions remove 182 validation enrollment records and 999 test enrollment records; these are source enrollment counts, not snapshot counts.

## Coverage and interpretation

Training contains BBB, DDD and FFF. Validation additionally contains AAA, EEE and GGG. Test additionally contains AAA, CCC, EEE and GGG. Report metrics by module and separately for familiar and unseen modules. This split combines temporal change with module change; pooled results cannot isolate either effect. Validation cannot establish performance during days 7–21. No final test model-performance metrics have been calculated.

Each partition exports features.csv and labels.csv separately, plus enrollments.csv containing snapshot counts and per-snapshot weight 1 / retained enrollment snapshot count. Use these training weights to avoid longer-lived enrollments dominating fitting. Identifiers and these weights are not predictor columns. The manifest includes all snapshot counts by week/module/outcome, provenance hashes, exclusions, and chronology gates. Outcomes in this report describe coverage only; do not use test outcomes for tuning or threshold choice.

## Checks performed

- Stable student assignment independent of outcomes and input order.
- Strict course-month chronology boundaries, including leap years and same-day rejection.
- Missing required partition rejection; both-class and nonempty checks on full outputs.
- Feature/label identity and outcome consistency, ordered unique enrollment snapshots, snapshot timing, and input row totals.
- Rejection of wrong archive provenance, misaligned labels and existing output destinations.
- Enrollment weights sum to one across retained snapshots.
- All original feature cutoff tests continue to pass.

Outputs are local and ignored: ml/outputs/oulad-splits-v1/. Existing snapshots and original ZIP remain unchanged. No backend code, notebooks, academic CSV records, database, commit, push or merge was touched. Failed runs may leave partial output; use a fresh destination rather than overwriting it.

Next: implement training-only preprocessing and baseline evaluation, using validation for selection and reserving test performance evaluation until the setup is frozen. Clearly label the course-end maturity and source event-availability assumptions.
