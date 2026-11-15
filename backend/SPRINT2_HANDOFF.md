# Sprint 2 handoff ? current local candidate

> Publication checkpoint (November 15, 2026): start with [SPRINT2_COMMIT_REVIEW.md](SPRINT2_COMMIT_REVIEW.md) for the fresh pre-push checks and latest-main review boundary. Earlier dated working-tree/package statements below describe their original checkpoint.

Prepared November 14, 2026. Ready for technical review and rehearsal; final team submission approval is pending. This document is the current entry point. Earlier dated reports remain historical evidence.

## Candidate to review

Working branch: feature/academic-risk-prediction. The working tree contains uncommitted implementation and untracked authored files; origin alone does not contain this complete candidate. No commit, push or merge was performed for this package.

The tested integration export is ml/outputs/main-integration/team-review-9dba938-a0c1930, combining main 9dba938da14df8607c81b6f92988e8210977bf24 and Datta a0c19303afbf51eda566b705e9934f6acb157627 with authored local overlays. It is not a merged team release. Li's latest published source revision has not been identified.

Canonical local demo: 105 users, 100 students, four advisors with 25 advisees each, one 30-credit program, 30 courses, 800 enrollments, 100 advisor assignments and three requirement groups. There are 179 active and 621 historical enrollments. Academic observation date is fixed at February 16, 2027; it is not a live feed. UI http://127.0.0.1:5179; API localhost:8005.

## Delivered behavior and evidence

| Contribution | Acceptance evidence | Important boundary |
|---|---|---|
| Student records and shared degree progress | All 100 students checked against CSV-derived credits and identity | Graduation is an estimate with documented pace assumptions |
| Advisor caseload and full records | All four advisors and 100 assigned records; 610 expected permission denials | Attention queue is not a probability-ranked intervention policy |
| Real course inference and readable explanations | 179 active enrollments scored/explained; all 800 audited; fresh model/SHAP smoke passed | Synthetic consistency does not establish institutional predictive accuracy |
| Plan approval, messaging and meetings | Automated persistence/role/validation tests on isolated test DB; 100 live follow-up contexts checked | Working-demo final account audit did not send messages or change approvals |
| Project-document help | Three checked guides, policy abstention and existing AI fallback verified | Lexical excerpt retrieval, not semantic RAG or institutional-policy advice; answers are plain text without source links |
| Shared role presentation | Recorded page-specific visual reviews and frontend checks | Responsive review remains deferred to frontend owners |

Latest full backend checkpoint: 433 passed with advisor defaults globally enabled, zero failures/errors/skips; actual artifact smoke enabled. Evidence: ml/outputs/advisor-defaults-enabled-backend-v2.xml. Latest full frontend checkpoint: 14 passed, zero failures, one explicitly skipped older standalone live-demo test. After removing guide links, the focused presentation test passed and the production build succeeded; the full backend suite was not rerun for that presentation-only change. Existing bundle-size warning remains.

Separate evidence: 52 ML tests, 13 provisioning tests, three optional-explanation-failure tests; seven retrieval foundation tests. Do not add overlapping suites into one total. All-account check: 105 identities, 2,777 HTTP checks, zero failures, 610 expected denials, 100 follow-up contexts (ml/outputs/team-e2e-final-v2.json). These are HTTP checks, not a browser test of every action. Original CSV bytes and working-demo academic fingerprint remained unchanged.

## Source and artifact handoff

Review authored risk adapters, knowledge modules, frontend components, overlay/preparation tools, validators, tests and documentation. Use git status to select files individually; do not stage the entire tools/ or tests/ tree without inspecting its contents. Some runtime frontend changes are applied by tools to the ignored export: send the reviewed overlay/preparer sources as well as the component sources. Do not send only the ignored export or assume a branch name identifies uncommitted changes.

Exclude ml/outputs, virtual environments, generated audits, temporary files, credentials, .env files and model binaries from Git. Existing model/reference ZIPs and the tested venv are ignored. Preserve frozen models, calibration maps and original CSV records.

Share these trusted packages separately, retaining filenames:

- ml/outputs/handoff/acadmate-frozen-artifacts-v1.zip ? SHA-256 0cedcdb50402612df878415360cf13e1423063d595b4b2cb15ba5a097a5a9c30
- ml/outputs/handoff/acadmate-explanation-references-v1.zip ? SHA-256 0ae567ee6d1f5627e856209a064b80cd988b3a239b9591629558423aa4582ee2

