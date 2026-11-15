# Sprint 2 team integration candidate

This is an isolated review candidate, not a merge or a replacement for the working CSV demo.

**Latest result: 418 backend tests passed in 116.70 seconds in a fresh isolated Python environment, with real-artifact HTTP smoke enabled and zero failures/errors/skips. See ML_EXPLANATION_SETUP.md for the November 14 fresh-environment checkpoint. The earlier 405-pass and 402-pass/2-failure results below are retained as history.**

## Pinned sources

- Team main: `9dba938da14df8607c81b6f92988e8210977bf24`.
- Datta risk/degree progress: `a0c19303afbf51eda566b705e9934f6acb157627`.
- Shared comparison base: `8c4b0843368b679ac3f3353f6332c73356888b14`.
- Working branch remains `feature/academic-risk-prediction`; Li's latest local review changes have not been identified in a published branch. Do not describe Datta's branch as Li's work.

## What the candidate combines

`tools/prepare_team_review.py` exports backend/frontend from pinned main to a NEW directory under ignored `ml/outputs/main-integration/`. It checks that the student router has not changed since the shared base before adopting Datta's additional degree-progress routes, service, schema and tests. It applies the existing authored advisor/approval/graduation/feedback overlays and applies Datta's degree-progress UI delta to the student page. Explicit checks require both degree progress and our returned-plan feedback/approved-label behavior to remain present.

No CSVs are adopted from another branch, no existing demo is overwritten, and preparation makes no database connection. The export manifest records source commits and the combined page hash. Guard failures or partially prepared output require review; do not silently reuse the directory.

```powershell
# Run from the repository root with the existing isolated Python environment.
$python = '.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe'
& $python tools/prepare_team_review.py --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930
npm.cmd --prefix ml/outputs/main-integration/team-review-9dba938-a0c1930/frontend ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix ml/outputs/main-integration/team-review-9dba938-a0c1930/frontend run build
$env:ACADMATE_MAIN_SNAPSHOT = Join-Path $PWD 'ml/outputs/main-integration/team-review-9dba938-a0c1930'
$env:ACADMATE_EXPECT_DEGREE_PROGRESS = 'true'
node --test frontend/tests/main-plan-feedback.test.js
```

The directory already exists after this review; choose a new name for a new preparation run. This command is development review tooling, not a deployment command.

## Confirmed alignment points

- The frozen experiment configuration and expected model/calibration hashes are identical between our branch and Datta's branch. Risk models and the original generator match after newline normalization.
- Preserve our explicit-column risk queries and request-validation handling. Datta's older service/router omit those fixes reported by Li.
- Latest main adds `users.must_change_password`, updated account-creation/authentication behavior, and a guarded test-database setup. Do not run its newer ORM against an old demo schema without an explicit local migration plan. No migration was run on either working demo or shared infrastructure.
- Import-only OpenAPI check: all **102 existing paths preserved**, **3 risk paths added** (105 total). This checks registration, not HTTP/database inference.
- Combined student page rendered regression: **1 passed, 0 skipped**, including 21/30 completed credits, 9 remaining credits, returned feedback, resubmission, approved labels and feedback removal. The same portable fixture also passed against the original demo page.
- Combined frontend production build: passed; existing >500 kB bundle warning remains.

## Dataset reconciliation: pending

Our preserved CSVs: 105 users, 100 students, 4 advisors, 1 program, 30 courses, 800 enrollments, 100 advisor assignments and 3 requirement groups.

Datta's published branch: 103 users, 99 students, 4 advisors, 1 program, 27 courses, 792 enrollments, 99 advisor assignments and 3 requirement groups. Its README still lists the original totals. Missing CSV IDs include users 1/2, student 101, courses 11/12/13 and eight enrollments. All 99 shared student records also use a different program_id. Other shared rows in the compared user/course/enrollment/assignment files match.

These are source-file differences, not a claim about Datta's final database population: seed records or importer mappings may explain some omissions. Obtain his or Li's import manifest and identifier crosswalk before selecting a canonical integration dataset. Do not union files or overwrite either dataset automatically. Our 100/800 demo stays intact while this is unresolved.

