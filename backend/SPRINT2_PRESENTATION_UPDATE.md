# Sprint 2 presentation and manual update text

Prepared November 14, 2026 for the team editor. This is replacement content/checklist; the PowerPoint and Word originals have not been edited. Baseline: user-confirmed deck slides 23?28. Keep dated historical results intact and add current results separately.

## Current contribution ? slide-ready text

AcadMate now connects the synthetic academic population to a complete advising workflow. Students see degree progress and advisor feedback. Advisors review their assigned students, understand course-level concerns through concise explanations, and use existing messaging, meeting and approval workflows to choose a next step.

The backend invokes the unchanged frozen OULAD model and calibration artifacts. All 179 active enrollments in the 100-student demonstration were audited with real inference and explanations. The 621 historical enrollments remain unscored. Checked project guides also provide short answers about application workflows. Synthetic results demonstrate software behavior, not predictive accuracy on institutional students.

## Validation ? slide-ready text

Full combined backend: 433 passed with advisor defaults enabled, zero failures/errors/skips. Weekday 08:00?17:00 default hours support booking unless an advisor adjusts their schedule. All-account acceptance: 105 identities and 2,777 HTTP checks, zero failures, including 610 expected access denials. Full frontend checkpoint: 14 passed, one older standalone live test skipped; the final plain-text presentation change passed its focused test and production build. Fresh environment, frozen-artifact verification and actual inference/SHAP smoke passed.

## Remaining work ? slide-ready text

Team acceptance of the exact submission candidate and dataset is pending. Operational intervention thresholds, institutional-policy retrieval, live external services, institutional model validation and responsive review are separate pending scope. Brightspace is an intended source; the MVP uses synthetic academic/LMS observations. Existing follow-up workflows do not establish intervention outcome tracking.

## Editor checklist

- Slides 10, 15, 28, 33, 35, 39, 40 and 48: replace current-tense missing-artifact/inference/SHAP claims with the dated current result; preserve older failure evidence as historical.
- Slides 23, 27, 30?31, 34, 41 and 44?47: reconcile Amara/36-credit/eight-advisee examples with the selected local Santos/30-credit/25-per-advisor candidate. Do not relabel an old fixture as a different student. Current Santos: 21 completed, three in progress, six left after term, estimated December 2027.
- Slide 46: do not label this local export a merged submission branch. Record the final team-approved source revision when selected.
- Update architecture diagrams to show academic/LMS observations -> temporal features -> verified frozen model/calibration -> optional explanation -> FastAPI -> advisor UI. Show trusted artifact provisioning separately. Do not draw a live Brightspace connection as implemented.
- Manual: use the combined candidate dependency instructions, both trusted artifact packages, plain-text project-help behavior and the documented synthetic observation date. Never include real credentials or generated model binaries in source instructions.
- Replace current screenshots only after rehearsal on the selected candidate. Match names, credits and counts across every screenshot and slide.
- Backlog: mark S2-08 partial and S2-10 bounded project help unless the team explicitly accepts that scope. Do not mark the broader product backlog complete from these checks.

Review and apply this text with the presentation/manual owners. Source package selection, teammate verification and the actual final slide/manual edits remain release tasks, not completed by writing this document.

## Final population acceptance addition

All 100 students completed booking/conflict/cancellation, a message/reply round trip, and plan changes requested, resubmission and approval on a separate test clone: 2,000 checks passed. The presentation database remained unchanged. All 179 active-course explanations passed a fresh population audit; final frontend regression passed 14 tests with one older standalone live test skipped. ML/provisioning/retrieval suites passed 72 tests plus four subtests. Keep these distinct from the 433-case backend regression and 2,777 live HTTP checks.
