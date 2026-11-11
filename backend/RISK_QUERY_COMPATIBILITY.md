# Risk query compatibility repair — 11 November 2026

Li reported that latest-main SQLAlchemy metadata selected academic columns absent from the older isolated demo database, producing HTTP 503. The risk service now explicitly selects only the academic fields consumed by extraction and student insights. The student-list route already used explicit columns.

Changed implementation: backend/risk_mvp/service.py and backend/risk_mvp/router.py. New tests: backend/tests/test_risk_schema_compatibility.py. No changes to academic models, migrations, frozen artifacts, feature engineering, API contracts or academic policy.

Four new regression tests cover real SQLite queries with absent metadata-only columns (including section_id), academic GPA/credits and course lists, missing enrollment/student handling, HTTP 200 unavailable rather than schema failure, and actual PostgreSQL/frozen-model inference with identical features, summaries and probabilities before/after adding newer metadata. Tests never create the extra columns in PostgreSQL.

Validation:
- Backend: 24/24 passed, including all disposable PostgreSQL tests and actual artifact smoke tests.
- ML: 41/41 passed. Training-unit tests use temporary toy fixtures; the frozen research model was not retrained or modified.
- Artifact provisioning: 6/6 passed; verify --smoke passed with unchanged frozen hashes.
- Frontend: 8/8 passed, including the live frontend-proxy/PostgreSQL/model component integration test.
- Frontend production build: passed.
- Database-backed compatibility example: enrollment 20024 probability 0.2169211773909568, exactly unchanged with newer metadata.
- Original fixture smoke: enrollment 20014 probability 0.3783828964249184; enrollment 20044 unavailable/null. Fixture and database inputs differ, so their probabilities need not match.

Reproduce from repository root with the existing disposable cluster running. The provisioning script and its tests are a separate handoff supplied to Li; the commands under tests/ and tools/ require those separately supplied files. Set RUN_LIVE_ADVISOR_TEST=true and start the documented API/Vite servers to include the optional live frontend test.

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OMP_NUM_THREADS = '2'
$env:RUN_RISK_DB_TESTS = 'true'
$env:RUN_RESEARCH_ARTIFACT_SMOKE = 'true'
$env:ACADMATE_RISK_DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_sprint2'
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ml/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/provision_ml_artifacts.py verify --smoke
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Scope: this fixes coupling to unrelated added academic columns. Required fields and the risk sidecar schema must still exist. No shared database or latest-main checkout was modified or tested. Li should rerun his latest-main HTTP integration check after receiving the repair. Datta and Li still need to agree on the eventual shared schema and authentication/assigned-advisor access. This repair does not establish production readiness or predictive validity on institutional data.

The verification runs did not commit, push or merge changes. Pre-existing artifact-provisioning changes were preserved and are excluded from the compatibility repair commit.


## Additional live verification

Live verification found an additional pre-existing error: the database dependency caught FastAPI RequestValidationError and converted invalid path/query inputs to HTTP 503. backend/risk_mvp/router.py now propagates RequestValidationError, retaining FastAPI HTTP 422 responses. A fifth regression test covers zero, negative and noninteger enrollment IDs and malformed cutoff dates through the real dependency with an isolated session double.

A temporary verification harness read column names from the team's 7 November source archive using AST parsing, without executing archive code. It represented the added columns in query metadata only: students (student_number, expected_graduation, start_term_id, goal, study_goal_hours), courses (type, description, is_active), enrollments (section_id, progress_pct, absences, sessions_held). Real whole-table PostgreSQL SELECTs failed with undefined-column errors for all three tables, reproducing the reported failure mechanism. The repaired service then passed live HTTP requests against the same database and metadata overlay.

Verified: 100 students listed; student 10001/enrollment 20024 returned HTTP 200 scored probability 0.2169211773909568; student 10000/enrollment 20014 returned HTTP 200 unavailable/null; unknown enrollment returned 404; enrollment ID zero and invalid cutoff returned 422; original fixture endpoint returned unchanged probability 0.3783828964249184. Live React/JSDOM selected student 10015, requested two course predictions through the real Vite proxy, and verified rendered results. All eight frontend tests passed with no skips.

These checks used the existing synthetic database, unchanged artifacts and no schema migration. Temporary API/frontend servers and the disposable PostgreSQL cluster were stopped afterward. This was live HTTP and DOM integration verification, not an interactive browser review or a full latest-main application test. The archive is dated 7 November; no claim is made about uninspected newer main changes. Li should still repeat his exact integration test.
