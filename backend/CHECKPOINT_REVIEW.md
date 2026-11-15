# Sprint 2 checkpoint file review

Branch: `feature/academic-risk-prediction`.

Review scope: current tracked diff, complete untracked inventory, Python syntax for new source files, credential-pattern scan, Git exclusions, and setup/test dependencies. This is a checkpoint scope review, not a fresh end-to-end security audit or proof of authorship. No staging, commit, push, branch switch, database operation, or model training was performed.

## Selected authored files

The existing pending set contains 3 modified and 72 new files (75 total). All are within the risk integration scope: optional explanations and artifact provisioning; main-app risk adapters and UI overlays; population/demo preparation and verification; approval/graduation consistency; tests and documentation. Keep the explicitly named files below; avoid broad `git add .`. This review document is one additional documentation file.

- `backend/ADVISOR_RISK_AUDIT.md`
- `backend/APPROVALS_REVIEW.md`
- `backend/CONSISTENCY_REVIEW.md`
- `backend/CSV_POPULATION_DEMO.md`
- `backend/DATASET_USAGE_AUDIT.md`
- `backend/END_TO_END_POPULATION_REVIEW.md`
- `backend/GRADUATION_PROJECTION.md`
- `backend/MAIN_RISK_INTEGRATION.md`
- `backend/ML_ARTIFACT_SETUP.md`
- `backend/RESEARCH_DEMO.md`
- `backend/RISK_MVP.md`
- `backend/VISUAL_REVIEW.md`
- `backend/risk_mvp/graduation.py`
- `backend/risk_mvp/main_assessment_cache.py`
- `backend/risk_mvp/main_attention.py`
- `backend/risk_mvp/main_data.py`
- `backend/risk_mvp/main_explanations.py`
- `backend/risk_mvp/main_host.py`
- `backend/risk_mvp/main_router.py`
- `backend/risk_mvp/plan_feedback.py`
- `backend/risk_mvp/service.py`
- `backend/tests/test_csv_demo_auth_scope.py`
- `backend/tests/test_graduation_projection.py`
- `backend/tests/test_main_advisees_review.py`
- `backend/tests/test_main_approval_workflow.py`
- `backend/tests/test_main_assessment_cache.py`
- `backend/tests/test_main_attention.py`
- `backend/tests/test_main_dashboard_review.py`
- `backend/tests/test_main_graduation_regression.py`
- `backend/tests/test_main_record_coverage.py`
- `backend/tests/test_main_record_summary.py`
- `backend/tests/test_main_risk_data.py`
- `backend/tests/test_optional_explanations.py`
- `frontend/THREE_ROLE_ALIGNMENT.md`
- `frontend/src/components/research/MainAdvisorAdvisees.jsx`
- `frontend/src/components/research/MainAdvisorApprovals.jsx`
- `frontend/src/components/research/MainAdvisorDashboard.jsx`
- `frontend/src/components/research/MainDegreePlan.jsx`
- `frontend/src/components/research/MainResearchRisk.jsx`
- `frontend/src/components/research/MainStudentRecord.jsx`
- `frontend/tests/csv-advisor-narratives.test.js`
- `frontend/tests/main-approvals.test.js`
- `frontend/tests/main-plan-feedback.test.js`
- `frontend/tests/main-research-risk.test.js`
- `ml/reports/SHAP_PROTOTYPE_VALIDATION.md`
- `ml/reports/SHAP_STAGE_INTEGRATION.md`
- `ml/requirements-shap.txt`
- `ml/src/acadmate_ml/explain.py`
- `ml/tests/test_explain.py`
- `tests/test_provision_ml_artifacts.py`
- `tools/Start-CsvPopulationDemo.ps1`
- `tools/apply_csv_demo_adapter.py`
- `tools/apply_main_advisees_review.py`
- `tools/apply_main_approvals_review.py`
- `tools/apply_main_dashboard_review.py`
- `tools/apply_main_graduation.py`
- `tools/apply_main_plan_feedback.py`
- `tools/apply_main_record_coverage_review.py`
- `tools/apply_main_student_record_review.py`
- `tools/audit_csv_advisor.py`
- `tools/audit_shap_prototype.py`
- `tools/audit_shap_stages.py`
- `tools/prepare_approval_demo.py`
- `tools/prepare_csv_population_demo.py`
- `tools/prepare_main_risk_demo.py`
- `tools/provision_ml_artifacts.py`
- `tools/sync_csv_coursework_progress.py`
- `tools/verify_all_advisor_journeys.py`
- `tools/verify_all_demo_sessions.py`
- `tools/verify_csv_population_demo.py`
- `tools/verify_demo_navigation.py`
- `tools/verify_frozen_demo_consistency.py`
- `tools/verify_graduation_demo.py`
- `tools/verify_main_attention.py`
- `tools/verify_main_risk_demo.py`

