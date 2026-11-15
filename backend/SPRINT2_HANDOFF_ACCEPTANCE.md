# Sprint 2 end-to-end acceptance before handoff

> Current checkpoint (November 14, 2026): see [SPRINT2_HANDOFF.md](SPRINT2_HANDOFF.md) for the reconciled status. Later evidence supersedes older pending/count statements below: 433 full backend passes with advisor defaults enabled; 14 full frontend passes with one older live test skipped; final plain-text UI change passed its focused test/build. Project-help retrieval is delivered for checked project guides only, with no displayed guide links. Institutional-policy retrieval, S2-08 policy approval and team release acceptance remain pending. Earlier dated evidence is retained.

Checkpoint: November 14, 2026. Working branch: feature/academic-risk-prediction. Scope baseline: user-confirmed slides 23-28 in the Sprint 2 deck. This is acceptance evidence for the pinned local combined candidate, not a claim of live institutional integration, a merged release or completion of every broader product story.

## Candidate and dataset

- Main source: 9dba938da14df8607c81b6f92988e8210977bf24.
- Datta source: a0c19303afbf51eda566b705e9934f6acb157627, with authored reviewed local overlays.
- Export: ml/outputs/main-integration/team-review-9dba938-a0c1930.
- Running frontend/API: localhost 5179 -> 8005.
- Synthetic demo: 100 students, 105 users, four advisors, 800 enrollments, 30 courses, one 30-credit program and three requirement groups. All four advisors have 25 students. Fixed demo observation date: February 16, 2027.
- Dedicated destructive regression target: only acadmate_risk_demo_main_sprint2_test on localhost:55439. Working demo academic tables were not rebuilt.

## Current local acceptance evidence

| Expected functionality | Verification and result | Boundary |
|---|---|---|
| Sign-in, identity and logout | Every one of 105 synthetic identities passed role/identity checks through the frontend proxy; logout rejected subsequent auth/me access. Existing 30 authentication regression cases passed. | External OAuth and real recovery-email delivery not exercised. |
| Student dashboard, courses and assignments | All 100 students loaded their dashboard, courses, assignments and events through authenticated HTTP. | GET workflow checks do not reproduce every browser interaction. Writes/validation are covered in the dedicated test DB suites. |
| Degree progress | All 100 serialized degree-progress results matched independently computed CSV requirement credits and identity. Degree-audit and plan routes loaded for all. | Existing documented GPA/pace assumptions are implementation/demo behavior, not institutional policy approval. |
| Advisor caseload, reports and records | Four advisors have exactly their assigned 25 students; all 100 records match student/user identifiers. Prior population audits confirm dashboard/list/report attention counts 22/20/20/23. | Attention rules are not a validated probability-based intervention policy. |
| Message recipient and meeting context | All 100 assigned students were found via exact-name contact search with the correct user ID; free-slot lookup accepted the correct student ID. Record/list link implementations use these respective identifiers. | Contacts intentionally return at most 20 unfiltered results. Initial verification incorrectly assumed an exhaustive unfiltered list; corrected the verifier, not production permissions. No live message or meeting was submitted. |
| Messaging persistence | Existing 17 messages regression cases and three advisor messaging cases passed, including reply/read/unread/contact/authorization behavior. | These actions use the isolated seeded test DB, not all 100 live demo accounts. No real outbound communication was sent. |
| Meeting persistence | Existing 14 meeting and seven advisor meeting cases passed, including booking, student visibility, conflicts, concurrent slot protection and role restrictions. | External calendar/video delivery is outside local acceptance. |
| Plan submission and advisor decision | Nine plan and six cross-role approval regression cases passed; frontend returned-feedback/approved-state workflows passed. Approval prechecks/warnings preserved. | No existing full-population demo approval was changed during this final account audit. Approval does not confirm offering availability or registration. |
| Real risk inference and explanations | Fresh environment and fresh source/artifact layout smoke passed. Newly recreated four-advisor audit checked all 800 enrollments: 179 active courses scored/explained; 621 historical courses unavailable/unscored as intended. | Synthetic software consistency is not predictive accuracy or intervention effectiveness. |
| Missing data, stale results and failures | Existing cache, temporal/source coverage, optional-explanation and real-artifact HTTP smoke checks passed. Missing coverage never becomes zero, invalidated results are not reused, missing model artifacts return safe 503, optional explanation failure preserves a valid estimate. | This uses explicit test scenarios; the fixed full-population demo has complete coverage for active-course scoring at its chosen date. |
| Role and assignment boundaries | Final all-account HTTP run handled 610 expected denials (student/admin/advisor boundaries, every cross-advisor student record and logout checks). Backend smoke also checks protected risk routes. | No institutional identity provider or production penetration assessment is claimed. |
| Admin population and catalog | Admin user list returned all 105 accounts. Overview, advisor management, catalog courses/requirements/terms, AI settings/flags, integrations, audit and settings GET routes succeeded. Existing admin create/update/import/publish/validation tests passed within the 418-case regression. | No admin account, catalog, requirement, assignment, credential or integration configuration was changed on the working demo. |
| AI guidance/fallback | Existing 14 AI regression cases passed and context/thread GETs loaded for every student. | This does not prove a live Claude request or approved-document retrieval. Retrieval remains unimplemented/unaccepted in this scope. |

