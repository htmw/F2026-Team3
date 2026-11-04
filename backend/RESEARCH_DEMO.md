# Sprint 2 research prediction endpoint

GET /api/v1/research/enrollments/{enrollment_id}/risk-prediction

The endpoint reads only the server-configured synthetic LMS fixture and academic CSVs. It calls simulated_lms.build() then predict.predict() in memory. Frozen model/map/source hashes are verified before trusted local deserialization; artifacts are cached per process. Unavailable coverage bypasses model loading and remains unscored. Requests never retrain, recalibrate, write predictions, access test datasets, call a database or contact a live LMS.

## Local demonstration without database configuration

From PowerShell:

```powershell
cd C:\Users\nhesv\Documents\AcadMate-Team
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-research-demo.txt
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:ACADMATE_RESEARCH_DEMO_ENABLED = 'true'
.\.venv\Scripts\python.exe -m uvicorn research_demo:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001/docs . In another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/v1/research/enrollments/20014/risk-prediction
Invoke-RestMethod http://127.0.0.1:8001/api/v1/research/enrollments/20044/risk-prediction
```

20014, 20024 and 20034 are ready cases; 20044 has an unavailable activity feed. The database-free host intentionally includes only the research router. The same router is registered in backend/main.py alongside the unchanged student router. Launching main:app still requires the preexisting database environment/driver configuration; that behavior was not changed. No .env is created by this feature.

Required trusted local files (not committed): ml/outputs/baselines-v1/logistic_regression.joblib and ml/outputs/calibration-v1/calibration_maps.joblib. The freeze specification is ml/configs/FINAL_EXPERIMENT_V1.json. A fresh clone needs a separately supplied approved artifact bundle matching those hashes. The endpoint must never train missing artifacts automatically. Copying arbitrary joblib files is unsupported.

## Response and errors

Response fields: schema_version, research_only, source_kind, enrollment_id, student_id, course_id, as_of_day, generated_at_utc, status, research_risk_probability, reason, model_version, calibration_method, warnings. IDs are positive integers matching existing API schemas. Probability is finite and in [0,1], or null for unavailable. as_of_day is simulated relative time; generation time is not the data's calendar date. No risk bands, automatic alerts or individual explanations are supplied.

- 200: scored_research_demo, or unavailable with null probability and a reason.
- 404: enrollment not present in fixture; does not assert absence from the database.
- 422: FastAPI's normal validation response for invalid/zero/negative IDs, matching existing parameter-validation behavior.
- 503: disabled demo, bad inputs, unavailable dependencies/artifacts or integrity failure. Structured error: error.code/message/details, without private paths in HTTP responses. Details are logged server-side.

Enable explicitly with ACADMATE_RESEARCH_DEMO_ENABLED=true. Default is disabled. This is a local research demo, with no new authentication or externally exposed service. Brightspace remains the intended architecture; fixture fields are not verified Brightspace API semantics. Early probabilities may overestimate risk and are not validated on AcadMate students.

## Tests

```powershell
cd C:\Users\nhesv\Documents\AcadMate-Team
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:RUN_RESEARCH_ARTIFACT_SMOKE = 'true'
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s ml/tests -v
.\.venv\Scripts\python.exe -m pip check
```

Do not use unrestricted discovery over backend/: backend/test_db.py intentionally connects to a database. The new API tests stub database imports/dependencies for existing route registration. The optional real-artifact test verifies actual predict.predict calls, finite scored responses, artifact caching, no pipeline refit/network calls/output writes, and unchanged fixture/academic hashes. Without RUN_RESEARCH_ARTIFACT_SMOKE=true that test is explicitly skipped.

Existing pinned Starlette emits an httpx TestClient deprecation warning. Tests currently pass with httpx==0.28.1; migration to its preferred client is deferred to avoid unrelated dependency changes.
