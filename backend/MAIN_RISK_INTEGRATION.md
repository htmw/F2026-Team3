# All-enrollment main integration — local Sprint 2 demonstration

Main commit: 8c4b0843368b679ac3f3353f6332c73356888b14. Research branch remains feature/academic-risk-prediction; no branch checkout, merge, commit or push was performed for this work.

## What is connected

The isolated main export keeps its academic seed, authenticated application, degree progress and advisor assignments. An additive risk sidecar is generated for **all 46 enrollments**, belonging to 13 students and 13 courses. This is main's dataset, not a replacement for the preserved 100-student/800-enrollment research dataset.

Eight risk tables contain 21 offerings, 46 enrollment links, 202 assessment identities, 202 assessment versions, 2,830 activity events, 382 submission records, 14,601 daily coverage checkpoints, and 79 simulated status-history records. Generated records are ignored under ml/outputs/main-integration/8c4b0843368b. No original CSVs or frozen model files changed.

Every enrollment gets complete synthetic activity, submission and schedule feeds throughout its course. Patterns depend on a fixed seed and enrollment ID, never recorded names, grades, outcomes or rule-based risk labels. All existing student/course/enrollment IDs are retained. Main student 101 remains Amara; the old Santos research dataset is never mixed into this database.

## Simulation boundaries

The term dates are main's dates, normalized to UTC with inclusive academic end dates represented by next midnight. Assessment schedules, registration timestamps, resource interactions and past active-status trajectories are synthetic. Terminal statuses are placed at simulated course end because actual completion/withdrawal timestamps are not available. This historical replay is not a claim about observed past student behavior. Academic scores are not fabricated; generated submissions carry no grades and the frozen model has no score/GPA inputs.

All 46 enrollments scored at their own simulated days 7, 14 and 28 (138 real-model assessments). At the fixed main demo date, 2026-10-01, 13 enrollments scored and 33 were unavailable because of timing/eligibility. Complete synthetic coverage does not override ended/not-yet-started courses or missing real-world evidence. Missing coverage is still unscored/null.

Eleven students have advisor assignments. Forty-four enrollments can be assessed by their assigned active advisors. Two existing enrollments have no assigned advisor; their activity is generated and internally auditable, but no advisor is granted access. Assigning them later is a separate team decision; this implementation does not invent assignments.

## Authenticated API and UI

New paths, hosted only by risk_mvp.main_host in the isolated main environment:

- GET /api/v1/advisor/research/students — assigned students only.
- GET /api/v1/advisor/research/students/{student_id}/insights — all recorded enrollments, names, original statuses, course dates, and fixed demo cutoff.
- GET /api/v1/advisor/research/enrollments/{enrollment_id}/risk-assessment?cutoff=... — actual unchanged frozen model, existing role and advisor-assignment checks, standard main errors.

The adapter uses main's session authentication and repeatable-read/read-only extraction transactions. All 101 existing distinct API paths are preserved; three are added. This count is paths, not HTTP method/operation count. The isolated research fixture server and earlier CSV pipeline remain unchanged.

The UI overlay adds a research panel to main's existing advisor student-record page. It lists every enrollment, allows one explicit date for a current assessment, and separately offers a labelled day-28 historical replay per course. Rule-based main risk bands remain separate. Each course request has independent success/error handling.

## Reproduce setup

Run from the repository root. Never use a shared database URL. The existing isolated PostgreSQL cluster is in ml/outputs/pg-risk-mvp; start only that cluster on 127.0.0.1:55439 using backend/RISK_MVP.md. This procedure creates acadmate_risk_demo_main_sprint2, never resets another database, and refuses unrelated existing data. Use the existing snapshot below to reproduce the prepared demo; export refuses an existing directory.

