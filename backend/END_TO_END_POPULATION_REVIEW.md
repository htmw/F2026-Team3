# Full-population end-to-end review

Date: 2026-11-12. Branch: feature/academic-risk-prediction. Target: isolated local CSV demo, frontend http://127.0.0.1:5178 and API 8004. No shared database involved.

## Account workflows

All 104 identities passed: 4 advisors and 100 students. 1952 HTTP requests through the frontend proxy; 608 expected authorization/session denials; zero failures.

For every account: login role and user ID, own profile, badge data, logout and rejection of the logged-out session. Every student: dashboard, courses, assignments, degree audit, plan, meetings, AI context and thread listing, plus denial of advisor APIs. Every advisor: dashboard, advisees, reports, settings, meetings and approvals; denial of admin overview and all 75 foreign student records (300 cross-advisor checks total).

Additional messaging/conversation contacts for all 104 accounts, and schedule/meeting directory for all students: 408 successful navigation responses, zero failures.

## Academic data and inference

- Original 1,143 academic source rows preserved; eight CSV hashes unchanged.
- 100 students, 800 enrollments, 105 users, 4 advisors, 30 courses, 1 program, 100 advisor assignments and 3 requirement groups.
- All 7,998 assignment/submission projections checked against sidecar source data.
- All 100 advisor student records and 400 student academic-page API responses passed the population verifier.
- Real frozen-model inference replay passed for all 800 enrollments at their day-28 snapshots.
- At the current demo snapshot: 179 active courses scored; 621 historical courses correctly have no current risk probability.
- Independent feature audit checked every active enrollment: all 16 feature values, source cutoff exclusion, direct pipeline/calibration probability, explanation reconstruction, and cached-response consistency.
- Graduation values agree for all 100 students across dashboard, advisor record, degree audit and advisee summary; all four advisor graduation bucket totals agree.

| Advisor | Students | Enrollments | Current predictions/explanations | Needs attention |
|---|---:|---:|---:|---:|
| Sarah | 25 | 202 | 44 | 22 |
| Rowan | 25 | 202 | 44 | 20 |
| Sage | 25 | 198 | 44 | 20 |
| Quinn | 25 | 198 | 47 | 23 |

Attention counts follow existing academic checks; they are not model-probability thresholds. Graduation can overlap attention.

## Regression and browser scope

- ML regression suite: 52 passed.
- Full-population explanation rendering regression: 1 passed, covering 100 students and all 179 current explanations.
- Production build passed in the immediately preceding styling review; no application code changed in this review.
- Browser: observed Sarah dashboard and loaded advisee list/summary. Full-width dashboard rendered successfully. Desktop occlusion/window restoration limited additional visual inspection. No claim that all 104 accounts were manually reviewed in the browser.

## Limitations and next validation

No failures were found in the executed checks. This verifies the tested read workflows and model/explanation consistency. It does not establish model accuracy on synthetic students or certify every UI interaction. No messages, approvals, notes, bookings, profile edits, assignment submissions or AI generation were submitted. Those state-changing workflows need separate disposable fixtures and explicit scenario checks. Responsive visual work and deferred unavailable controls remain with the frontend team.

Normal test logins/logouts create/revoke local sessions and related audit entries. Academic records, model/calibration artifacts and CSV files were not modified. No commit, push or merge.

## Reproduce

From repository root, use the isolated main interpreter:

```powershell
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/verify_all_demo_sessions.py
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/verify_demo_navigation.py
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/verify_csv_population_demo.py --snapshot ml/outputs/main-integration/8c4b0843368b
.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe tools/verify_graduation_demo.py
```

Run tools/audit_csv_advisor.py with the same --snapshot and --advisor-id 201, 10200, 10201 and 10202 for the full independent inference/explanation audit. Detailed generated JSON results remain in ignored main-integration outputs.
