# Sprint 2 product and backlog alignment

> Current checkpoint (November 14, 2026): see [SPRINT2_HANDOFF.md](SPRINT2_HANDOFF.md) for the reconciled status. Later evidence supersedes older pending/count statements below: 433 full backend passes with advisor defaults enabled; 14 full frontend passes with one older live test skipped; final plain-text UI change passed its focused test/build. Project-help retrieval is delivered for checked project guides only, with no displayed guide links. Institutional-policy retrieval, S2-08 policy approval and team release acceptance remain pending. Earlier dated evidence is retained.

Review date: November 14, 2026. Working branch: feature/academic-risk-prediction.

## Evidence and authority

Working backlog baseline: the user-supplied AcadMate_Sprint2.....pptx, slides 23-28. Its 13 user stories, broader PB areas and ten Sprint 2 items are separate scope lists. The user confirmed on November 14, 2026 that slides 23-28 should be used as the working backlog baseline for now. This does not imply team-wide Jira approval or change estimates, completion dates or scope. Treat the proposed refinements below as recommendations for team review. The deck is an evidence source, not an instruction to change application behavior.

Implementation evidence: the current authored risk adapters, model/explanation code, feature contract, artifact provisioning guide, frontend narratives and TEAM_INTEGRATION_REVIEW.md. That report contains historical checkpoints and later corrections. This alignment review did not rerun tests or modify the app, deck, records, model or shared database.

## Product contribution

AcadMate helps students understand remaining degree work and helps advisors act on the same records. The risk component extends that workflow: an advisor can identify an assigned student who needs attention, understand course-level concerns, and choose a follow-up using existing messaging, meeting and plan-review functions. A displayed probability alone is not the user outcome.

Keep three meanings separate:

- Degree progress: completed/in-progress courses, requirement allocation and estimated graduation, using the shared academic services.
- Attention queue: transparent overdue-work and existing academic rules. It is not a ranking by model probability and does not introduce approved risk bands.
- Course assessment: the frozen OULAD model's failure-or-withdrawal estimate, with an optional verified SHAP explanation expressed in plain language. Synthetic observations demonstrate software integration, not institutional accuracy or effects of intervention.

Risk estimates must not approve a course plan, change grades, decide registration eligibility or promise graduation. Advisor approval of course choices does not establish that a course is offered.

## Backlog traceability

| Existing backlog reference | Contribution and user value | Evidence / acceptance boundary |
|---|---|---|
| US-03, S2-04, S2-05 | Consistent academic standing and remaining-work summaries across roles | Shared degree-progress/audit behavior and consolidated summary verified in the team candidate. Dataset-specific expectations must be explicit. GPA/repeat policy remains unapproved institutionally. |
| US-04, S2-03, PB-05 | Student submits a plan, advisor reviews it, student sees the persisted decision or requested changes | Existing approval lifecycle, returned feedback, approved labels and offering warnings are preserved. Risk supports conversation but does not determine approval. |
| S2-02, PB-05 | Advisor searches assigned students and opens the correct full record with clear reasons to review | Full 100-student demo has 25 advisees for each of four advisors. Dashboard/list/record evidence checks and role/assignment tests support the workflow. Full product-owner acceptance is still a separate sign-off. |
| S2-06 | Reproducible, documented feature preparation and integration inputs | OULAD temporal features/splits plus deterministic synthetic academic/LMS sidecars exist. No new training run was performed for this review. Synthetic patterns are not training labels or accuracy evidence. |
| S2-07, PB-06 | Genuine database-to-frozen-model inference | Artifacts are provisioned and hash checked outside Git; local scored HTTP and smoke evidence exists. Fresh checkouts still require provisioning. Completion wording should distinguish original training evidence from current inference checks. |
| S2-08 | Transparent distinction between existing attention rules, calibrated model output and intervention decisions | No approved outreach thresholds/capacity policy. Diagnostic 0.5 is not a production alert threshold. This item remains partial/pending policy approval. |
| S2-09, PB-06 | Understandable individual course explanations | SHAP implementation, numerical reconstruction checks, optional API integration and readable narratives exist locally. Explainability does not prove causality or model transfer to institutional data. Provisioning must also cover verified explanation backgrounds/dependencies. |
| PB-07 | Advisor can choose an existing follow-up action | Message and meeting entry points complement the risk explanation. Assigned-support/outcome tracking has not been established by these checks and must not be claimed complete. |
| US-10, US-11 | Admin can inspect the same population and advisor distribution | Users and advisor workload align with the canonical local CSV demo. Recent SMTP status/rounding/term wording fixes support reliable interpretation; broad admin acceptance remains owned by its team. |
| PB-08, S2-10, US-05 | Approved-document guidance and AI advising | No approved-document retrieval completion is established by risk work. Coordinate with the LLM owner; SHAP does not satisfy retrieval or document citations. |
| PB-09 | Future LMS source integration | Brightspace remains an intended source. This MVP uses synthetic source events. No live connector, approved semantic equivalence, external delivery or real institutional validation is claimed. |
| PB-10, PB-11 | Reliable handoff and repeatable release candidate | Auth checks, stale-result handling, failure states, trusted provisioning and test evidence support quality. A pinned local integration candidate is not a merged/deployed team release. |