## Remaining handoff checkpoints

1. Identify Li's exact reviewed branch/commit or source patch; compare against this pinned candidate before merging.
2. Agree on the canonical student/course/program/enrollment crosswalk and import provenance. Do not load data during code alignment.
3. Preserve main's auth/session/error conventions and current admin screens; keep demo-only overrides local.
4. Validate the full latest-main backend suite plus degree-progress/approval regressions on a disposable *_test database. The historical 376-pass result applies to the earlier demo snapshot, not this candidate.
5. Actual full-population HTTP inference against the newer schema remains separate from registration and rendered mock checks. Frozen model artifacts and explanation backgrounds remain provisioned outside Git.

No commit, push, branch merge, shared database change or model retraining was performed.


## Latest backend validation results

Combined candidate: **402 passed, 2 failed** in 248.43 seconds. All tests used only `acadmate_risk_demo_main_sprint2_test`; conftest rebuilt that disposable database. The first invocation was correctly refused by main's safety guard because app/test URLs were identical; the rerun used distinct names and left the guard unchanged.

Both failures reproduced in **unmodified pinned main**, running only the two affected tests: **2 failed** in 6.01 seconds. They therefore predate the candidate under this local environment:

- `backend/tests/test_admin_advisors.py::test_seeded_list`: expects `temporaryPassword` in the ordinary advisor service row; the row does not include that key.
- `backend/tests/test_admin_users.py::test_reset_password`: calls `db.refresh(user)` on a `User` created by the `make_user` fixture in another session; SQLAlchemy reports that it is not persistent in this session.

No admin implementation or test assertions were changed to mask these failures. Share this evidence with the backend/frontend owners and compare Li's unpublished fixes before deciding on repairs. The candidate is not an all-green merge-ready release.

To reproduce the backend run from repository root (the test fixture intentionally drops/recreates only the dedicated local test database):

```powershell
$repo = $PWD.Path
$snapshot = Join-Path $repo 'ml/outputs/main-integration/team-review-9dba938-a0c1930'
$python = Join-Path $repo 'ml/outputs/main-integration/8c4b0843368b/.venv/Scripts/python.exe'
$env:PYTHONPATH = "$repo/backend;$repo/ml/src"
$env:DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2'
$env:TEST_DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2_test'
Push-Location $snapshot
try { & $python -m pytest backend/tests -q } finally { Pop-Location }
```

The app URL is only the safety guard comparison; conftest replaces it with TEST_DATABASE_URL before importing the database module. Do not use shared/Neon URLs here. Both working demo databases remain untouched.


## Follow-up repairs and real-model checks

The isolated preparation tool now applies two narrow, guarded test corrections reproduced from the pinned main failures. No admin production behavior changes:

- Advisor listing: require that the raw service row does not expose a temporary password, then validate it through `AdminAdvisorRow` before asserting the serialized API keys and null password. This preserves the API contract while respecting the service/schema boundary.
- Password reset: obtain the fixture-created user through the current test database session before refreshing it. All password verification, forced-password-change, revoked-session, used-token, audit-event and rejection assertions remain unchanged.

Both corrected tests passed in the focused run.

`backend/tests/test_main_team_risk_smoke.py` adds an opt-in check that creates only test risk sidecars, invokes actual frozen model inference through the authenticated latest-main HTTP routes, and checks real inference invocation counts. It refuses anything except the named loopback *_test database. It prevents pipeline fitting, validates unauthorized and foreign-advisor access, invalid/unknown enrollment responses, missing-artifact 503, incomplete coverage with null probability, cache invalidation and unchanged academic records. Test-only sidecars are dropped individually in reverse dependency order, avoiding metadata-level DDL on copied academic enum types.

The first harness attempts exposed namespace/session-isolation and cleanup problems; these were corrected. The targeted real-artifact smoke subsequently **passed (1 test, 17.27 seconds)**. Login verification clears preceding cookies and checks the actual authenticated identity; HTTP 200 from a password-change challenge is not treated as successful authentication.

The approvals render harness now also resolves React/ReactDOM/router from the same prepared team frontend, while keeping its authored test dependencies in the branch. Advisor approvals and combined student feedback/degree progress: **2 passed, 0 skipped**.

