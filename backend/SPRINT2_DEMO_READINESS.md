# Sprint 2 demo readiness across the population

November 14, 2026. The objective is consistent behavior for any of the 100 synthetic students and four advisors, including clear handling of invalid or unavailable cases. No finite test suite establishes perfection or institutional predictive accuracy.

## Current evidence

| Gate | Actual result | Scope |
|---|---|---|
| Combined backend | 433 passed, zero failures/errors/skips | Defaults enabled, real artifact smoke; dedicated seeded test DB |
| ML and source/artifact tests | 72 passed and four subtests passed | 52 ML + 13 provisioning + seven retrieval tests; no frozen retraining |
| All-account HTTP acceptance | 105 identities, 2,777 checks, zero failures | Real synthetic logins; 610 expected denials; 100 follow-up contexts |
| Cross-role availability | Four advisors and 100 student views agree | Weekday 08:00-17:00 defaults, overrides, next-day slots, weekends empty |
| Full-population write acceptance | 100 students, 2,000 checks, zero failures | In-process HTTP on a separate full-population clone, identity dependency override; external mail blocked |
| Current course explanations | 100 students and 179 active enrollments passed again in the refreshed final audit | Real frozen inference/SHAP, source facts and narrative consistency; 621 historical courses unscored |
| Frontend | Final full result 14 passed, one older standalone live test skipped | Current combined live panel passed; plain-text help change passed focused test and build |

The full-population write check exercised for every student: advisor booking, duplicate-slot conflict, student visibility, cancellation, student message/advisor reply, eligible course addition, duplicate-course rejection, plan submission, duplicate submission rejection, advisor changes requested, student feedback, resubmission, approval and feedback clearing. All 100 completed the plan sequence. No original enrollment/grade/CSV records were rewritten. This does not mean every combination of dates, topics, courses, failures and input strings has been tested.

Test clone: acadmate_risk_population_acceptance_v1_test, loopback port 55439 only. The presentation database acadmate_risk_team_review_sprint2 retained its academic fingerprint and all CSV byte hashes. The clone contains synthetic test messages and decisions only; do not package its dump, sessions, logs or database files. Authentication was overridden only inside this write harness; actual account login/logout/role checks were tested separately through the running proxy. Existing regression tests cover unassigned actions and concurrent slot protection.

Evidence: ml/outputs/population-write-acceptance-v1/results.json, ml/outputs/team-e2e-default-hours-v2.json, ml/outputs/advisor-default-hours-live-v3.json and ml/outputs/advisor-defaults-enabled-backend-v2.xml. These counts have different scopes and must not be added into a single total.

## What any-case readiness means

An eligible active enrollment can be assessed from its current synthetic observations. Historical/ineligible enrollments and incomplete feeds must stay unscored. A booked/conflicting/too-soon time must be unavailable. A student cannot decide their own request or view another advisor's protected record. A course with missing prerequisites must fail validation. These are intended results, not demo failures to bypass.

The same source files, configuration, artifacts and population must be used to reproduce these results elsewhere. Sharing exact package hashes replaces guesswork about which local edits someone has; it does not authorize a merge or eliminate peer integration review. No new academic or outreach policy is approved by this evidence.

## Remaining presentation and delivery work

Current behavior is ready for technical handoff and rehearsal. Update the historical deck/manual examples and show a coherent student/advisor record. Real provider delivery, live Brightspace, institutional-policy retrieval, intervention outcome tracking, numeric intervention thresholds and deferred responsive work remain separate scope. Native PowerPoint/Word copies require the document connection/runtime and visual verification; update text is prepared but is not a claim those binaries have been edited.

Use the existing approved-plan state for a read-only presentation. If demonstrating an actual write, choose a designated synthetic case and be clear that the action changes its local workflow state. Do not reset the whole demo between examples or force impossible dates/eligibility.

Fresh final population evidence: ml/outputs/population-narrative-final-v2, including all 179 real explanations and independent feature/evidence checks. The full frontend suite reran against these inputs and the live combined app: 14 passed, zero failures, one older standalone live test skipped. Production build passed with the existing bundle-size warning.

## Final package verification

The assembled source snapshot passed verification from its own source layout. All 105 accounts signed in through its in-process app, and all 179 active enrollments returned genuine scored responses with available explanations: 694 HTTP checks passed. Academic fingerprint unchanged. This is separate from the live 5179 acceptance and does not claim a new-machine PostgreSQL install.

The package's standalone frozen inference/SHAP smoke passed without training tables, database access, refitting or calibration changes. Model probability for the established fixture remained 0.3783828964249184. Locked frontend dependencies installed offline and the packaged production frontend built successfully. A missing DATABASE_URL setting exposed by the fresh layout was fixed in the smoke tool by supplying a nonconnecting placeholder and explicitly forbidding Engine.connect.

Fixed dataset validation also reran: all 16 validation groups passed and all 31 dataset tests passed, with the original counts and seed-preservation checks intact. No synthetic academic record was regenerated.