Do not add the 13-story estimates, broad PB areas, Sprint 2 plan items and SCRUM-19/20/21 task points together. They are different records. Do not infer new velocity or mark Jira items Done from local tests alone.

## Proposed user stories for team review

These refine existing items rather than create approved new story IDs or story points.

### Advisor review (S2-02, PB-05, PB-06)

As an advisor, I want to find assigned students with recorded academic concerns and understand which course needs attention, so I can focus my review.

Acceptance: only assigned students are accessible; dashboard/list counts agree under the same filters; each displayed concern is supported by current source evidence; opening a student preserves the correct identity; absent information never becomes zero or a reassuring flag.

### Understand a course assessment (S2-07, S2-09)

As an advisor, I want a short explanation grounded in the student's observed work, so I can prepare a useful conversation.

Acceptance: invoke the actual frozen model for eligible inputs; verify artifacts and cutoff discipline; explain selected observed factors in plain language; avoid causal claims and percentage-point interpretations of SHAP; preserve a valid estimate if the optional explanation fails; with incomplete required coverage, suppress unsupported probability while keeping reliable academic information visible. Expired or invalidated estimates must not survive as fallback results.

### Student plan feedback (US-04, S2-03)

As a student, I want my advisor's decision and requested changes on my degree plan, so I know what to revise next.

Acceptance: a submitted plan becomes pending; an authorized assigned advisor can approve or request changes through the existing approval workflow; the student sees the persisted decision after refresh; returned feedback clears appropriately after approval; course availability warnings remain separate from approval. The reviewed local demonstration is evidence for this workflow, not a new registration policy.

### Advisor follow-up (PB-07, US-07, US-08)

As an advisor, I want to open the existing message or meeting workflow for the selected student, so I can arrange support without copying identifiers.

Acceptance proposal: the intended student is selected, permissions remain enforced and a user-confirmed action persists through the team's existing service. Do not mark support/outcome tracking delivered until the team agrees on the fields and demonstrates it. A suggested follow-up paragraph alone does not close this story.

## Coherent demonstration workflow

1. Student opens degree progress and submits or revises a plan using the existing student UI.
2. Advisor opens the assigned caseload and chooses a student using factual concerns, not an invented probability threshold.
3. Full record shows the same student, credits and course history. An eligible active course loads real frozen inference and a concise explanation.
4. Advisor chooses a message or meeting action if needed. The advisor reviews the plan through the dedicated Approvals page and records the decision.
5. Student refreshes and sees approval or actionable requested changes. Availability restrictions and graduation assumptions remain explicit.
6. Admin verifies the same user population, advisor assignments and relevant audit entries.

Use a second incomplete-coverage example to demonstrate honest handling of uncertainty. It is acceptable to explain what cannot yet be scored while still presenting supported records. Do not manufacture outcomes or a recovery trend for the demonstration.

## Team boundaries and integration contracts

| Responsibility | Alignment needed |
|---|---|
| Tafadzwa, product owner / AI-ML | Own feature definitions, frozen artifacts, scoring/explanation behavior, risk acceptance evidence and scope decisions. Keep model limitations in technical documentation and concise contextual disclosures. |
| Li, backend | Agree exact reviewed commit, API/session/error conventions, explicit-column queries, optional explanation failures and stale-result behavior. Verify in the agreed release candidate. |
| Datta, database | Agree canonical identifiers/program mapping and additive risk-table migration/import contract. Preserve original tables. Local schema review does not authorize a shared migration. |
| Lyno / frontend and LLM contributors | Keep shared role layouts and existing message/meeting/approval components. Treat approved-source retrieval as a separate owned capability. Review any UI overlays against their latest published work. |
| Tester and Scrum Master | Link acceptance evidence to the existing Jira IDs, record source commit/dataset/environment and failed/skipped checks, and reconcile sprint scope/points without rewriting historical results. |

