# Full CSV population demo

The canonical 100-student CSV population is connected to the isolated local AcadMate frontend and FastAPI app. Use **http://127.0.0.1:5178**; API and Swagger are at **http://127.0.0.1:8004/docs**. The previous 13-student demo remains unchanged on 5177/8003. No shared PostgreSQL/Neon database was changed.

## Population and identity

Exactly 105 users, 100 students, 4 advisors, 1 program, 30 courses, 800 enrollments, 100 advisor assignments and 3 requirement groups were imported. All original CSV academic values and IDs are preserved; CSV files are unchanged. The canonical `eligible_course_ids` CSV column is explicitly mapped to the pinned main ORM's legacy `eligible_courses_ids` attribute. Added required-course counts are derived from the existing three-credit course values, not new academic policy.

Each advisor has 25 students. Capacities use the existing model default of 40, so none is deliberately over capacity. CSV advisors are Sarah Smith, Rowan Flint, Sage Linden and Quinn Meadow. The small-demo advisors Daniel, Maya and Priya, and students Amara/Hana, are not part of this population. In this dataset student 101 is Santos Shel.

## Demo accounts

Use the existing synthetic demo password `Acadmate!2026` for these local accounts:

| Role | Email |
|---|---|
| Advisor Sarah Smith | sarah.smith@pac.edu |
| Advisor Rowan Flint | advisor.2@example.invalid |
| Advisor Sage Linden | advisor.3@example.invalid |
| Advisor Quinn Meadow | advisor.4@example.invalid |
| Student Santos Shel | santos.shel@pac.edu |

Other student and admin emails remain exactly those in data/synthetic/users.csv. CSV placeholder password strings remain unchanged in the CSVs; valid password hashes are provisioned in the isolated local database only. Reserved example.invalid addresses are accepted for login only when both the local host and exact CSV-demo database guard match. Signup, password reset and non-demo validation are unchanged. No real mailbox or external LMS is required.

## Shared data and snapshot

The initial snapshot is **2027-02-16 at 23:59:59.999999 UTC**, 28 days after the main calendar's Spring 2027 start. All roles use that fixed clock. Changing only the date environment variable is unsupported: the student-submission projection must be rebuilt/validated for a different snapshot first.

All 800 enrollments have linked synthetic histories, schedules, activity and source coverage. Risk sidecars contain 103 course offerings, 1,028 assessment identities and versions, 48,631 activity events, 6,848 submission versions, 262,740 coverage rows and 1,421 history rows. Student Assignment IDs explicitly match the risk assessment IDs; dates and observed submissions share a 1,028-row identity crosswalk. There are 7,998 student-assignment projections. Future submissions are not projected into the current student view. Per-course progress means the percentage of scheduled coursework with an observed submission, not a grade or probability; it is derived consistently for all 800 enrollments.

There are 179 current in-progress enrollments, all scored by the real frozen model at this snapshot. The other 621 are historical/ineligible for a current assessment; all 800 score at their own simulated day-28 historical checkpoint. Historical courses remain separate in the advisor UI. This is software-flow validation on synthetic records, not evidence of institutional predictive accuracy.

The model and calibration artifacts are unchanged. Missing course-component scores, grading weights, instructors, class schedules and graduation dates are not invented. Existing final enrollment grades remain intact. Scenario metadata remains validation metadata, never a model input. Meetings, notes, approval requests and plan items are not copied from unrelated small-demo identities; those features may correctly be empty until exercised.

## Commands

From C:\Users\nhesv\Documents\AcadMate-Team, with the dedicated local PostgreSQL cluster running on 127.0.0.1:55439:

```powershell
$snapshot = 'ml/outputs/main-integration/8c4b0843368b'
$python = '.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe'
# CSV-only compatibility for the existing isolated export:
& $python tools/apply_csv_demo_adapter.py --snapshot $snapshot
# Creates only acadmate_risk_csv_sprint2; refuses unmarked populated databases:
& $python tools/prepare_csv_population_demo.py --snapshot $snapshot
& $python tools/sync_csv_coursework_progress.py --snapshot $snapshot
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File tools/Start-CsvPopulationDemo.ps1
& $python tools/verify_csv_population_demo.py --snapshot $snapshot
```

The launcher starts hidden processes only on the new ports and preserves the old demo. Add `-RestartApi` to the launcher only to reload the CSV API. It does not change machine execution-policy settings. The setup requires the existing main overlay and frozen artifacts documented elsewhere; it does not clone, merge, train, commit or push.

## Validation results

- All 1,143 original academic/source rows compared against CSV values; only the documented local auth hash adaptation is excluded from byte-value comparison.
- All eight CSV hashes unchanged; fixed-file validator and all 31 validator tests passed.
- 800 real frozen-model day-28 scores; 179 current scores; 621 correctly unavailable current historical assessments.
- All 7,998 assignment/submission projections checked against as-of risk records; all 800 progress values independently checked.
- All 100 assigned student records served under their correct advisors; 4 real explanation smokes and 4 forbidden cross-advisor checks passed.
- All 400 student dashboard/course/assignment/degree-audit responses passed; admin overview/advisor APIs passed.
- Existing backend suite: 361 passed. Additional CSV login-scope test: 1 passed, covering local CSV, normal local and non-local database settings plus signup/reset/malformed-address rejection.
- Frontend production build passed; existing large-chunk warning remains.
- Original smaller demo academic fingerprint still matches its original manifest.
- Browser review confirmed the new 5178 dashboard shows Sarah's 25-student caseload and Spring 2027.

Detailed machine-readable manifests and validation results are ignored under ml/outputs/main-integration/8c4b0843368b/csv-*.json. Generated datasets, credentials, model binaries and environments are not committed. No commits or pushes were made.