```powershell
$repo = 'C:\Users\nhesv\Documents\AcadMate-Team'
Set-Location $repo
$snapshot = Join-Path $repo 'ml\outputs\main-integration\8c4b0843368b'
# For a NEW export directory only:
# .\.venv\Scripts\python.exe tools/prepare_main_risk_demo.py export --snapshot $snapshot --source-ref 8c4b0843368b679ac3f3353f6332c73356888b14
# For a NEW dedicated environment only:
# py -3.13 -m venv "$snapshot\.venv"
$python = Join-Path $snapshot '.venv\Scripts\python.exe'
# Install into that dedicated environment when setting it up:
# & $python -m pip install -r "$snapshot\backend\requirements.txt" -r "$repo\ml\requirements.txt"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python tools/prepare_main_risk_demo.py prepare --snapshot $snapshot
& $python tools/prepare_main_risk_demo.py audit --snapshot $snapshot
& $python tools/verify_main_risk_demo.py --snapshot $snapshot
& $python tools/prepare_main_risk_demo.py frontend --snapshot $snapshot
npm.cmd --prefix "$snapshot\frontend" ci
npm.cmd --prefix "$snapshot\frontend" run build
```

The original frozen artifacts must already be provisioned in THIS research checkout with the earlier verified tool/bundle. The main-only environment installs main's dependency pins plus ml/requirements.txt; do not combine the conflicting old requirements-research-demo.txt with main requirements.

Start the combined API in one terminal:

```powershell
$repo = 'C:\Users\nhesv\Documents\AcadMate-Team'
$snapshot = Join-Path $repo 'ml\outputs\main-integration\8c4b0843368b'
$env:PYTHONPATH = "$snapshot\backend;$repo\backend;$repo\ml\src"
$env:DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_main_sprint2'
$env:ACADMATE_RISK_MVP_ENABLED = 'true'
$env:ACADMATE_TODAY = '2026-10-01'
$env:OMP_NUM_THREADS = '2'
& "$snapshot\.venv\Scripts\python.exe" -m uvicorn risk_mvp.main_host:app --host 127.0.0.1 --port 8003
```

Start the main frontend in another terminal:

```powershell
$env:API_PROXY_TARGET = 'http://127.0.0.1:8003'
$env:VITE_API_URL = '/api/v1'
npm.cmd --prefix 'C:\Users\nhesv\Documents\AcadMate-Team\ml\outputs\main-integration\8c4b0843368b\frontend' run dev -- --host 127.0.0.1 --port 5177 --strictPort
```

Open http://127.0.0.1:5177/login and use main's existing synthetic advisor demo account (see its manual; do not put real credentials in chat). Open Amara's record through Advisees. She has ten recorded enrollments. Current-date assessment shows scored/ended states; day-28 replay shows estimates for all ten, explicitly labelled historical simulations.

Stop API/frontend with Ctrl+C. Stop the isolated PostgreSQL cluster with the existing pg_ctl command in RISK_MVP.md. Generated data and environments remain ignored; no cleanup/drop is required.

## Verification performed

- Existing main backend suite: **353 passed** in 79.63s, exclusively against a separately created acadmate_risk_demo_main_sprint2_test database. Its destructive test fixtures never ran against the integration database.
- Research backend: **28 passed**, including four new generator tests and all prior real-artifact/disposable-database tests.
- ML: **41 passed**; toy training-unit fixtures do not retrain the frozen model.
- Cohort audit: **46/46 scored at each day 7, 14 and 28**; probabilities ranged 0.16285873090327113–0.9409651876215805. This validates software flow, not accuracy.
- Actual main-session API checks: **44 authorized enrollment scores**, **94 cross-assignment denials**, unauthenticated 401, student/admin 403, invalid input 422, unknown enrollment 404, missing activity coverage unscored/null, missing artifacts safe 503; missing-sidecar enrollments stay visible and unscored. Academic snapshot fingerprint remained identical.
- Main frontend production build: passed, with pre-existing large-chunk warning.
- Live React/JSDOM test through main Vite proxy, real login, PostgreSQL and frozen model: passed; all ten Amara enrollments rendered and both current/replay modes verified. This is DOM integration testing, not an interactive browser review.
- npm audit reported one high-severity Vite package finding in main's pinned Vite 8.3.2. No automatic package upgrades were applied. The frontend owner should review it before broader deployment.

