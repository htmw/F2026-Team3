# Research database API contract — Sprint 2 local MVP

All routes are under /api/v1/research/database and require ACADMATE_RISK_MVP_ENABLED=true plus the guarded disposable database URL. No authentication deployment or live institutional access is included. The frontend's development proxy forwards only this namespace to loopback port 8002.

## Student selection

GET /students -> { students: [{student_id: positive integer, name: synthetic string}] }

GET /students/{student_id}/insights -> student_id, name, source_kind, academic_summary_scope, recorded_gpa (number/null), completed_credits, gpa_policy, failed_courses[], withdrawn_courses[], active_enrollments[{enrollment_id,course_id,course_code,term}]. These are current recorded academic facts, separate from a prediction cutoff. They are not additional predictors or approved academic-policy rules.

## Enrollment assessment

GET /enrollments/{enrollment_id}/risk-assessment?cutoff=<timezone-aware end-of-day UTC timestamp>

Example cutoff: 2027-02-08T23:59:59.999999Z. The UI converts a selected UTC date to that value. Only UTC demo offerings are supported. Missing/invalid parameters return 422; unknown IDs return 404; missing infrastructure/artifacts return 503. Application errors retain code/message/details where handled, while FastAPI validation/dependency errors may use detail. Clients must handle both forms.

Response fields:

- enrollment_id, student_id/course_id when known, cutoff, as_of_day (nullable when calendar was not known).
- research_only=true, source_kind=synthetic_lms_demo.
- status=scored_research_demo or unavailable.
- research_risk_probability: finite [0,1] only for scored records, otherwise null.
- reason: null when scored; explicit missing coverage/eligibility reason otherwise.
- model_version=final-experiment-v1, calibration_method=sigmoid, computed_at_utc.
- coverage: activity/submissions/schedule -> complete and through_at. Missing keys mean coverage unknown, not zero activity.
- evidence: assessments_due, submissions, overdue_assignments, clicks_7d, clicks_28d, active_days_7d, engagement_change, days_since_activity, late_submission_rate, assessment_completion_rate, released_scores[], score_use. Fields can be null or absent when unsupported by coverage/eligibility.
- warnings: synthetic/domain-transfer and early-overestimation limits.

Assessment completion is distinct observed submissions to assessments due by cutoff divided by the number of due eligible assessments; it is null for no due assessments or incomplete dependent coverage. Early submissions to work due later do not inflate completion. Engagement change is the raw recent-7-day interaction count minus the preceding 7 days, not a causal explanation or a change in predicted risk.

A complete feed with no records produces legitimate zero counts and absence flags. Incomplete coverage yields null dependent evidence and an unscored record; other trustworthy evidence is retained. Ineligible cutoffs return no derived evidence and do not invoke feature/model calculation. Released scores are descriptive and never enter the frozen 16 inputs.

## Frontend behavior

Each active course is requested independently. A per-course HTTP failure produces a client-only request_error state, retains other successful responses, and is distinct from a server unavailable response. Initial student-list failure has a retry control. Changing cutoff clears prior estimates. UI never assigns risk bands or automatic alerts; it labels probability separately from facts and preserves null versus zero.

## Team integration

Proposed SQL under migrations/proposed/001_risk_mvp.sql requires Datta's review for table naming, migration conventions and cross-offering write constraints before shared application. Current deployment is isolated/disposable only. The frozen artifact bundle must be provided through a trusted local setup matching hashes; missing models are never retrained automatically. Existing student APIs and the four-case fixture endpoint retain their previous contracts.