## Exclusions and integrity checks

- Git confirms the frozen logistic model and calibration maps, generated `ml/outputs/` content (including the pinned main export), virtual environments and `backend/.env` are ignored.
- No pending files are model binaries, CSV datasets, archives, environment files, compiled caches, or generated builds. No private-key, GitHub-token, AWS-access-key or credential-bearing-URL pattern was found in the pending text files. Local database URLs are loopback-only and contain no password; tests use existing public synthetic demo credentials. Pattern scanning cannot establish that every possible secret is absent.
- `backend/models.py`, `backend/seed_data.py`, `backend/main.py`, original `data/synthetic/` records and `ml/configs/FINAL_EXPERIMENT_V1.json` have no changes relative to HEAD. No tracked teammate backend implementation file is changed beyond the scoped `risk_mvp/service.py` evidence additions. Contributor identity for untracked files cannot be established from Git history.
- Root pytest cache excludes itself; `ml/.gitignore` excludes outputs, local data, archives and serialized models. No additional Git ignore configuration is required for this selected set.
- The index was empty at review time. Tracked diff whitespace check passed; Git emitted existing LF-to-CRLF notices for two Markdown documents.

## Validation evidence

- Latest complete isolated main backend suite: **376 passed** in 223.84 seconds, only against the disposable local test database.
- Separate graduation calendar/credit tests: **15 passed**.
- Earlier checkpoint run: ML **52 passed**; authored risk/API suite **44 passed, 12 skipped** (opt-in integrations); separate frozen-artifact smoke **1 passed**; integrated frontend checks **6 passed**; original frontend suite **7 passed, 1 skipped**. Frontend production build succeeded with the existing bundle-size warning. These earlier checks were not repeated during this file review.

## Integration considerations before team handoff

1. The combined app runs from a pinned, ignored main export, not directly from this branch's old main app. Authored overlays and adapters belong in Git; the exported app, its environment and generated evidence do not. Li must review how these changes are adopted into the current shared main source before merging.
2. Resolved: the student feedback UI test now reads version-controlled `frontend/tests/fixtures/plan-feedback.json`, with usage/provenance in the adjacent README. It no longer reads saved local demo state. The renderer uses the team frontend React installation, avoiding duplicate React instances. Targeted rendered test: **1 passed, 0 skipped**. The prepared team frontend is still required; consolidation with Li remains a separate task.
3. The CSV narrative test requires generated per-advisor audit JSON; those can be produced with the authored audit tools after local demo setup. Several backend main-app tests must be copied into the isolated export to use its conftest and schema; this is not covered by ordinary root test discovery. A single documented preparation/test command would reduce handoff errors.
4. Historic reports include earlier 13-student/46-enrollment demo counts and earlier test totals. They describe separate stages; the current CSV demo is 100 students, 800 enrollments, 179 current courses. Avoid presenting historic counts as current evidence.
5. Frozen model files remain distributed through the verified artifact bundle, never committed. Optional SHAP backgrounds also rely on ignored local research outputs; missing explanation inputs must retain the existing safe optional behavior.

Recommendation: the selected files form a relevant development checkpoint. The fixture gap is resolved. Consolidate the team-app preparation/test setup with Li before describing it as a fully self-contained teammate release. No commit or push is authorized by this review step.


A newer isolated team candidate is now documented in `TEAM_INTEGRATION_REVIEW.md`, prepared by `tools/prepare_team_review.py`. It combines pinned latest main and Datta degree progress while retaining our overlays. Its full backend result is **402 passed, 2 failed**; both failures reproduce on unmodified pinned main. Do not confuse this with the older demo's 376-pass result. Li's exact published work and dataset identifier reconciliation remain pending. The portable feedback fixture includes a degree-progress response and passes on both pages.


Final team-candidate follow-up: **405 backend tests passed** with the real-artifact smoke enabled. The two baseline main failures were corrected through guarded test-only setup/serialization fixes. Advisor/student frontend regressions: **2 passed**. Datta degree-progress compatibility: **100/100 CSV students passed** in read-only checks. See `TEAM_INTEGRATION_REVIEW.md` for exact commands, chronology, and the remaining deployment/dataset-identifier boundary.


Student summary follow-up: include `frontend/src/components/research/MainTeamDegreePlan.jsx` and `backend/tests/test_main_degree_summary.py`, with updated team preparation tool, portable fixture and frontend regression. Focused validation: **25 backend + 2 frontend passed**, production build passed, live Chrome summary review confirmed. Datta calculation service and all original CSVs remain unchanged.
