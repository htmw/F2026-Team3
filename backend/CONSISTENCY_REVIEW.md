# Sprint 2 consistency review — 12 November 2026

Scope: feature/academic-risk-prediction and its isolated main integration export at 8c4b0843368b. Not a review of an unseen shared deployment. Demo snapshot remains 1 October 2026; no snapshot preset was chosen or added.

## Corrections found during this review

- Reports used mutually exclusive status counts after Advisees adopted independent attention/graduation filters. The scoped overlay now shares the filter predicate, uses true caseload as the percentage denominator and explains overlapping graduation counts.
- Earlier twelve-hour work enabled the backend cache but missed the actual browser timer and manual-refresh invocation because an edit did not match the source whitespace. Both are now corrected and directly asserted by UI tests. Earlier claims that minute polling was already removed were incorrect.
- ML and original research tests require their own import paths; main-integration pytest modules run in the main environment. An attempted test command using the demo database was automatically rejected; tests were redirected to the separate disposable test database. No security settings were relaxed.

## Final results

| Check | Actual result |
|---|---|
| Complete main-backend suite | 359 passed |
| ML suite, including SHAP and leakage checks | 52 passed |
| Original research/backend unittest collection plus pure cache/evidence checks | 37 collected: 26 passed, 11 explicitly skipped |
| Real-inference frontend/component suite | 3 passed |
| Frontend production build | Passed; existing >500 kB chunk warning |
| All-advisor read-only audit | 4 advisors, 11 assigned students, 41 denied nonassigned access checks |
| All-enrollment real inference | 46 scored at each of days 7, 14 and 28: 138 successful assessments |
| Real explanation reconstruction | 46 verified at day 28 |
| Current demo snapshot | 13 scored / 33 ineligible historical enrollments |
| Frozen model/calibration hashes | Unchanged and verified |
| Academic records | Unchanged by read-only audits |
| Git generated/secret exclusions | Model files, ml/outputs, .venv and backend/.env ignored |

The 11 skipped research tests comprise eleven legacy disposable-database integration tests. They are not counted as passes. The current database-backed path was independently exercised read-only across all 46 enrollments and all four advisors. Some existing tests train temporary toy models to test research functions; no frozen artifact was retrained or overwritten.

## Current behavior and limits

- Dashboard, sidebar and Advisees attention counts agree. Graduation can overlap with attention. GPA/planning checks are separate from model probabilities.
- Concern summaries use the same shared rules and course overdue source. Existing assignment pages still use separate coursework/advising records without an identifier crosswalk; no equivalence is claimed.
- Automatic course scoring has no advisor date control or visible cutoff label. Every open/return checks source evidence; expensive results are reused for up to twelve hours. The UI timer is twelve hours, manual refresh sends force_refresh=true, and failed/expired updates have no stale fallback.
- The cache is bounded and process-local, not a scheduled background job or cross-worker cache. Source changes are detected on the next request, not by push notifications. The same fixed synthetic demo day remains configured.
- Two students have no advisor assignment and remain outside advisor caseloads.
- Real model execution on synthetic records validates software behavior, not institutional predictive accuracy.
- Current checks are automated and data-backed; latest full visual review, narrow-screen review and presentation-machine rehearsal remain separate steps.

No shared database/schema changes, dataset regeneration, commits, pushes or merges were performed. No messages were sent. Existing teammate source modules remain untouched in the checkout; guarded changes apply to the isolated main export.


## Outstanding course work alignment ? 2026-11-12

The isolated main demo now includes known outstanding assessments across active courses as an additional advisor-review reason. The existing recent-deadline and academic rules retain their priority. This closes the mismatch where Amara had overdue course work but appeared under No current flags because those deadlines were older than fourteen days. No model probability threshold or new academic policy was introduced. All course totals require complete observed coverage; missing data is not treated as zero.

Attention reasons now take precedence over routine pending-plan approval text. The same shared rule feeds dashboard counts, sidebar badges, advisee filters, reports and record concern summaries. At the unchanged October 1 snapshot, Sarah has 6 needing attention and 2 without current flags; Daniel has 1 and 2 respectively. Amara has 5 outstanding assessments across active courses and appears in Needs attention. No current flags means no matched workflow rule; it is not a guarantee of low model risk.

Validation: 4 attention unit tests passed; the read-only all-advisor audit passed for 4 advisors, 11 assigned records and 41 denied access checks. The live API confirmed Amara's reason and dashboard count of 6. All 359 existing backend tests passed; after the final reason-priority adjustment, all 22 affected advisor dashboard/list/report tests passed. The 3 frontend inference regressions passed. No shared database writes, model changes, commits or pushes.


## No academic records state ? 2026-11-12

Hana Sato (105) and Marcus Reed (106) have no enrollments. They now appear in a separate No academic records category, excluded from No current flags. Daniel has 3 advisees: 1 needs attention, 2 have no academic records, and 0 have no current flags. Existing administrative attention flags can still coexist with a missing-records state. Record summaries explicitly state that progress and course risk cannot be assessed; unknown academic totals and progress charts are not shown as measured zero progress. Reports use the same category, and CSV exports omit the internal Low rule level for missing-record students. No new academic data was created.

Validation: 361 backend tests passed; 6 affected report/coverage tests passed after final export adjustment; 52 ML tests passed; 3 frontend inference tests passed; frontend production build passed (existing chunk-size warning). Live API checks confirmed missing-record list/record schemas and empty enrollment lists for both students. Read-only consistency checks covered all 4 advisors, 11 assigned records and 41 denied assignment checks. Fixed synthetic CSV validation passed all 16 check groups and all 31 validator tests, with counts unchanged: 105 users, 100 students, 4 advisors, 1 program, 30 courses, 800 enrollments, 100 assignments and 3 requirement groups.

Reproduction: apply tools/apply_main_record_coverage_review.py --snapshot <isolated-export> after the existing dashboard, advisees and student-record overlays. No shared schema changes, model changes, commits or pushes.
