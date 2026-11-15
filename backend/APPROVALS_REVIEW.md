# Approvals workflow review

Date: 2026-11-12. Branch: feature/academic-risk-prediction.

## Verified behavior

Student plan submission creates a pending request for the assigned advisor. Queue tabs/counts and sidebar approval badges reflect decisions. Approve changes the student plan to Approved; requesting changes returns it with the advisor comment. Reopen/Undo restores Pending and the plan state. Other advisors cannot read or decide another advisor's requests; students cannot invoke advisor decision APIs. Duplicate decisions conflict. Reopen is rejected after the supported window or after affected records have changed. Form decisions, drop-request withdrawal and restoration, and required change-request comment validation are covered.

## Corrections

- `frontend/src/components/research/MainAdvisorApprovals.jsx`: preserve all queue-response fields during local count updates, including `prechecks: false`. Previously making a decision could re-enable the hidden pre-check UI. Uses the frontend team's Approvals page and shared components; clarified empty queue text.
- `tools/apply_main_approvals_review.py`: reproducible copy into the isolated main export.
- `tools/apply_main_graduation.py`: retain degree audit's existing approval-aware graduation status. The initial recent projection overlay replaced ?Pending capstone approval? with estimate assumptions; the workflow regression caught this. Graduation remains credit-projected while outstanding approval status stays visible. Expected graduation wording now matches across the relevant surfaces.
- `frontend/src/components/research/MainAdvisorAdvisees.jsx`: match Expected graduation label.
- `tools/verify_graduation_demo.py`: accept the consistent graduation label during verification.

## Tests

- Initial backend run: 16 passed, 1 failed, identifying the graduation-status regression. Corrected without weakening existing assertions.
- Final backend run: **28 passed** across existing approvals, student plan, assignments/form tests and new cross-role lifecycle/comment validation tests.
- New frontend rendered-component test: **1 passed**; exercises the actual page with mocked API responses, real auth/toast/router providers, count updates, disabled prechecks and Undo. Its initial CommonJS router-import harness error was corrected before the passing rerun.
- Frontend production build: **passed**, existing >500 kB bundle warning remains.
- Read-only graduation check: **all 100 students and four advisor totals passed**; original CSV hashes unchanged.

New tests: `backend/tests/test_main_approval_workflow.py`, `frontend/tests/main-approvals.test.js`.

## Environment and limits

Mutation tests ran only against `acadmate_risk_demo_main_sprint2_test` on local PostgreSQL port 55439. They did not submit requests, decisions, messages or academic changes in the 100-student CSV demo. Test-generated notifications remain confined to disposable fixtures. The CSV demo API was restarted to load the corrected projection overlay.

The main demo has no requests because its students have not submitted plans/forms/drop requests. An empty approvals queue is valid and is not evidence that the page is disconnected. No requests were invented to fill it. A visible demonstration should follow a deliberate student submission in a separately agreed demo scenario, then an assigned-advisor decision and student follow-up. Manual browser interaction with a populated queue is still pending; automated state transitions and rendered page behavior were tested here.

No shared database, frozen model, calibration map or original CSV changed. Nothing committed or pushed.

## Visual review follow-up

Observed the real CSV advisor Approvals page in Chrome: header, shared styling, active navigation and all three tab selections rendered correctly with zero counts. Found a redundant empty detail card asking the user to select a nonexistent request. Replaced the two-column empty state with a single shared Card containing tab-specific text; populated requests retain MasterDetail. Extended rendered-component regression passed including Approved/Changes requested empty states and existing approval/Undo coverage. Final screenshot of the updated state is pending because Chrome switched to unrelated private content and automatic approval review blocked further observation. No further browser access attempted.

## Populated demo request

With user authorization, submitted Santos Shel?s Fall 2027 plan through his authenticated student API session: CS706 and CS799, six credits, request ID 1, assigned to Sarah (201). Both added PlanItems carry a Sprint 2 demo note. No advisor decision submitted. Pending queue count and badge are 1. CSV records remain unchanged. External email configuration verified log-only.

The populated request exposed a gap: stored nonblocking offering warnings were absent from the advisor response. Added optional warnings to the isolated-export approval response and rendered them under the shared pre-check Notice, using an amber warning badge when relevant. Credit-based completion text no longer promises graduation. Existing approval rules and pre-check visibility preference are preserved. No future course offerings were invented. Reproduce with tools/prepare_approval_demo.py; it preserves an existing pending request. Final populated-browser review awaits the user leaving the demo tab active.

## Demonstrated request-changes decision

Returned request 1 to Santos through Sarah?s authenticated local demo API, with the user?s authorization. Comment asks Santos to confirm Fall 2027 availability of CS706 and CS799 before resubmission and offers to review alternatives. Verified: Pending 0, Approved 0, Changes requested 1; approval sidebar badge 0; both student PlanItems show Changes requested; the student?s in-app conversation contains the advisor comment. Original eight CSV hashes unchanged. The decision is reopenable under existing rules; no reopen performed. Browser was on an unrelated tab, so this decision was exercised through the API rather than a manual browser click.