Run the real-model check together with the full backend suite using the documented test environment and:

```powershell
$env:RUN_TEAM_RISK_SMOKE = 'true'
$env:OMP_NUM_THREADS = '2'
# From the prepared candidate directory, with the Python path and local URLs above:
& $python -m pytest backend/tests -q --show-capture=no
```

This fixture uses the existing main seed enrollment IDs, not the separate 100-student CSV demo. It validates integration behavior, never predictive accuracy. The working full-population demo is preserved; reconciling published dataset IDs remains a separate import/handoff decision.


## Full CSV degree-progress compatibility

`tools/verify_team_degree_progress.py` ran Datta's newer degree-progress service and response schema against the existing local 100-student/800-enrollment demo, inside a PostgreSQL-enforced repeatable-read/read-only transaction. All **100 students passed** an independent calculation from the preserved CSV completed attempts, eligible-course lists and requirement-credit caps, including serialized earned/remaining credits and completion rate. No course, student, program, enrollment, approval or CSV record was changed. This validates service/data compatibility, not migration of the newest authentication schema or a union of Datta's dataset with ours.

Both existing local demo health endpoints returned HTTP 200. Read-only population counts still match 105 users, 100 students, 4 advisors, 1 program, 30 courses, 800 enrollments, 100 advisor assignments and 3 requirement groups.

```powershell
& $python tools/verify_team_degree_progress.py --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930
```


## Final verified checkpoint

- Combined latest-main backend + Datta degree progress + authored regressions + real-artifact HTTP smoke: **405 passed, 0 failed, 0 skipped**, 263.97 seconds.
- Advisor approvals and combined student degree-progress/feedback rendered tests: **2 passed, 0 skipped**.
- Combined frontend production build: passed, existing bundle-size warning only; no frontend production code changed after that build.
- Full CSV degree-progress comparison: **100 students / 800 source enrollment rows passed**, database-enforced read-only.
- Both existing demo APIs returned healthy HTTP 200 and the full population counts remained exact.

The isolated admin test repairs are applied reproducibly by `tools/prepare_team_review.py`; no main admin production code was modified. The authored `test_main_team_risk_smoke.py` is copied by the same preparation tool and runs only with RUN_TEAM_RISK_SMOKE=true. Ordinary runs explicitly skip it when artifacts/integration testing are not requested.

Remaining boundary: the candidate has not replaced the running CSV demo or been deployed to shared main. The published CSV identifier differences are recorded, not resolved by overwriting academic records. Li's unpublished changes can be compared later without blocking this tested checkpoint. No accuracy claim, new academic policy, shared migration, commit, push or merge is implied by these software checks.


## Separate full-population visual-review demo ? November 14, 2026

The combined version is now running separately at **http://127.0.0.1:5179**, API **http://127.0.0.1:8005/docs**, using `risk_mvp.team_host:app` and the named loopback database `acadmate_risk_team_review_sprint2`.

`tools/prepare_team_review_demo.py` uses pg_dump/pg_restore to copy the existing local full-population synthetic demo into a new, provenance-marked database. It refuses unrelated existing targets. No CSVs, academic records, LMS events or model files were regenerated. It verifies identical academic fingerprints, adds latest main's `must_change_password` column ONLY in the new clone, and clears only the copied login sessions. The initial setup hit an incorrect session table name; that transaction rolled back, and the verified clone was resumed after correcting it to `sessions`. The setup now records the intermediate cloned state for safe resumption. The source database and its approval history remain unchanged.

The team host requires the exact new database name, loopback host, port 55439, explicit opt-in and fixed date. It has its own session cookie, uses the existing February 16, 2027 demo snapshot and preserves authorization. Reserved synthetic advisor emails are accepted for login only in this one local clone; other authentication validators remain unchanged.

Verified through the running frontend proxy:

- Student login, dashboard, course plan, degree audit and Datta degree-progress API passed (21 of 30 completed credits).
- All four advisor accounts signed in successfully; each returned exactly 25 assigned students and a successful approvals response.
- Admin login and overview passed.
- Santos's eight recorded enrollments were returned; an active enrollment produced a real frozen-model score and an available explanation.

