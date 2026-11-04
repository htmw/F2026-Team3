# Simulated LMS input contract — MVP v1

Brightspace remains the intended source in AcadMate's architecture. The MVP uses explicitly synthetic, platform-neutral LMS input to validate the software flow. No live Brightspace access is required or implemented; these fields are not claimed to match its API or exports.

## Data separation

- Original OULAD: fixed research training/evaluation source; unchanged.
- data/synthetic/: existing academic identities, courses and enrollments; unchanged.
- ml/fixtures/simulated_lms/events.json: new demonstration event records linked by existing IDs. No final outcomes, grades, risk labels or accuracy claims.
- ml/outputs/simulated-lms-v1/features.json: local ignored derived features. No model inference or backend import in this stage.

This is an additional sidecar fixture, not regeneration or extension of the eight academic CSVs. Cases describe input behavior, not assigned risk categories. No student names, emails or credentials are copied into fixtures.

## Input envelope

schema_version must be 1.0; source_kind must be synthetic_lms_demo. intended_platform is a descriptive architecture label, not a verified connector identifier. as_of_day is a nonnegative weekly relative day (7,14,...). assumptions lists demonstration choices. All record IDs are nonempty unique strings within their table. Day/count fields are nonnegative integers, not booleans. V1 supports only active linked enrollments and one submission per enrollment/assessment; revisions, resubmissions, grade histories, withdrawals and real timestamps require later explicit schema extensions.

| Table | Fields | Meaning |
|---|---|---|
| courses | course_id, length_days, available_day | Existing academic course; known simulated duration |
| enrollments | enrollment_id, student_id, course_id, registered_day, available_day, case | Exact identity linkage to an existing in_progress academic enrollment |
| assessments | assessment_id, course_id, due_day, available_day | Known scheduled non-exam coursework; no scores |
| activity | event_id, enrollment_id, day, available_day, activity_count | OULAD-style simulated activity count; not a validated Brightspace measure |
| submissions | submission_id, enrollment_id, assessment_id, submitted_day, available_day | Observed first submission; no score or grade |
| coverage | enrollment_id, start_day, through_day, available_day, activity_complete, submissions_complete, schedule_complete | Explicit declared feed coverage; exactly one declaration per fixture enrollment |

IDs are for joining and output metadata, never predictors. Existing term/status records are not rewritten. Courses, students and enrollments must exist in the original academic CSVs; submissions must reference an assessment in the enrollment's course. Duplicated IDs, conflicting linkage, negative counts and impossible event availability fail validation.

## As-of and coverage rules

A usable event must both occur and be available on/before as_of_day. available_day cannot precede the activity/submission event day. Future schedule information can be known early, but only due assessments contribute to due/overdue counts. A submission after the snapshot cannot cure an earlier overdue assessment.

The course and enrollment must be available, registration effective, and course not ended at the snapshot. Coverage must be known by the snapshot, extend from day 0 through that day, and declare all three feeds complete. Without sufficient coverage return status=unavailable, features=null and a reason; never fabricate zero activity. Coverage is an assertion of the simulator, not a verified institutional delivery guarantee. V1 assumes first-submission records and immutable assessment schedules, excluding schedule-change and lifecycle-history modeling.

The existing 16-feature function is reused without modification. Grade-release delays, scores, GPA and final outcomes are excluded. A complete feed with no events returns actual zero counts and explicit absence flags, distinct from unavailable data.

## Included cases

All four link to course 10026 in Spring 2027. The fixture uses a simulated 112-day duration and day-28 snapshot; neither is derived from the real institution's schedule. These are simulated relative days, not a claim about today's actual enrollment state.

| Enrollment | Student | Case | Expected result |
|---|---|---|---|
| 20014 | 10000 | Steady participation | Ready; 75 clicks in last 7 days; 150 in last 28; two submissions; no overdue work |
| 20024 | 10001 | Recent activity gap | Ready; 10 days since activity; one late submission; one overdue assessment |
| 20034 | 10002 | Confirmed zero activity | Ready; no activity/submissions; two overdue assessments |
| 20044 | 10003 | Activity feed unavailable | Unavailable; no feature vector |

One future activity event and one late-arriving historical event are included intentionally and must not affect day-28 features. No synthetic record is used to retrain, recalibrate, or score predictive accuracy. A later demonstration using saved predictions must label domain transfer and early-week overestimation limits; this adapter alone is not deployment validation.

## Run

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\ml\src"
.\.venv\Scripts\python.exe -m acadmate_ml.simulated_lms --input ml/fixtures/simulated_lms/events.json --academic data/synthetic --output ml/outputs/simulated-lms-v1/features.json
```

Use a new output file for another run; existing files are never overwritten. Output contains identity/as-of/provenance metadata, ready/unavailable status, feature values or a reason, and a research-only warning. Source academic hashes are included. This command never contacts a database, LMS or network and does not load the final test cohort or saved models.
