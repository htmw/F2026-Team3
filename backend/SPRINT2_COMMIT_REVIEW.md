# Sprint 2 source checkpoint for team review

Prepared November 15, 2026 on feature/academic-risk-prediction. This checkpoint preserves the authored integration, tests, setup tools and documentation for peer review. It does not merge the combined demo into the shared application.

## What to review

- Risk source adapters, current-result cache, optional SHAP explanations and readable advisor narratives.
- Student/advisor views, plan feedback, consistent graduation summaries and opt-in weekday advisor hours.
- Bounded project-help retrieval and its checked project guides; no institutional-policy claims.
- Frozen-model and explanation-reference provisioning, isolated demo preparation and population acceptance tools.

The tested combined candidate remains the ignored export ml/outputs/main-integration/team-review-9dba938-a0c1930. It combines pinned main 9dba938da14df8607c81b6f92988e8210977bf24 and Datta a0c19303afbf51eda566b705e9934f6acb157627 using the version-controlled overlays. Use tools/prepare_team_review.py and backend/ML_EXPLANATION_SETUP.md to understand that layout before running tests. Ordinary root discovery does not reproduce the combined backend suite.

After fetching on November 15, origin/main is b9985b9 and is newer than the tested pinned main. Li must reconcile the authored adapters/overlays with that revision before integration. No branch merge, rebase or shared schema change was performed. See TEAM_INTEGRATION_REVIEW.md for preparation history and review boundaries.

## Fresh pre-push validation

- ML, artifact provisioning and retrieval: 72 passed and four subtests passed.
- Fixed dataset: all 16 validation groups and 31 unit tests passed. Counts remain 105 users, 100 students, four advisors, one program, 30 courses, 800 enrollments, 100 assignments and three requirement groups.
- Combined frontend: 14 passed, zero failed, one explicitly skipped older standalone live-demo case. Current combined live risk panel passed. Population narrative checks consumed the existing verified audit inputs; no fresh full-population audit was claimed by this rerun.
- Combined frontend production build passed with the existing >500 kB bundle warning.
- Frozen artifact hash verification and real inference smoke passed. Established scored fixture remains 0.3783828964249184; the unavailable fixture remains unscored. Explanation-reference verification passed for all 16 packaged stages.
- Frozen model source hashes, backend/models.py, backend/seed_data.py, backend/main.py and original academic CSVs remain unchanged.

Combined backend regression: **433 passed, zero failures/errors/skips in 142.07 seconds**. JUnit evidence is retained locally at ml/outputs/prepush-20261115-backend.xml. The run uses only the dedicated loopback acadmate_risk_demo_main_sprint2_test database, with advisor defaults and real-artifact smoke enabled. The working demonstration and shared databases are outside this regression target.

## Source exclusions and review boundaries

Only authored source, tests, synthetic test fixtures, checked project-help guides and Markdown documentation are selected. Generated datasets/results, ignored combined exports, trained binaries, artifact ZIPs, Office documents, environment files, credentials, virtual environments and temporary files are excluded. A pattern scan found no credential-like material in the selected files; this is not an exhaustive security audit. Public synthetic credentials in tests and instructions are demo-only.

The presentation/manual are separate deliverables, not Git source. The new 45-slide main and 13-slide backup decks are under the ignored sprint2-updated-deliverables directory. Earlier reports retain their dated checkpoint/uncommitted descriptions; this document supersedes those descriptions for this publication checkpoint.

Li should review latest-main adoption, API/auth/error behavior, setup reproducibility and optional explanation failures. Datta or an available database reviewer should review sidecar schema, identifier mapping and import boundaries. The frontend owner should review overlay adoption and responsive layouts. External provider delivery, institutional validation, approved academic/outreach policy and intervention outcome tracking remain separate work. Synthetic consistency does not validate predictive accuracy.

No PR is opened or merged by this publication task. Artifact packages must still be shared separately using the documented trusted hashes.