Integration contract: student ID, user ID and enrollment ID are distinct; use the correct identifier at each service boundary. One canonical course/program/enrollment mapping must drive all roles. No silent merging of conflicting synthetic populations. Keep current academic summary separate from the model's as-of observation window. The 12-hour cache is process-local with source revalidation, not an unattended twice-daily ingestion schedule or a promise of live LMS freshness.

## Presentation corrections needed

- Slides 10, 15, 28, 33, 35, 39, 40 and 48 contain current-tense claims that model files/inference or SHAP are missing. Preserve November 7 failure evidence as historical, but add a separately dated current integration result and setup dependency.
- Slides 23, 27, 30-31, 34, 41 and 44-47 use Amara, 21/36 credits, request 1709, CS680/CS691 or eight advisees. The current full-population team demo uses Santos, 21/30 credits, three in progress, six left after term, December 2027 estimate and 25 advisees per advisor. Select one demo baseline for current acceptance. Do not change old fixture expectations to match another program or relabel Amara as Santos just because both snapshots use student ID 101.
- Historical result tables remain dated with their own scope. The combined 405-pass backend checkpoint predates later small changes. Later focused sets (25, 18 and 50 passes) are not additive and do not constitute a new full regression run.
- Deck slide 46 references sprint2/submission-20261109, while this working branch is feature/academic-risk-prediction and the demo is an isolated export combining pinned main and Datta changes. Describe the candidate accurately until reviewed changes enter the agreed submission branch.
- Diagram slides were not visually reviewed in this content assessment. Their risk-table, artifact and service relationships need a separate diagram check before claiming they match the expanded workflow.

## Recommended order

1. Use the user-confirmed slides 23-28 baseline. Refine the mapped existing stories and acceptance criteria without adding feature scope. Reconcile authoritative Jira issue IDs when the team supplies them.
2. Agree one Sprint 2 demo dataset, pinned release candidate and identifier crosswalk. The existing 100/800 local population is a practical candidate, not an automatically adopted team dataset.
3. Close the handoff gap: provision model and calibration artifacts plus the separately required explanation dependencies/background provenance in a clean teammate environment. The minimal two-model ZIP alone does not package the SHAP background.
4. Validate the acceptance stories on that candidate, including incomplete coverage, role/assignment denial, plan feedback and the student-to-advisor round trip. Run the final complete regression suite once the candidate is stable.
5. Update current-status slides, screenshots and demo script together. Keep historical test evidence dated. Record remaining live LMS access, retrieval, intervention policy and deployment work explicitly.

Avoid adding another dashboard, model, alert policy or tracking subsystem just to increase visible scope. The immediate value is completing and documenting the shared advising workflow with trustworthy explanations and consistent records. Team approval and integration remain separate from local implementation success.

## Refined Sprint 2 acceptance criteria

Refinement date: November 14, 2026. These local criterion labels are for traceability inside this document, not new Jira story IDs. Baseline remains slides 23-28. No estimates or sprint completion states are changed. "Evidence exists" means inspected implementation/tests or recorded prior execution, not a fresh test run or team acceptance.

### Advisor identifies a student needing attention

Backlog: S2-02, PB-05 and PB-06. As an advisor, I want to identify assigned students with supported academic concerns so I can decide whose record to review first.

| Criterion | Observable acceptance check | Existing evidence | Remaining acceptance work |
|---|---|---|---|
| A1 Correct caseload | Each advisor sees only their assigned students. Under the same filters, dashboard counts, list counts and full-record identity agree. | test_main_advisees_review.py; test_main_record_summary.py; verify_team_advisor_consistency.py; recorded live Sarah review. | Repeat on the final team candidate and retain all-four-advisor evidence. |
| A2 Supported concerns | An overdue-work concern agrees with observed assessments at the selected snapshot. Missing coverage does not become zero or a false clearance. Graduation status does not hide an independent concern. | test_main_attention.py; test_main_record_coverage.py; Santos visual comparison. | Include one incomplete-coverage case in the final demonstration. |
| A3 Useful navigation | Name search, clearing, no matches and opening a result preserve the intended student. | Existing search/filter tests and recorded browser reviews. | Tester records final candidate, dataset and selected students. |

Pass means the advisor reaches the right record with a defensible reason to review it. It does not mean the queue is a validated probability ranking or an approved outreach priority policy.

### Advisor receives a genuine course assessment

Backlog: S2-06, S2-07 and PB-06. As an advisor, I want an assessment based on available course observations so I can use it alongside the academic record.

