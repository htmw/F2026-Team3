# Weekly snapshot validation — 2026-10-28

Branch: feature/academic-risk-prediction. No model trained or train/test split assigned.

## Results

- Seven automated tests passed, including strict ResourceWarning checking.
- Full original ZIP run completed successfully: 897,750 weekly enrollment snapshots, 16 feature columns, separate outcome-label file.
- Source SHA-256 before and during build matched: b344faabbf728c2fec93913127813391d259b959aa283de715db51b2c0eaa81b.
- Input records consumed: 22 presentations; 32,593 student enrollment rows; 32,593 registration rows; 206 assessments; 173,912 assessment records; 10,655,280 VLE activity records. Optional vle.csv is not needed by v1.
- Excluded 45 enrollments with missing registration dates; 280,358 candidate snapshots at/after unregistration; 284 before registration; 6,868 banked/exam submission records; 688,988 negative-day activity records.
- Snapshot label counts (not independent students): Pass 448,820; Distinction 109,762; Fail 253,213; Withdrawn 85,955.
- Outputs: ml/outputs/oulad-weekly-v1/{features.csv,labels.csv,manifest.json}; verified ignored by Git.

Tests cover future-event invariance, label/score independence, inclusive time boundaries, missing/zero behavior, overdue/lateness handling, registration eligibility, banked/exam exclusion, missing required feed rejection, and refusing output overwrites.

## Remaining work and limits

Chronological student-disjoint splits, chronology auditing, model evaluation and advisor-capacity metrics are not implemented yet. Do not use a random snapshot split. Source event-day availability and presentation length as completion proxy remain research assumptions. Empty enrollment activity does not prove reliable telemetry coverage. Scores are excluded because no grade availability timestamp exists. No Brightspace connection or field equivalence is claimed. No accuracy/AUC claim is made from feature-generation success.

The builder is intended for validated original OULAD inputs. On a later output-writing or semantic-validation failure it may leave partial files; an existing output directory will not be overwritten. Use a fresh destination when retrying.

Backend code, original notebooks, OULAD ZIP, and the fixed synthetic academic records were not modified. No database access, commit, push, or merge was performed.
