# Simulated LMS fixture validation — 2026-11-02

Brightspace remains the intended architectural data source. This MVP stage uses clearly labeled synthetic, platform-neutral events and does not implement a live connector or claim compatibility with Brightspace fields.

## Delivered

- ml/SIMULATED_LMS_INPUT_CONTRACT.md: input fields, time/coverage rules, identity joins, limitations and run command.
- ml/fixtures/simulated_lms/events.json: four cases linked to existing in_progress enrollments 20014, 20024, 20034 and 20044; all course 10026, Spring 2027.
- ml/src/acadmate_ml/simulated_lms.py: read-only academic linkage validation and as-of conversion using the unchanged 16-feature function.
- Seven focused adapter tests, in addition to the existing suite.

## Results

All 38 ML tests passed. Full fixture adapter run produced four records: three ready feature vectors and one unavailable record with features=null. Hand-checked values are asserted in tests: steady participation has 75 recent-7-day clicks, 150 recent-28-day clicks, two submissions and no overdue assessment; the activity-gap case has 10 days since activity, one late submission and one overdue assessment. Confirmed zero activity remains distinct from unavailable telemetry. Future and late-arriving events cannot alter day-28 vectors.

Academic linkage, duplicate events, impossible availability, score exclusion and coverage knowledge are checked. Original academic CSV hashes are unchanged across adapter execution. Derived output is local and ignored: ml/outputs/simulated-lms-v1/features.json. It records hashes of academic inputs used for joins.

## Boundary

The simulated 112-day duration, relative day-28 snapshot and activity counts are demonstration assumptions, not institutional schedule facts or verified Brightspace semantics. Cases have no assigned final outcome or ground-truth risk. No existing academic CSVs were regenerated or edited. No model training, recalibration, production inference or accuracy evaluation was performed on these fixtures. The real held-out cohort was not reevaluated; evaluation tests use only tiny temporary fixtures.

Next: a separate local inference demonstration can consume ready vectors using the existing frozen model, retain the unavailable state, and clearly label domain-transfer and early-risk calibration limits. Backend/frontend integration remains a later task. No backend code, database, original notebooks or original OULAD data was changed. Nothing was committed, pushed or merged.