Machine-readable local evidence: risk-main-manifest.json, risk-main-audit.json, risk-main-api-verification.json in the ignored snapshot directory. No claim is made about deployment to shared infrastructure or predictive validity on institutional students.

## Authored deliverables

- backend/risk_mvp/main_data.py: deterministic all-enrollment generation, provenance and guarded sidecar loading.
- backend/risk_mvp/main_router.py: assigned-advisor API with read-only extraction and complete enrollment listing.
- backend/risk_mvp/main_host.py: dedicated-main-database guard and additive router registration.
- backend/tests/test_main_risk_data.py: deterministic generation, complete linkage, outcome independence and validation tests.
- frontend/src/components/research/MainResearchRisk.jsx: main-only all-enrollment panel.
- frontend/tests/main-research-risk.test.js: opt-in live main panel verification.
- tools/prepare_main_risk_demo.py: export, prepare, audit and isolated frontend overlay commands.
- tools/verify_main_risk_demo.py: real-session API, authorization and failure-mode verification.
- backend/MAIN_RISK_INTEGRATION.md: this report and setup guide.

Existing provisioning work remains separate. No original frozen sources/results, academic CSVs, main checkout files or branch history were overwritten. The source branch's original frontend has 7 passing offline tests and one intentionally skipped legacy live-server test; its production build passed. Six provisioning tests passed and the model/calibration hashes remained unchanged.

## Remaining team review

Datta: confirm simulation boundaries, eventual ingestion/migration ownership, and whether to assign the two currently unassigned enrollments. Li: review the authenticated adapter and main dependency combination. Frontend owner: review styling/accessibility in an interactive browser and Vite dependency finding. Preserve eligible_courses_ids in main for now; this integration does not import the older program_requirements.csv or rename shared columns.


## Completed interactive desktop review

Reviewed the polished advisor panel in the actual Chrome desktop window at http://127.0.0.1:5177/advisor/advisees/101. The previous browser-policy interruption was resolved by a fresh session and raising the Chrome window; no browser security protection was bypassed.

Verified visually:
- Main academic summary stays above the research panel, with GPA 3.73 and 21/36 credits unchanged.
- Prediction target explicitly says failure or withdrawal and retains synthetic/OULAD limitations.
- Three active courses appear first; seven historical enrollments start collapsed and expand/collapse correctly.
- Selected-date mode (1 October 2026, course day 38) shows CS608 31.5%, CS661 65.2%, CS675 23.5%.
- Supporting data for CS608 expands to show 28 resource interactions, one active day, five due assessments, four submissions, one overdue assessment, 80.0% completion and 0.0% lateness. All three feed coverage labels show complete through 1 October 2026 UTC. Descriptive evidence is explicitly not a model explanation.
- Historical replay is labelled distinctly at the panel and card level; current-course replay uses 21 September 2026, course day 28. Historical courses display their own readable cutoff dates and estimates.
- Changing the date from 1 to 2 October clears estimates and changes the mode back to selected-date assessment. Restoring 1 October and assessing again restores the expected selected-date results, without stale replay labels.
- No desktop clipping or overlapping controls observed in the reviewed panel. This is desktop verification; a mobile/narrow-viewport review was not completed.

Demo remains running on localhost and Chrome is left on Amara's selected-date assessment. No source code, frozen artifacts or database schemas changed during this review. Integration and provisioning work remains uncommitted; no push or merge occurred.


## Optional SHAP integration follow-up

The main-only advisor endpoint now accepts include_explanation=true and the panel requests it. The declared preceding-week reference uses day 35 for the default day-38 assessment. Predictions remain available if explanation dependencies or verified backgrounds are missing. See ../ml/reports/SHAP_STAGE_INTEGRATION.md for the actual 685-case audit, optional API contract, setup commands and reference-provisioning limitation. This is subsequent work; the earlier completed desktop review did not cover the new expanded SHAP section.


