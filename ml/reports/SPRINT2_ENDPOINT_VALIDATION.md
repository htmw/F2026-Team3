# Sprint 2 endpoint implementation validation — 2026-11-04

Branch: feature/academic-risk-prediction. No commits, pushes, merges or database changes.

## Delivered files

Created backend/routers/research_predictions.py, backend/schemas/research_predictions.py, backend/services/research_predictions.py, backend/research_demo.py, backend/tests/test_research_predictions.py, backend/requirements-research-demo.txt, backend/RESEARCH_DEMO.md, and this report. Modified backend/main.py only to import/register the router. Extended ml/.gitignore to explicitly exclude serialized models, generated CSVs, archives, local datasets/environments and temporary files. All existing ML source, specifications, fixtures and historical reports are preserved.

The service has no database dependency. It lazily imports ML packages, uses fixed repository-local paths, verifies frozen configuration and code/artifact hashes before loading trusted joblib files, caches artifacts per process, and calls existing simulated_lms.build() and predict.predict(). It returns unavailable coverage without loading or invoking the model. No hardcoded probabilities, retraining, live LMS requests or prediction-file writes are introduced.

## Actual checks

- Existing 41 ML tests: PASS.
- Six API tests, including explicitly enabled real-artifact smoke test: PASS.
- pip check: no broken requirements.
- Real artifact outputs: 20014 -> 0.3783828964; 20024 -> 0.8484056211; 20034 -> 0.9727812511. These are measured outputs, not constants in service code.
- 20044: HTTP 200 unavailable with null probability; artifact loader not called.
- Disabled demo and missing artifacts: HTTP 503, sanitized structured error.
- Integrity mismatch: HTTP 503 before joblib deserialization.
- Unknown fixture enrollment: 404. Invalid/zero/negative IDs: FastAPI 422.
- Scored/unavailable schema consistency enforced.
- Both research and existing student-profile paths registered in main; existing student not-found response preserved with stubbed database dependencies.
- Real smoke test confirms inference calls and two artifact deserializations across three requests (cached thereafter); no Pipeline.fit, external socket connection or Path output writes; academic and fixture hashes unchanged.

The student registration test initially re-imported its dependency after leaving the database stub scope. The test was corrected to patch the already-imported module. No database connection was made. The service and student/database code required no such change.

## Version-control audit

Before endpoint coding, the 33 authored ML files were inventoried, Python parsed, JSON decoded, and text inspected for credential patterns (with encoding fallback for original legacy reports). No credential-pattern matches were found; this is a targeted audit, not a guarantee against every possible secret format. All 27 generated files found during the final audit were ignored. This report adds another authored document. No credentials or .env files were added. The local audit utility under ignored ml/outputs/ is temporary and should not be committed.

Recommend committing authored ML code/tests, pinned requirements, documentation/reports, hand-authored JSON demo fixtures, the freeze specification and ml/.gitignore; plus the new backend deliverables and minimal main.py router registration. Do not commit ml/outputs/, trained joblib artifacts, generated CSVs, raw OULAD ZIP/data, virtual environments, credentials or temporary files. Nothing has been staged.

## Remaining limitations

The existing full app initializes SQLAlchemy database configuration during import; there is no backend/.env in this checkout. Its behavior is preserved. backend/research_demo.py is a minimal database-free host for the exact same router, enabling local demonstration without touching database configuration. Full app startup still needs its existing environment/driver setup. Model artifacts are intentionally ignored and must be provisioned separately for another checkout, matching frozen hashes.

The pinned Starlette TestClient emits a deprecation warning for httpx; current tests pass. No frontend wiring or authentication rollout is included. Keep the host on loopback for the demonstration. Predictions remain research-only, especially early in a course, and actual Brightspace compatibility is unverified. Full instructions and exact local commands are in backend/RESEARCH_DEMO.md.