Use ML_ARTIFACT_SETUP.md and ML_EXPLANATION_SETUP.md for exact installation, checksum verification, fresh environment and smoke commands. The second package and reviewed loader source are needed for portable explanations. Use the combined candidate requirements plus ml/requirements-shap.txt; do not combine conflicting standalone backend pins. No retraining or original OULAD training tables are needed for inference handoff.

## Review ownership and release gates

1. Li: exact source candidate, explicit-column queries, auth/errors, real inference, optional explanation failure, cache invalidation and existing API regression. Confirm setup on his machine.
2. Datta or available database reviewer: identifiers/crosswalk, canonical population and additive risk-table migration/import contract. No shared migration is authorized by this document.
3. Frontend owner: shared role components and overlay adoption. Responsive work remains theirs.
4. Product owner/tester: agree story acceptance statuses, rehearse DEMO_WALKTHROUGH.md and update team presentation/manual using SPRINT2_PRESENTATION_UPDATE.md.
5. Agree final source revision and submission branch. Review files and secrets before any separately authorized commit/push. Obtain peer acceptance; do not merge automatically.

## Backlog disposition for team acceptance

Implemented local contribution: S2-02 advisor review; S2-03 plan workflow; S2-04/05 shared academic summaries; S2-06 temporal features; S2-07 frozen inference; S2-09 explanations. These are local technical acceptance claims, not unilateral Jira closure or acceptance of every teammate-owned story.

S2-08 remains partial: numeric outreach thresholds/capacity policy is unapproved. S2-10 has a bounded project-help demonstration; institutional sources and semantic retrieval remain pending. PB-07 existing follow-up entry points/persistence are supported; intervention outcome tracking is not delivered. Live Brightspace, actual external provider delivery, institutional model validation and deferred responsive work remain unverified/future scope. The full product backlog is not complete.

No new feature, academic policy, frozen-model change, shared database import, commit, push or merge was introduced by this documentation checkpoint.

## Advisor availability checkpoint

Weekday 08:00?17:00 defaults are enabled in the guarded team host. Custom schedules/preferences and explicit clears are preserved; existing booking conflicts/lead time remain enforced. See ADVISOR_DEFAULT_HOURS.md. Focused scheduling: 28 passed. Final full backend: 433 passed, zero failures/errors/skips, in 134.54 seconds, real-model smoke enabled. A discovered existing-appointment conflict was fixed and the unchanged regression passed. Intermediate failed evidence remains retained separately.

Final all-account run after the correction: 105 accounts, 2,777 HTTP checks, 610 expected denials, 100 follow-up contexts, zero failures; same academic fingerprint and unchanged CSVs. Evidence: ml/outputs/team-e2e-default-hours-v2.json. The launcher now selects the tested handoff-venv-v1 environment and fails clearly if it is missing. It does not rebuild the database.

Final cross-role availability verification passed: all four advisors and all 100 student booking views agree on next-day open-slot counts, each student can discover their assigned advisor, weekday time bounds hold and weekends have no default slots. Evidence: ml/outputs/advisor-default-hours-live-v3.json. No bookings were created. Overlay reapplication is byte-identical.

## Population-wide workflow and packaged-source checkpoint

See SPRINT2_DEMO_READINESS.md for final scoped results. A separate full-population clone passed 2,000 write-workflow checks for all 100 students, including booking/conflict/cancellation, messaging round trips and plan changes/resubmission/approval. This leaves the presentation population unchanged. Fresh all-population model/narrative audit passed for 179 active enrollments. Final frontend: 14 passed, one older standalone live test skipped, production build passed. ML/provisioning/retrieval: 72 passed plus four subtests; dataset: 16 groups and 31 tests passed. Packaged backend: 105 real synthetic logins and 179 actual explanations, 694 HTTP checks passed. Do not combine these scopes into a single total.

Source-only package assembly uses tools/build_sprint2_handoff.py, with per-file provenance and SHA-256, explicit runtime/credential/model exclusions and frozen source hashes. Original model and explanation-reference ZIPs remain separate. It is a review snapshot including uncommitted work, not a pushed branch or self-installing database distribution. Native PowerPoint/Word originals remain unchanged while document access is pending.