### Dashboard clarity overlay

Apply `python tools/apply_main_dashboard_review.py --snapshot ml/outputs/main-integration/8c4b0843368b`. The overlay copies the authored MainAdvisorDashboard component into the isolated export and applies guarded changes to its advisees service. It does not change main checkout modules, database records, approval rules, ML models, or prediction thresholds.

Student concerns precede approvals; the preview states its shown/total count; High/Medium badges are hidden on concern cards. Administrative categories remain separate from model probabilities. Missing sign-in history is described as unknown; known inactivity explicitly refers to AcadMate. Contact dates use recorded direct messages or completed meetings, not merely elapsed confirmed appointments. A recorded message does not establish a student reply.

Validation: 28 focused tests passed (dashboard, advisees, approvals and two new evidence regressions), frontend production build succeeded with the existing bundle-size warning, and desktop Chrome inspection confirmed the new layout. Remaining work: unify the existing assignment evidence with the separate simulated LMS records before adding model-derived summaries to the dashboard. Sidebar Advisees badge still represents students flagged for review, rather than total caseload; its explanation remains a UI follow-up.


### Shared deadline evidence and sidebar follow-up

The sidebar now explicitly says `N to review`. In the opted-in dedicated main demo, `risk_mvp.main_attention.align_context` replaces the original assignment overdue count with coverage-checked data from the same `service.extract` used by course inference. It applies to shared advisees context, so badges, dashboard, advisees and reports read the same counts. GPA, plan, request, login rules and approval decisions remain unchanged. No probabilities are aggregated into student-wide risk categories.

The additional descriptive evidence field `overdue_last_14_days` counts outstanding non-exam, non-banked assessments due on the selected UTC date or the preceding 13 calendar days, using only definitions and submissions known at cutoff. It is not a model feature. The course model still uses its original cumulative overdue feature; its observation window differs deliberately from the existing dashboard two-week check. Missing/ineligible coverage leaves the dashboard overdue total unknown, never zero or a partial sum. No fallback to unrelated assignment records is used within this opted-in demo. Outside the dedicated demo DB the adapter makes no changes.

Verify with the isolated Python environment: `python tools/verify_main_attention.py --snapshot ml/outputs/main-integration/8c4b0843368b`. Actual checks: 10 active enrollments / 8 assigned advisees matched shared extraction; badge and dashboard both reported 5 students for review; transaction read-only and model loading prohibited. Tests: 2 aggregation checks, 28 existing dashboard/advisees/approval/evidence regressions and 3 frontend checks passed; production build passed (existing bundle-size warning). Chrome inspection confirmed `5 to review` and `Showing 3 of 5`.

Remaining integration boundary: existing main assignment pages still display their own coursework/advising items. These have no crosswalk to the independently generated simulated risk assessments and are not claimed to be identical. A production LMS adapter or reviewed identifier mapping is required before unifying those pages. No records were merged, regenerated or imported.


### Advisees follow-up

Apply `python tools/apply_main_advisees_review.py --snapshot ml/outputs/main-integration/8c4b0843368b` after the dashboard overlay. Attention is now independent of graduation: `Needs attention` filters on the existing non-Low rule flag, `On track` (displayed as `No current flags`) filters Low flags, and `Graduating` remains a separate overlapping filter. API label values and response schema remain unchanged. Counts and sorting use the same filter predicate. Graduating students with flags show both badges. Existing record, message and meeting links remain unchanged.

The search bug was a PageHeader prop mismatch: a React element was passed where search configuration was expected. The overlay supplies the controlled value, callback and visible `Search students…` placeholder. The existing debounce and URL query handling remain intact.