| Criterion | Observable acceptance check | Existing evidence | Remaining acceptance work |
|---|---|---|---|
| P1 Genuine inference | A ready enrollment invokes the unchanged frozen model and calibration artifacts. No fitted component trains during the request. Response identifies the correct student, course and enrollment. | test_main_team_risk_smoke.py wraps actual predict and forbids Pipeline.fit; frozen hash verification. | Run real-artifact smoke from a clean teammate setup on the final candidate. |
| P2 Time validity | Feature windows use only observations known by the cutoff. Future activity, revisions or score release cannot change an earlier feature row. Scores/GPA remain outside the frozen 16 predictors. | Original temporal extraction/ML regression tests and feature contract. | Include those existing suites in final regression; do not reopen the held-out test set. |
| P3 Honest absence | Missing required coverage returns unavailable with a null probability while supported academic information remains accessible. Missing artifacts return the existing safe 503 error. | Real-inference HTTP smoke covers source-gap invalidation and missing-artifact 503; service extraction checks. | Verify UI separately for source coverage gaps and operational service failure. |
| P4 Access and freshness | Student/admin/unassigned advisors cannot use the advisor-only risk routes. Expired or invalidated cached results never return as fallback after failure; manual refresh recomputes. | Auth and cross-assignment checks in smoke; test_main_assessment_cache.py. | Repeat with current role sessions in final acceptance. The 12-hour cache is not a scheduled ingestion job. |

Pass means correct software inference and access behavior. It does not establish accuracy on synthetic students, Brightspace equivalence or an approved clinical/academic intervention threshold.

### Advisor understands the explanation

Backlog: S2-09 and PB-06. As an advisor, I want a concise account of the student's observed course activity so I can prepare a relevant conversation.

| Criterion | Observable acceptance check | Existing evidence | Remaining acceptance work |
|---|---|---|---|
| E1 Verified attribution | Optional SHAP contributions reconstruct the raw model score and frozen calibrated probability within the established numerical tolerance. The reference uses verified training data and never a future checkpoint. | ml/tests/test_explain.py; SHAP_STAGE_INTEGRATION.md records numerical checks. | Provision verified explanation backgrounds and optional runtime dependencies for teammates, separately from the minimal two-model ZIP. |
| E2 Understandable wording | Explain selected behavioral factors using supported observations and a short paragraph. No SHAP/log-odds jargon, invented causes, guaranteed outcomes or harmful interpretation of resource-use counts. | explanationParagraph() in MainResearchRisk.jsx; csv-advisor-narratives.test.js; recorded Santos visual review. | Tester/PO reviews representative late, missed, engaged and unusual resource-count cases. Automated wording checks do not prove usability. |
| E3 Independent failure | If explanation references/dependencies are unavailable, the valid prediction remains intact and the UI states that an explanation is unavailable. An unscored course never receives a fabricated explanation. | test_optional_explanations.py. | Demonstrate missing-reference behavior without modifying the frozen model or original artifacts. |

Reproducibility gap: csv-advisor-narratives.test.js reads ignored advisor-*-audit.json files and skips when ACADMATE_MAIN_SNAPSHOT is absent. A skipped test is not acceptance evidence. The final handoff must document regeneration using the existing read-only audit tooling, or provide portable non-sensitive test fixtures. Preserve the original audit results. Do not treat this file as an already self-contained clean-checkout test.

### Advisor and student complete the existing plan workflow

Backlog: US-04 and S2-03. As a student, I want an advisor decision and useful requested changes on the same plan I submitted so I know what to do next.

| Criterion | Observable acceptance check | Existing evidence | Remaining acceptance work |
|---|---|---|---|
| W1 Decision round trip | Submission becomes pending; the assigned advisor can approve or request changes through Approvals; student refresh shows the persisted state. Unassigned and student decision attempts fail. | test_main_approval_workflow.py tests both decision paths and role boundaries. | Repeat on the selected full-population demo using a designated test request. Do not mutate an existing approval just to reset the demo without an agreed test scenario. |
| W2 Actionable feedback | Requested changes require a meaningful bounded comment. Student feedback appears, and clears appropriately after subsequent approval. Badges/counts track decisions and reopening. | main-plan-feedback.test.js; main-approvals.test.js; approval lifecycle tests. | Final UI review on the release candidate. These are workflow tests, not proof of an agreed academic policy. |
| W3 Academic consistency | Completed/current/remaining credits and estimated graduation agree across roles for the same program. Offering warnings remain visible; approval of choices does not confirm registration. | test_main_degree_summary.py; graduation/record tests; latest visual approval wording verification. | Agree one dataset and program mapping. Never replace 36-credit fixture expectations with 30-credit ones without changing the test scenario explicitly. |
| W4 Follow-up entry | From the selected student, Message or Schedule follow-up opens the correct existing recipient/meeting context. Submission remains an explicit user action. | Navigation is present in MainStudentRecord and Advisees. | Explicit recipient-ID/student-ID mapping and persistence checks on the final candidate. This review does not establish that this criterion has passed end to end. |