These are HTTP checks, not a completed visual review. Both native computer-use connections reported `Computer Use native pipe is unavailable`, so no browser screenshot/layout inspection is claimed for this demo yet.

For the already prepared database, start services from repository root:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File tools/Start-TeamReviewDemo.ps1
```

The launcher refuses occupied ports instead of stopping unrelated processes. It uses the existing isolated Python environment, hidden service windows and ignored logs. It does not restart or overwrite either original demo. If a NEW setup is required, review the provenance safeguards before running:

```powershell
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/prepare_team_review_demo.py --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930
```

The dump, clone manifests, logs, database and exported app remain ignored. Authored setup/host scripts and this documentation are uncommitted. No shared PostgreSQL/Neon operation or Git commit/push/merge was performed.


## Consolidated student degree summary ? November 14, 2026

The authored `frontend/src/components/research/MainTeamDegreePlan.jsx` replaces the duplicated progress block plus summary with one four-tile summary, while retaining Datta's unchanged degree-progress calculation/API. Credits completed and remaining-now totals come from that endpoint; current/after-term details and approval-aware status remain from the existing audit. Requirements appear once, followed by the existing semester roadmap and feedback controls. The earlier described full UI delta is now represented by this consolidated authored page rather than applied verbatim from Datta's JSX diff.

The separate top-level completion tile and repeated requirement-credit blocks were removed. The remaining credits distinguish "9 credits remaining now" from "Remaining after this term: 6", qualified by passing current courses. The graduation date is shown once with an Estimate badge; its unrelated progress bar is removed. The subtitle retains program/catalog information. Approval status remains separate from the estimate assumptions.

An optional `graduation.estimateNote` field exposes the existing `graduation_note()` text to the page; it matches the student dashboard and does not change pace assumptions, date calculations or database schema. The isolated overlay also updates the exact graduation-response assertion for this additive field, retaining the date and approval-state checks. No course records, CSVs, model files or approval decisions changed.

Validation after this change:

- Focused backend: **25 passed** in 11.49 seconds (summary-note equality, approval lifecycle, plans, degree progress).
- Frontend rendered workflow: **2 passed**, checking no duplicated credit/date summary, shared estimate note, returned feedback, resubmission and approved labels.
- Frontend production build: passed, existing bundle warning only.
- Live Chrome review on the separate demo: confirmed one summary, 21/30 completed, 3 in progress, 6 remaining after term, December 2027 estimate, and the shared explanation. Original course requirements and approval states were still available in the page accessibility tree. The screenshot showed the summary and requirement list without the previous duplicated card. No plan or approval action was submitted.

The historical **405-pass full backend run predates this small additive response/UI change**; it was not rerun for this iteration. The 25 focused backend checks above are the current validation for the change. Roadmap badge/text overlap remains the frontend team's deferred layout work.

## Advisor attention and approval verification - November 14, 2026

The dedicated team-review database was missing from the loopback-only attention alignment allowlist. Added its exact database name so the dashboard, advisee list and record use the same overdue-assessment evidence. Existing academic thresholds and frozen model probabilities were preserved. Approved-plan wording now says: "The course choices are approved. Confirm availability and any outstanding requirements before registration."

Validation for these changes (before the final browser review):

- Focused attention/dashboard/advisee/record/approval backend tests: 18 passed in 15.05 seconds.
- Read-only population consistency check: all four advisors, 100 students and 179 active enrollments passed. Attention counts: Sarah 22, Rowan 20, Sage 20, Quinn 23. Academic fingerprint unchanged.
- Frontend production build passed with the existing bundle-size warning.

Final live Chrome review confirmed Sarah's dashboard and navigation badge show 22, the Advisees filters show All 25 / Needs attention 22 / No current flags 3, and searching Santos returns his correct record at /advisor/advisees/101. His list and full-record concern both report one overdue assessment. The course card loaded actual inference at 59.3% and explained three late submissions and one overdue assessment. The approved Fall 2027 plan displays the revised registration qualification alongside existing course-offering warnings and the preserved approval comment. No decision, note, message, plan or database write was submitted during this visual check.

This closes these two advisor regression checks; it does not claim a new full-suite run or completion of the remaining admin visual review. No commit, push or merge was performed.

## Admin desktop visual review - November 14, 2026

Reviewed the separate team demo in Chrome as synthetic administrator Morgan Summit. Inspected Overview, Users, Advisors, Courses, Degree requirements, Terms, Integrations and Audit log. Shared colors, typography, cards and navigation are consistent with the student/advisor shell at desktop size. No blocking layout problem was observed on these screens. Settings and AI configuration were not exercised, and responsive layouts remain deferred to the frontend team.

Confirmed visually:

- Users: 105 total, 100 students, four advisors, one administrator.
- Advisors: Quinn, Rowan, Sage and Sarah each have 25 of 40 capacity, matching the overview workload table and the full 100-student population.
- Catalog: 30 course entries in the accessibility tree; requirement groups Core 9 credits / Electives 18 / Capstone 3 total 30 credits. These match the existing degree summary.
- Catalog offer toggles refer to Summer 2027; current list labels should not be interpreted as availability in every term. Summer dates display registration March 29, classes May 25 through August 13; add/drop dates are blank. No dates or offerings were changed.
- Audit log loaded the demo sign-in/sign-out history and event details successfully.
- Overview's one active student measures sign-ins in the last 30 days, not the 100 enrolled student accounts; its explanatory subtitle is present.

Remaining findings for team review:

1. Overview reports email notifications Healthy while Integrations reports Email (SMTP) Off / Not connected. The overview should derive status from the same integration configuration and distinguish configuration from successful delivery. No connection or email was attempted.
2. Workload percentage rounding differs: Overview uses Python round (25/40 -> 62) while Advisors uses JavaScript Math.round (25/40 -> 63). Counts and assignments agree; use one rounding convention for presentation.
3. Catalog list says Not offered without a term in each row; the editor specifies Summer 2027. Consider a visible term qualifier above the list to avoid confusing this with Spring enrollments or Fall approval warnings. Do not invent offerings to remove warnings.

This was a read-only functional/UI inspection apart from ordinary synthetic login/session audit records. No accounts, assignments, capacities, course offerings, requirements, academic records, approval decisions, integration settings or credentials were edited. No exports, messages, imports, publication, commit, push or merge occurred. Automated tests were not rerun because this turn changed documentation only. The previous focused test results remain historical evidence, not a new test run.

## Admin consistency fixes implemented - November 14, 2026

Added authored `risk_mvp/admin_display.py` plus guarded `tools/apply_main_admin_display.py`, called by the team export preparer. The changes are applied to the isolated team demo, preserving the existing API response schema and database configuration.

- Overview email status now checks the same persisted Integration row and connection-state function used by Integrations. Disabled/missing SMTP is Off; connection errors map to the existing Down enum; enabled recent failures are Degraded. Connected without recent failures remains Healthy with explicit wording that delivery is not verified by this status. No SMTP send or configuration change occurs.
- Overview workload uses half-up rounding for nonnegative counts, matching the existing frontend Math.round convention (25/40 -> 63%).
- Course list now identifies Summer 2027 from the existing nextTerm response and clarifies that offered/not offered labels apply to that term. No offerings or dates were changed.

Tests: the first focused run had 48 passes and two failures because older overview tests expected disconnected seed SMTP to be Healthy/Degraded. Updated only those affected assertions/setup in the reproducible export patch: disconnected seed is Off, and the degraded scenario explicitly enables the disposable test integration then restores it. Final focused run: **50 passed in 9.34 seconds**, covering new state/rounding regressions, existing overview APIs, advisor management and integrations. Tests use only the dedicated local `_test` database. Production frontend build passed (existing >500 kB bundle warning).

Live Chrome verification after restarting only the verified local API on 8005 confirmed Overview email Off with disabled-delivery explanation, all four overview workloads at 63%, and the visible Summer 2027 qualifier above the catalog list. No demo settings, academic records, capacity, assignments, offerings or approvals were edited. No frozen artifact changed. No full-suite rerun, commit, push or merge is claimed.
