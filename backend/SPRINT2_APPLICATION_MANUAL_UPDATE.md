# AcadMate Sprint 2 application and installation update

November 14, 2026. This update covers the integrated 100-student synthetic demonstration and supersedes the older Amara/36-credit/missing-model instructions for this candidate. Original older examples remain historical. The system uses synthetic academic/LMS observations and does not connect to Brightspace.

## Application access and records

Open http://127.0.0.1:5179. Use separate browser profiles for simultaneous roles because ordinary tabs share the session cookie. The existing public synthetic password is Acadmate!2026, for local demonstration only. Santos Shel is santos.shel@pac.edu and advisor Dr. Sarah Smith is sarah.smith@pac.edu. Use users.csv to choose any other synthetic account rather than inventing credentials. Each of four advisors has 25 assigned students. Keep real credentials and institutional data out of this demo.

Santos's Degree plan shows 21/30 completed credits, three in progress and six left after this term. Estimated graduation is December 2027 under the documented nine-credit Spring/Fall pace and successful completion assumptions. Course choice approval does not confirm course offerings, registration or graduation. Other students have different records; compare each against their own source rather than expecting Santos's values everywhere.

## Advisor review and course assessment

Open Advisees, search by name and select the intended student before opening their record. Search and status filters apply together. Clear a filter if a valid name is not in its selected category. Assigned identity and credits agree across the caseload and record.

The active-course panel invokes the frozen logistic model and calibration, then presents concise explanations of selected contributors. In the complete-coverage population, 179 active enrollments score and explain. The 621 historical enrollments remain unscored. Missing required feeds must not become zero activity or a fabricated probability. A missing model is an operational error; an optional explanation failure must not erase an otherwise valid score. Synthetic software consistency does not establish predictive accuracy on institutional students.

Message and Schedule follow-up keep the selected student's identity. All advisors have default Monday-Friday 08:00-17:00 availability in the school timezone unless adjusted. Custom schedules and deliberate clears are preserved. Existing 12-hour lead time, classes, meetings and booking limits still apply. Select February 17, 2027 to demonstrate next-day slots at the pinned observation date. A booking is saved only after the user submits it. Local persistence does not establish external email/calendar/video delivery.

## Plans and feedback

Student Degree plan supports course additions and submission to the assigned advisor. Invalid prerequisites, duplicates and already-pending submissions produce validation/conflict responses. Advisor Approvals supports changes requested and approval. The student sees saved feedback after refresh and can revise/resubmit. Approval clears returned-change feedback. Review offering warnings separately from course-choice approval.

Santos already has an approved Fall 2027 plan for CS706 and CS799. The saved comment retains the unresolved offering checks. Use Approved in the advisor queue to show this state; do not reopen an existing request just to make a screenshot look pending.

## Project help and other roles

Student AI advisor can answer How do I submit my degree plan in AcadMate? using a checked project guide. The answer is plain text without source-link/version clutter. Backend metadata retains source provenance. University policy questions are referred to the advisor and official catalog. This is bounded lexical project guidance, not comprehensive semantic retrieval or an approved institutional-policy service.

The existing student Schedule, Assignments, Messages and Settings and the admin population/catalog/audit/settings routes remain integrated. Admin and advisor permissions are enforced independently. Account deletion, reassignment, catalog publication and institution setting changes are consequential actions; do not use them casually to prepare a presentation.

## Current local setup

From C:\Users\nhesv\Documents\AcadMate-Team use the reviewed Python 3.13.14 environment at ml/outputs/handoff-venv-v1. Install combined candidate backend/requirements.txt plus ml/requirements-shap.txt, following ML_EXPLANATION_SETUP.md. Do not combine the old standalone backend dependency manifest with the candidate's conflicting pins.

Model/calibration ZIP and explanation-reference ZIP are provisioned separately from source. Follow ML_ARTIFACT_SETUP.md and ML_EXPLANATION_SETUP.md to verify package hashes, install without retraining and run the frozen inference/SHAP smoke. No original OULAD training tables are needed for serving.

The existing synthetic loopback PostgreSQL cluster is on 55439, using acadmate_risk_team_review_sprint2. Do not run reset_db.py or the destructive pytest suite against it. The current launcher tools/Start-TeamReviewDemo.ps1 starts the verified candidate on 8005 and 5179 when those ports are free and the prepared manifest exists. If the demo is already running, refresh it instead of starting a competing server. It does not initialize a teammate's database automatically.

For another machine, reproduce the named disposable setup through the reviewed guarded preparation tools and verify the same data/artifact manifests. Never substitute a shared Neon URL. A source ZIP contains source only, not the prepared database, virtual environment, node_modules, credentials or trained models. No instruction here is evidence that a new teammate machine has been provisioned.

## Verification and troubleshooting

Read SPRINT2_DEMO_READINESS.md for latest scoped counts and DEMO_WALKTHROUGH.md for the presentation sequence. Tests run on explicitly separate *_test databases. The full-population mutation harness refuses an existing target and uses an isolated clone with external mail blocked.

If a booking date has no times, check lead time, office overrides, classes and existing meetings. For 401 sign in again; for 403 check role and assignment. For a missing-artifact 503 verify both artifact packages and versions. For no assessment, check course eligibility/coverage rather than forcing a score. If student and advisor disagree, verify the same source/data/API and refresh; do not relabel students or overwrite the dataset.
