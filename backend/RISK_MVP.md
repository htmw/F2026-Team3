# Sprint 2 database-backed academic risk MVP

This local synthetic workflow extends the existing academic data without modifying the original models, CSVs, frozen ML code or results. The schema is prepared separately under risk_mvp/ and migrations/proposed/001_risk_mvp.sql for Datta's review. No shared database migration is applied. Namespaced tables exist only in a new disposable local PostgreSQL cluster for tests/demo.

## Working flow

Advisor selects a synthetic student -> current academic insights -> active enrollment and explicit end-of-day UTC cutoff -> read-only PostgreSQL transaction -> temporal version/coverage checks -> unchanged 16-feature calculation -> actual frozen logistic regression and sigmoid -> research estimate plus evidence -> React advisor page.

The original /api/v1/research/enrollments/{id}/risk-prediction fixture endpoint is preserved. New routes:

- GET /api/v1/research/database/students
- GET /api/v1/research/database/students/{student_id}/insights
- GET /api/v1/research/database/enrollments/{enrollment_id}/risk-assessment?cutoff=2027-02-08T23:59:59.999999Z

Academic insights are the current recorded snapshot, not historical as-of GPA. GPA/credit calculations match existing student-profile behavior and are explicitly policy-unconfirmed. Failed/withdrawn courses are descriptive. Scores are available only after their synthetic release timestamp, displayed descriptively and excluded from frozen inference.

## Local setup

PostgreSQL 18 binaries must be installed at C:\Program Files\PostgreSQL\18\bin. The bootstrap owns only ml/outputs/pg-risk-mvp, port 55439 and database acadmate_risk_demo_sprint2. It uses local trust authentication in this loopback-only disposable cluster containing synthetic data; never use this configuration for institutional data or network deployment. It never connects to the existing PostgreSQL service or shared database. It refuses unexpected cluster/port state and nonmatching existing table counts rather than overwriting.

From PowerShell at repository root:

```powershell
cd C:\Users\nhesv\Documents\AcadMate-Team
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-research-demo.txt
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m risk_mvp.bootstrap
$env:ACADMATE_RISK_DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_sprint2'
$env:ACADMATE_RISK_MVP_ENABLED = 'true'
$env:ACADMATE_RESEARCH_DEMO_ENABLED = 'true'
$env:OMP_NUM_THREADS = '2'
.\.venv\Scripts\python.exe -m uvicorn research_demo:app --host 127.0.0.1 --port 8002
```

In a second terminal:

```powershell
cd C:\Users\nhesv\Documents\AcadMate-Team\frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Open http://127.0.0.1:5175/advisor/academic-risk . Select student 10001 for a scored example; select student 10000 for an incomplete activity-feed example. Default cutoff is simulated 2027-02-08 (course day 28), not today's date. The Vite proxy targets API port 8002 by default, only for the new research namespace; ACADMATE_API_TARGET can override the local target.

Trusted existing frozen model and calibration files must remain under their documented ignored ml/outputs paths. They are not committed and must be provisioned separately on another checkout; no automatic training occurs. The demo model version/hash remains the original frozen experiment.

Stop the API and frontend with Ctrl+C. Stop only this disposable cluster when finished:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D 'C:\Users\nhesv\Documents\AcadMate-Team\ml\outputs\pg-risk-mvp' -m fast -w stop
```

No recursive cleanup or database drop is needed. Bootstrap restarts and preserves the demo on the next run.

## Generator and schema

`python -m risk_mvp.generate --output ml/outputs/risk-mvp-new/bundle.json` generates another deterministic sidecar without loading it. Existing destinations are refused. --load-local is permitted only with an explicitly named loopback acadmate_risk_demo* database and refuses nonempty academic data. Bootstrap is the recommended repeatable demo command.

