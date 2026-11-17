# Sprint 2 expanded workflow implementation — 2026-11-04

Branch: feature/academic-risk-prediction. Core local database-to-model/API/frontend workflow implemented. Shared databases, original academic CSVs, backend/models.py, frozen ML modules/artifacts, and previous reports remain unchanged. No commit, push or merge.

## Implemented

- Eight namespaced additive SQLAlchemy tables and PostgreSQL DDL prepared separately for Datta review.
- Deterministic sidecar generator (seed 20261104) and guarded loader/bootstrap for a new checkout-owned loopback PostgreSQL cluster, not the existing PostgreSQL service.
- Read-only repeatable-read API transactions; as-of course timing, latest known assessment/submission versions, source coverage and eligibility checks; exact existing 16-feature function.
- Actual saved logistic-regression/sigmoid inference with unchanged integrity verification, not constants or retraining.
- Academic insights matching the current profile's GPA/credits calculation, plus failures, withdrawals and active courses. No academic policy is invented; current snapshot metrics are labeled separately from historical prediction cutoff.
- Assessment completion, overdue counts, recent activity and released scores as supporting descriptive evidence; scores remain excluded from the model.
- An isolated advisor page at /advisor/academic-risk with student selection, UTC cutoff, active enrollments, predictions, coverage, academic evidence, warnings, loading/error states and unavailable responses.
- Existing fixture API preserved and regression-tested. New database router registered alongside it in main and the independent research-demo host.

## Data generated and loaded only locally

Original data: 100 students, 800 enrollments, 179 active enrollments. All 100 students are represented among active enrollments.

| Additive table | Records |
|---|---:|
| risk_course_offerings | 103 |
| risk_enrollment_offerings | 800 |
| risk_assessments | 210 |
| risk_assessment_versions | 210 |
| risk_submission_versions | 2,188 |
| risk_activity_events | 8,445 |
| risk_source_coverage | 6,444 |
| risk_enrollment_history | 800 |
| Total | 19,200 |

Patterns among active enrollments: high 37, moderate 37, declining 18, late 26, missed 20, improving 18, feed gap 23. These are construction patterns, not risk labels or evaluation targets. UTC dates, 112-day offerings, variable synthetic grading times and calendar checkpoint coverage are explicit demo assumptions. Existing final academic records are preserved rather than rewritten to match patterns.

## Actual validation

- 41 original ML regression tests: PASS.
- 14 backend/API/PostgreSQL tests: PASS, including the original six API tests and real-artifact smoke test.
- Two Node frontend helper tests: PASS.
- Production frontend build: PASS on Vite 8.3.5.
- npm audit after the non-major Vite security patch: zero vulnerabilities (full audit); final production-only audit also clean.
- pip check: no broken requirements.
- Deterministic generation twice: identical bundles.
- Fresh seed into second disposable acadmate_risk_demo_verify database: PASS. Nonempty overwrite refusal: PASS.
- PostgreSQL foreign-key rejection and transaction read-only enforcement: PASS.
- Hand-calculated 7/14/28-day click windows, distinct active days, engagement change, submission timing, overdue work and lateness: PASS.
- Post-cutoff activity, late-arriving historical activity, future schedule revisions and score changes cannot change earlier features: PASS.
- Missing activity coverage suppresses probability while preserving reliable assessment evidence: PASS.
- Frozen code hashes and original academic CSV hashes verified unchanged.

The tests exposed UTC/session-timezone conversion and explicit-ID sequence issues; both were corrected and rechecked on a fresh local database. Academic-summary tests compare against the actual existing profile behavior rather than assuming policy or fixed credit totals. Temporary test mutations are rolled back.

## HTTP/proxy integration

Verified through frontend port 5175's proxy to API port 8002 and the disposable PostgreSQL cluster on 55439:

- /students returns 100 synthetic students.
- Student 10001 returns one active course plus academic insights.
- Enrollment 20024 at cutoff 2027-02-08T23:59:59.999999Z returns scored_research_demo, day 28, actual probability 0.2169211773909568.
- Enrollment 20014 returns unavailable with null probability due to activity coverage; assessment evidence remains available.
- /advisor/academic-risk serves HTTP 200, and JSX compiles in the production build.

Do not confuse the new generated database case for enrollment 20024 with the older four-case fixture endpoint: they intentionally use different synthetic event inputs and produce different model outputs. The old endpoint's original output remains unchanged.

## Frontend verification limit

Interactive browser QA was attempted with the Computer Use skill. The tool stopped because it could not confidently determine the current browser URL to enforce its policy. No alternate browser-control route was used. Thus production build, helper tests and HTTP/proxy/API integration are verified, but interactive selection/rendering remains a manual verification item. This is not reported as a passed browser test.

## Files created in this implementation

- backend/risk_mvp/__init__.py
- backend/risk_mvp/models.py
- backend/risk_mvp/database.py
- backend/risk_mvp/generate.py
- backend/risk_mvp/service.py
- backend/risk_mvp/router.py
- backend/risk_mvp/bootstrap.py
- backend/migrations/proposed/001_risk_mvp.sql
- backend/tests/test_risk_mvp.py
- backend/RISK_MVP.md
- frontend/src/pages/advisor/AcademicRisk.jsx
- frontend/src/research/api.js
- frontend/tests/research-api.test.js
- This report.

Modified: backend/main.py and backend/research_demo.py (register additive router), backend/requirements-research-demo.txt (PostgreSQL driver/timezone dependency), frontend/src/App.jsx (new isolated route), frontend/src/config/nav.js (advisor navigation entry), frontend/vite.config.js (narrow research proxy), frontend/package.json and package-lock.json (Vite 8.3.2 -> 8.3.5 patch and resolved dependencies).

Generated local-only artifacts: ml/outputs/risk-mvp-v1/bundle.json, disposable PostgreSQL data/logs and frontend/dist. All are ignored and must not be committed. No credential files were created; the local disposable URL has no password and is not a shared connection string.

## Remaining integration boundaries

Datta must review schema names, migration conventions and cross-offering write enforcement before any shared adoption. PostgreSQL FKs enforce identity existence; cross-offering consistency is checked by the generator/importer and read service, not a composite SQL FK in this proposal. No arbitrary ingestion API exists. A future multi-source ingestion writer must enforce these invariants transactionally.

Current MVP supports UTC-only offering calendars, end-of-day cutoff from day 7 until course end, single submission attempts with append-only grading versions and synthetic resource-interaction counts. It does not verify Brightspace event equivalence. Incomplete coverage does not become zero. GPA/credits follow existing code only, not an approved institutional policy. Scores and academic histories are descriptive, not new model predictors.

No new risk models, academic policies, operational thresholds, persisted prediction history, individual explanations or authentication deployment were added. Synthetic inference proves software wiring, not model accuracy. No real held-out test was reevaluated; historical evaluation tests use tiny temporary fixtures.

## Demonstration and next tasks

Follow backend/RISK_MVP.md for exact bootstrap, API, frontend, test and teardown commands. Select student 10001 for scoring and 10000 for a coverage-gap example at the default simulated day-28 cutoff.

Next tasks: manual advisor-page verification; Datta schema/migration review; strengthen database-level cross-offering constraints when shared ingestion is designed; package a trusted artifact bundle for teammates; later independently approve any fallback-model research. Do not reopen the consumed holdout for tuning.
