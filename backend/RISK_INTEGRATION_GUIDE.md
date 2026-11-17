# AcadMate Academic Risk MVP — Main Backend Integration Guide

## 1. Integration Status

The database-backed Academic Risk MVP has been integrated into the
Main FastAPI application as an additive research-only feature.

Integration commits:
- Phase 1: 0df4528 — ML research foundation and prediction API
- Phase 2: f0f6e54 — Database-driven Academic Risk MVP API

The existing Student and Advisor APIs remain registered.

This integration has been validated locally using synthetic data.
It is not a production deployment or an institutionally validated
academic risk prediction system.

## 2. Architecture

The Main FastAPI application contains two distinct data workflows:

- Existing Student/Advisor APIs use the Main application database.
- Database-driven Research Risk APIs use a separate, disposable,
  loopback-only PostgreSQL research database.

The Risk MVP is implemented under:

    backend/risk_mvp/

Its HTTP router is registered in:

    backend/main.py

The Risk MVP must not modify or initialize the team's shared Neon
database.

## 3. Python Dependencies

Install the Main Backend and ML dependencies from the repository root:

    python -m pip install -r backend/requirements.txt
    python -m pip install -r ml/requirements.txt

Use the Python interpreter associated with the project's virtual
environment.

The local integration was tested with the installed Main Backend
dependencies and the frozen research ML environment.

Dependency verification:

    python -m pip check

A clean-environment deployment has not yet been validated.

## 4. Environment Configuration

Main Backend:

    DATABASE_URL=<main application database URL>

Optional dedicated test database:

    TEST_DATABASE_URL=<dedicated disposable test database URL>

Research Risk MVP:

    ACADMATE_RISK_DATABASE_URL=<local research database URL>
    ACADMATE_RISK_MVP_ENABLED=false

The Risk MVP feature flag is disabled by default. Set it to true
only for controlled local research testing.

The Risk database connector accepts only loopback hosts
(127.0.0.1 or localhost) and database names beginning with
acadmate_risk_demo.

The locally verified research database used:

    Host: 127.0.0.1
    Port: 55439
    Database: acadmate_risk_demo_sprint2

This local setup is an example, not a required database location
for every team member.

Do not connect this research workflow to shared Neon or live
institutional data.

## 5. Frozen ML Model Artifacts

The inference service requires these files:

    ml/outputs/baselines-v1/logistic_regression.joblib
    ml/outputs/calibration-v1/calibration_maps.joblib

Expected SHA-256 digests:

    logistic_regression.joblib
    93cab4b90d3fc755b087be6343673b47ec3b163f4d4a8d3aace93e356fcb0020

    calibration_maps.joblib
    d9ef14cad9c5d0cc8731e68b02633bb831ebed7a8ba6bb255bef2513f7be88e7

These artifacts are excluded from Git by ml/.gitignore.

They must be supplied separately through a trusted team-approved
artifact handoff and verified against:

    ml/configs/FINAL_EXPERIMENT_V1.json

Do not automatically retrain or replace the frozen artifacts.

Loading serialized model files from untrusted sources is unsafe.
Only load files from the verified handoff.

## 6. API Endpoints

The following routes are registered in the Main FastAPI application:

GET /api/v1/research/database/students

GET /api/v1/research/database/students/{student_id}/insights

GET /api/v1/research/database/enrollments/{enrollment_id}/risk-assessment

Example assessment request:

    GET /api/v1/research/database/enrollments/20024/risk-assessment?cutoff=2027-02-08T23:59:59.999999Z

The cutoff must be timezone-aware and represent the end of a
UTC day.

Possible outcomes include:

- 200: Scored or explicitly unavailable research assessment.
- 404: Unknown student or enrollment.
- 422: Invalid path parameter or cutoff.
- 503: Disabled research demo or unavailable dependencies.

Main application error handlers may produce the common AcadMate
error envelope rather than FastAPI's default detail field.

The existing fixture-based research prediction endpoint is retained:

    GET /api/v1/research/enrollments/{enrollment_id}/risk-prediction

## 7. Local Verification

Completed integration checks:

- Main OpenAPI registration: 105 paths, including three new
  database-backed Risk API routes.
- Feature flag disabled by default: HTTP 503 as expected.
- Main ORM and Research PostgreSQL schema compatibility: verified.
- Main application HTTP integration: HTTP 200.
- Enrollment 20024 frozen research probability:
  0.2169211773909568.
- Phase 1 Research API tests: 5 passed, 1 skipped.
- Risk schema compatibility tests: 4 passed, 1 skipped.
- Existing Student/Advisor regression tests: 22 passed.
- Python package dependency check: passed.
- Frozen model file hashes: verified.

Example safe test commands, from the repository root:

    python -m pytest backend/tests/test_research_predictions.py --noconftest -q

    python -m pytest backend/tests/test_risk_schema_compatibility.py --noconftest -q

Set PYTHONPATH to include backend and ml/src before running
these tests. Main application imports also require DATABASE_URL.

For the schema compatibility suite, keep RUN_RISK_DB_TESTS=false
unless explicitly performing the isolated PostgreSQL tests.

IMPORTANT: The general backend/tests/conftest.py fixture executes
SQLAlchemy drop_all(), create_all(), and seed() against the configured
test database. Do not run database-backed regression tests until
TEST_DATABASE_URL has been verified to point to a dedicated,
disposable local test database.

Never point destructive tests at shared Neon or the Research Demo
database.

## 8. Current Limitations and Remaining Work

- Results are derived from synthetic research data.
- Predictive validity on institutional student data is unproven.
- The Research Risk API is not yet an authenticated production feature.
- Advisor authorization and assigned-student access require review.
- The Risk MVP React advisor page has not been integrated into
  the Main frontend as part of this backend integration.
- Proposed shared database migrations have not been applied.
  Datta must review the eventual shared schema before changes.
- Frozen model files are not included in Git.
- The disposable research database is not included in Git.
- Clean-checkout setup and artifact provisioning still require
  a documented team handoff and validation.

Keep the feature disabled outside controlled local research demos.

## 9. References

Original research documentation in Tafa's Risk Review:

- backend/RISK_MVP.md
- backend/RISK_QUERY_COMPATIBILITY.md
- backend/risk_mvp/API_CONTRACT.md

This guide describes the verified Main Backend integration and
does not replace the detailed research methodology or API contract.