## Actual counts and evidence locations

Final running-demo account audit: **passed**, 105 accounts, **2,777 HTTP checks**, **610 expected access denials**, **100 follow-up contexts**, zero failures. Counts include login/logout and expected-denial requests, not 2,777 successful feature actions. Evidence: ml/outputs/team-e2e-final-v2.json. The earlier v1 evidence remains preserved; four advisor checks stopped because the verifier incorrectly treated the contact-picker's first 20 results as exhaustive. Every student/admin account passed that first run. Corrected v2 queries each intended contact by name and uses pageSize=200 for a complete admin user listing.

Academic fingerprint before/after: 7aa14cfe2e488d1c6de389d2eec6c686b60f632d31a0e64e3a6ca0b35f885d7c. All original academic CSV byte hashes unchanged. Authentication produces ordinary local session/audit activity. No academic mutation endpoint was invoked by the final all-account verifier.

Existing current regression evidence (no application changes since that run):

- Full combined backend: **418 passed**, zero failures/errors/skips in 116.70 seconds, fresh isolated Python environment, real-model HTTP smoke enabled. JUnit: ml/outputs/handoff-check-fresh-env-v1/backend-results.xml.
- ML: **52 passed**; provisioning: **13 passed**; optional explanation failures: **3 passed** in the fresh environment.
- Frontend: **13 passed**, zero failures, one explicitly skipped older standalone live demo. Current combined-app live inference panel passed. Production build passed with the existing bundle-size warning.
- Population narrative assertion: passed for all **179** current explanations and 100 students, zero skipped. Evidence inputs were freshly recreated in ml/outputs/population-narrative-check-v1/.
- Fresh dependency install, pip check and actual frozen inference/SHAP smoke passed. Source/artifact layout: ml/outputs/handoff-check-fresh-env-v1/. No original training CSV copied and no frozen model refitted.

These suites have different scopes. Do not add their counts together into one acceptance metric. The new final verifier is HTTP integration, not a new full visual review. Earlier page-specific visual findings and deferred responsive work remain in TEAM_INTEGRATION_REVIEW.md.

## Reproduce the final running-demo check

Start only the already verified local team demo using its documented launcher. Then from repository root, choose a NEW output filename:

```powershell
.\ml\outputs\handoff-venv-v1\Scripts\python.exe tools/verify_team_end_to_end.py `
  --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930 `
  --output ml/outputs/team-e2e-final-new.json
```

It refuses unexpected snapshot/database provenance and existing output files. The target is intentionally the local synthetic app, not an arbitrary URL or shared database. See ML_EXPLANATION_SETUP.md for fresh environment, model/reference provisioning, narrative recreation and regression commands.

## Handoff decision

The implemented local core workflow has current passing acceptance evidence and is suitable for technical handoff/review with the boundaries above. It would be inaccurate to say every broader backlog item is complete.

Explicit carryover/unverified boundaries: live Brightspace mapping, real OAuth/provider delivery, approved-document retrieval (S2-10), approved outreach thresholds/capacity policy (S2-08), intervention outcome tracking, institutional model validation, deferred responsive visual work, teammate-machine execution and agreement on the canonical submission commit/dataset. Do not silently change these into completed items or add new implementation scope as part of acceptance.

Before calling the team submission final: reconcile the deck's old Amara/36-credit/eight-advisee example and obsolete missing-artifact/SHAP claims with the selected candidate; obtain normal peer review and explicit source/dataset agreement. Local verification does not authorize a merge or shared migration. No commit, push, merge, external message, shared database import or frozen model change occurred.