## Cross-role visual verification

Observed Sarah's returned request in Chrome: Pending 0, Changes requested 1, no pending sidebar count; two courses, availability warnings, full decision comment and Reopen/Open student controls. Signed in as Santos: confirmed Changes requested badges on CS706 and CS799 in the degree plan and the full advisor comment in the Acadmate notification thread on Messages. Opening the notification marked it read under normal app behavior. No resubmission, reopening or further decision performed.

Visual gaps to address: the degree plan does not surface the advisor comment beside returned work; graduation still reads On track while the plan has changes requested. The underlying approval state and notification agree, but those summary cues can be clearer. Final expanded notification screenshot was interrupted when the user switched to another browser tab; no claim of a complete screen-by-screen visual certification.

## Student plan feedback implementation (2026-11-13)

Added `risk_mvp/plan_feedback.py` with read-only helpers. Term output has an optional advisorFeedback field, populated only from the newest applicable returned plan request touching currently returned items. Old comments disappear on reopen/resubmission rather than being displayed as a current decision. Future/current returned plan items make graduation status ?Plan changes requested?; the computed date is retained.

Authored frontend `MainDegreePlan.jsx` preserves the frontend team's page and adds a shared amber Notice directly above the roadmap with the term, exact comment, and next-step text. `tools/apply_main_plan_feedback.py` applies schema/service additions and the page to the isolated export, without database writes. Apply it after the main graduation/approval overlays.

Validation: 23 backend tests passed across approval lifecycle, plans, permissions, comment bounds and warnings. Two rendered-page tests passed: advisor decision/Undo/settings and student feedback/date/status. The student test uses ignored `plan-feedback-fixture.json` captured from the real synthetic demo API; initial harness failures from API-prefix and shared-card lookup assumptions were corrected before the passing run. Production build passed with the existing bundle warning. Direct live API check confirmed the exact comment and December 2027 / Plan changes requested, and original CSV hashes unchanged. No new advisor decision, database migration, model change, commit or push. Final browser visual review of these two additions is not claimed by these automated checks.

## Resubmission and approval demonstrated (2026-11-13)

User explicitly requested skipping course-offering setup and proceeding with resubmission/approval. Through authenticated local demo APIs, revised Santos?s CS706 plan item with a note acknowledging unconfirmed availability, resubmitted the two-course Fall 2027 plan as request 2, and approved it as Sarah. Approval comment explicitly limits this to demo course choices and does not confirm offerings or registration. Both original availability warnings remain visible. No new offerings or enrollment records created.

Verified request 2 Approved, both student course plan statuses Approved, current advisorFeedback null (old returned comment no longer current), December 2027 estimate preserved, Pending count/badge 0, Approved 1. Changes requested 1 refers to historical request 1; it is not a current pending task. Student?s in-app approval notification verified. Original CSV hashes unchanged. Step 1's final visual verification was blocked by automatic browser review identifying the previously active private page; no workaround attempted. These are API/data verifications, not screenshots of the approved screens.

## Approved-state visual review completed

Re-established Chrome control using a fresh inventory identifying the Acadmate window. Observed Santos?s refreshed requirements: both Fall 2027 courses Approved, December 2027 estimate retained, old change-request feedback absent. Messages displayed the full approval and availability caveat. Signed in as Sarah and inspected request 2 in Approved: Pending 0, Approved 1, original request retained under Changes requested 1, both availability warnings and the approval comment visible. No further decision submitted.

Found and corrected two frontend inconsistencies in authored MainDegreePlan.jsx: roadmap rows now preserve explicit planStatus (Approved previously rendered as Planned), and SENDABLE now matches backend draft/revision states including Planned and Changes requested. Extended rendered test verifies returned plans can be sent, approved plans cannot be sent again, both roadmap labels remain Approved, and old feedback disappears. Both rendered-page tests passed. Application data unchanged by this correction; only normal login/logout and read receipts during browser review.


## Portable feedback regression fixture

The feedback page test now reads `frontend/tests/fixtures/plan-feedback.json` relative to the test source, rather than the ignored saved demo response. The adjacent fixture README documents its synthetic origin and exact command. The unused catalogue was removed; no identities, credentials, database URLs or predictions are included. The historical local response is preserved unchanged. React and the renderer are loaded from the same prepared team frontend to avoid duplicate-React hook failures when running from the repository root. Targeted rendered regression: **1 passed, 0 skipped**, covering returned feedback, resubmission, approval labels and old-feedback removal. No live advisor decision or database operation was performed. Team frontend setup consolidation remains separate pending alignment with Li.