Validation: 30 backend regression tests passed including two new overlapping-filter/search/sorting tests; production build succeeded with existing bundle-size warning. Seeded main's no-flags count expectation is deliberately updated from 3 to 4 because a Low-flag graduating student is now also included; graduation counts are not intended to sum with attention/no-flags. Live read-only verifier additionally checks badge/dashboard/filter agreement and flagged graduates. Manual Chrome verification of the latest changes was blocked by a minimized window; no completed visual check is claimed.


### Automatic assessment view (no advisor date controls)

The course panel automatically requests the server-defined demo snapshot, then scores active enrollments only. Historical courses remain collapsed without current predictions. Date input and displayed cutoff labels are removed. Refresh assessment remains available; refresh also occurs on focus, visibility restore, reconnect and every 60 seconds. Previous results clear before refresh, on offline/hidden state, and when moving students; aborted/superseded requests cannot populate the new view. Snapshot and supplied identity mismatches become unavailable rather than showing a result. Incomplete source coverage remains governed by backend extraction, not imputed to zero. Authenticated demo research responses carry `Cache-Control: no-store, private`.

This is polling, not transactional live push: a source update can take up to the next refresh to appear. There is no claim of instantaneous freshness or predictive correctness. Current refers to the explicitly configured synthetic demo day (2026-10-01), not the wall-clock date or a real LMS feed. A production data adapter needs source freshness watermarks and change notifications before offering a stronger freshness guarantee. No model, calibration map, feature definition or database record was changed by this UI refinement.

Validation: all 3 UI tests passed, including real-artifact automatic scoring, absent date controls, offline clearing, wrong-snapshot rejection and student-switch clearing. Production build passed after correcting a Windows text-encoding issue; the existing chunk-size warning remains. Live HTTP check verified the no-store response header.


### All-advisor consistency audit

Run `python tools/verify_all_advisor_journeys.py --snapshot ml/outputs/main-integration/8c4b0843368b` with the isolated environment. Actual read-only audit: 4 advisors (caseloads 8/0/3/0), 11 assigned student records, 41 denied checks for nonassigned student access, 2 students without advisor assignments. Dashboard, sidebar badge, attention/no-flags/graduation filters, name search, record identity and concern summaries agreed for every advisor. Empty caseloads are covered; no model loading was needed. No assignment was fabricated for the two unassigned students.

The audit exposed an existing lazy-write path in the removed on-time-submission statistic. The isolated record overlay now removes that unused calculation and tile from the response, avoiding assignment-row creation while opening records. The audit then passed in a PostgreSQL read-only transaction. All 26 focused student-record, authorization, advisee and shared-summary tests passed after the fix. This is exhaustive for this local synthetic database, not a claim about an unseen shared deployment.


### Twelve-hour assessment refresh policy (supersedes minute polling)

The course panel now polls every 12 hours instead of every minute. Opening/returning to the record checks current source evidence but reuses a valid process-local cached assessment. Cache keys include enrollment, cutoff and explanation mode; the cache is bounded to 256 entries and lives only in the isolated API process. On each request the read-only extractor revalidates features, evidence, eligibility and coverage; a changed signature invalidates the saved result immediately on that request. Source changes are detected on requests, not via database push notifications. Model inference and explanation are reused for up to 12 hours. An explicit `force_refresh=true` query parameter powers the existing manual Refresh assessment button. Authorization still precedes any cache lookup.

Unavailable/failed results are not cached, and expired/changed entries are removed before recalculation; there is no stale-on-error fallback. Browser responses remain no-store. The process cache is not a background scheduler: when nobody has the page open, the next request refreshes an expired result. API restart also resets the cache. Demo dates and frozen model/calibration remain unchanged.

Validation: 4 new cache tests passed (expiry, immutable returned copy, source change, force refresh, failure handling, unavailable results, key separation and capacity); all 3 UI tests passed; production build succeeded with existing bundle warning. Authenticated live-artifact smoke verified identical computation timestamps on reuse, a new timestamp on manual refresh, unchanged probability and no-store headers.