Eight additive tables: offerings, enrollment links, assessment identities, assessment versions, submission versions, LMS activity events, source coverage, and enrollment history. Base declarations are copied to separate metadata for disposable creation; backend/models.py and its metadata are not changed. Prepared SQL creates only risk_ tables and indexes, with no ALTER/DROP statements. It is not a production migration approval. Cross-offering/course consistency is validated by the generator/importer and read service; SQL foreign keys enforce record existence. A future shared ingestion writer should add composite-key enforcement or equivalent transactional checks after Datta's review.

Seed 20261104, fixed UTC calendars and 112-day durations are simulation configuration, not academic policy. All 800 original enrollments receive offering links/history; the 179 active Spring 2027 enrollments receive activity, assessment submissions and complete/incomplete feed cases. Patterns vary by deterministic student-key hash: high, moderate, declining, late, missed, improving and feed gap. Engagement and score variation are not target labels. No probabilities are generated as constants or used to construct risk outcomes.

Assessment/submission changes are append-only versions selected by known_at <= cutoff. UTC-normalized date conversion is essential even if PostgreSQL returns session-local timestamps. Current MVP supports UTC offerings, end-of-day cutoffs from day 7 until course end, one submission attempt per assessment and non-exam TMA events. Coverage checkpoints exist at days 7,14,...,84. A date without declared complete coverage remains unscored; no feed is imputed as zero. Coverage ends at the declared checkpoint, not inferred from event presence.

## Tests

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:RUN_RISK_DB_TESTS = 'true'
$env:RUN_RESEARCH_ARTIFACT_SMOKE = 'true'
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s ml/tests -v
node --test frontend/tests/research-api.test.js
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe -m pip check
```

Database tests explicitly opt in and roll back mutations. They verify actual PostgreSQL referential integrity/read-only behavior, deterministic generation, day-window goldens, temporal leakage isolation, actual model inference, academic summary compatibility, API errors and original endpoint registration. They never touch the final research holdout. The historical frozen results remain preserved.

## Limitations

This validates software flow on synthetic data, not predictive accuracy on AcadMate students. Early estimates can overstate risk. No live Brightspace mapping, operational thresholds, new academic policies, fallback model training, persisted prediction history or authentication rollout is included. Original full main:app still requires its existing database configuration; research_demo:app hosts the same research routers independently.

Browser interaction QA was stopped by Computer Use because it could not establish the current browser URL for policy enforcement. No alternate browser-control path was attempted. Production build, client helper tests, direct HTTP and frontend-proxy/API integration were verified; manual interactive page verification remains necessary.

## Expanded end-to-end verification and audit

The advisor now preserves successful course predictions if another course request fails, provides retry after initial API failure, and shows completion percentage plus recent interaction counts/change. These are factual indicators, separated from model estimates. See risk_mvp/API_CONTRACT.md for field/null/error behavior and ml/reports/SPRINT2_END_TO_END_VERIFICATION.md for cohort statistics and verification evidence.

With the disposable database running, reproduce the read-only cohort audit with a NEW output filename:

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\ml\src"
$env:ACADMATE_RISK_DATABASE_URL = 'postgresql+psycopg://acadmate_demo@127.0.0.1:55439/acadmate_risk_demo_sprint2'
.\.venv\Scripts\python.exe -m risk_mvp.audit --cutoff 2027-02-08T23:59:59.999999+00:00 --output ml/outputs/risk-mvp-verification/audit-new.json
```

Frontend tests now include React/JSDOM component interactions. The optional live component integration test requires both documented API/frontend servers to be running:

```powershell
cd frontend
$env:RUN_LIVE_ADVISOR_TEST = 'true'
npm.cmd test
```

Without the opt-in, the live test is explicitly skipped; other component/helper tests run offline. The live test selects a real synthetic student with multiple courses, requests actual predictions through the Vite proxy and checks rendered results in a DOM environment. This is automated component/API integration, not interactive browser verification. The earlier browser URL-policy block remains; no alternate browser automation is used.
