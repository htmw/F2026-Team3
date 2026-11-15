# Graduation projection

The demo calculates estimates without overwriting saved graduation targets or CSV records. Main estimate: 9 credits per future Spring/Fall; 12-credit alternative appears in the explanatory note when different. Current enrolled credits count only for the current term, assuming successful completion. May ends Spring; December ends Fall. No summer credits are assumed. An underway term without enrollment contributes no credits.

This is a credit-based estimate, not a verified degree audit. Course availability, prerequisites, requirement groups and approvals can delay completion. Meeting the credit total displays ?Credits complete? rather than inventing an award date. Missing program requirements do not produce a guessed date.

Apply after other isolated-demo overlays:

```powershell
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/apply_main_graduation.py --snapshot ml/outputs/main-integration/8c4b0843368b
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File tools/Start-CsvPopulationDemo.ps1 -RestartApi
```

Shared by student dashboard/degree audit, advisor record/list/dashboard/reports, profile and approval text. Stored targets, retention logic and preference writes remain unchanged. No production database migrations or imports.

Validation: 15 calendar/credit tests passed; read-only population check passed for all 100 students across student dashboard, advisor record, degree audit and advisee list, plus all four advisor bucket totals. Original CSV hashes unchanged. Production frontend build passed (existing bundle-size warning). Population estimates: May 2027: 20; December 2027: 65; May 2028: 10; December 2028: 5.


## Seeded main regression review

The isolated main test fixture pins October 1, 2026 and has a 36-credit program. Enrollment/course records were checked independently of the projection helper. At 9 credits each future Spring/Fall, the eight advisees project as follows:

| Student ID | Completed credits | Current Fall credits | Projection |
| --- | ---: | ---: | --- |
| 101 | 21 | 9 | May 2027 |
| 107 | 9 | 0 | May 2028 |
| 108 | 18 | 6 | December 2027 |
| 109 | 6 | 3 | May 2028 |
| 110 | 6 | 0 | December 2028 |
| 111 | 6 | 0 | December 2028 |
| 112 | 6 | 0 | December 2028 |
| 113 | 27 | 9 | December 2026 |

The dashboard buckets therefore contain 1 for December 2026, 1 for May 2027, and 6 later. Two original main tests asserted stored targets and plan-approval wording; the isolated overlay updates those exact assertions to the credit-based estimate and its qualifications. All other assertions remain intact. `test_main_graduation_regression.py` checks the eight explicit enrollment credit totals and dates. `tools/apply_main_graduation.py` installs these checks reproducibly and stops if the legacy assertions have changed unexpectedly.

Final regression run: **376 backend tests passed** in 223.84 seconds against the disposable local test database. The separate calendar/credit suite passed **15 tests**. No CSV records, shared database, model artifacts, or graduation calculation logic changed during this review.