W4 refines the existing messaging/meeting stories US-07/US-08 and PB-07. A follow-up suggestion or visible button does not complete intervention outcome tracking. Do not introduce a second messaging, scheduling or approval service in the risk component.

## Final acceptance record

For each criterion above, the tester records: backlog reference, candidate commit/export provenance, dataset manifest, test command or manual steps, expected result, actual result, pass/fail/blocked/skipped, date and evidence location. Record only synthetic identifiers needed for reproduction. Proposed division of review: Tafadzwa verifies product/explanation meaning; Li verifies API/auth/inference integration; Datta or an available database reviewer verifies mappings and schema/import invariants; frontend owner checks shared components; tester runs and records acceptance. These are proposed review responsibilities, not claims of teammate approval.

Keep the existing evidence scopes separate:

- Earlier combined backend checkpoint: 405 passed before subsequent small changes.
- Later focused checkpoints: 25, 18 and 50 passed for their documented scopes, not an aggregate new total.
- The most recent 50-pass run covers admin presentation and integrations, not complete risk/ML acceptance.
- The final candidate still needs one complete regression run with explicit opt-ins and actual artifact smoke, plus the agreed cross-role workflow review.

## Next bounded work package

First close verification portability: document or make reproducible the full-population narrative audit inputs and verify model-plus-explanation provisioning in a clean teammate environment. Then select the final candidate/dataset and run the acceptance checklist above. This advances S2-07 and S2-09 without adding models, academic policies, live integrations or new UI scope. Update current presentation status only after the corresponding evidence is recorded.

## Acceptance evidence update - November 14, 2026

The verification-portability work package above now has local execution evidence in ML_EXPLANATION_SETUP.md. A separate trusted numeric reference package permits actual model/SHAP inference without original training CSVs. A fresh source/artifact layout passed; the installed Python environment was reused, so fresh-machine dependency acceptance remains open. Reference provisioning tests: 7 passed; model provisioning: 6 passed; original ML: 52 passed; optional explanation failures: 3 passed.

The population runner now recreates all four advisor audits into a new output directory and passes the frontend narrative assertions with zero skips: 100 students, 800 enrollments, 179 scored/explained active enrollments, 621 unscored historical enrollments. Academic fingerprints were unchanged. This replaces the earlier portability gap with a documented reproducible local procedure, without claiming model accuracy or team release acceptance. Canonical candidate/dataset agreement, teammate dependency setup, follow-up action acceptance and final full regression remain open.


## Fresh-environment acceptance update - November 14, 2026

Fresh isolated dependency installation and actual model/SHAP smoke now pass locally. The complete combined-candidate backend regression passes **418 tests**, with zero failures/errors/skips and real-model smoke enabled. Separate fresh-environment suites pass 52 ML, 13 provisioning and 3 optional-explanation tests. Current frontend suite: 13 passes, one explicitly skipped older standalone live check; the current combined live check and production build pass. See ML_EXPLANATION_SETUP.md for exact commands, test harness corrections, dependency-manifest distinction and evidence paths. These results replace the prior pending local full-regression gate; they do not constitute teammate-machine confirmation, team-wide release/dataset agreement or institutional accuracy validation.

## All-account end-to-end acceptance update

See SPRINT2_HANDOFF_ACCEPTANCE.md for the final workflow matrix and exact limits. The running combined demo passed 105-account verification through the frontend proxy: 2,777 HTTP checks, 610 expected denials and correct follow-up recipient/meeting context for all 100 students. All CSV hashes and the academic fingerprint remained unchanged. This complements the 418-pass backend regression and fresh model/explanation setup, without claiming completion of external integrations, approved retrieval or outreach policy.

## Project-help retrieval increment - November 14, 2026

Following user authorization, S2-10 now has an implemented project-document demonstration with exact passages, versioned source citations, authenticated source views and explicit academic-policy abstention. It reuses the existing AI conversation and preserves blocked-topic/engine/fallback behavior. Full backend regression after this integration: 426 passed, zero failures/errors/skips; frontend: 14 passed with one explicitly skipped older standalone live test; build and live non-persisting proxy check passed. See PROJECT_HELP.md. Do not label this institutional academic-policy retrieval or semantic RAG, and do not mark broader S2-10 scope complete without team agreement.
