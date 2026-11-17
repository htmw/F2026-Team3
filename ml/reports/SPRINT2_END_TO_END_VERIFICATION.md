# Sprint 2 end-to-end verification — 2026-11-04

Branch: feature/academic-risk-prediction. Complete local workflow verified using the documented disposable PostgreSQL database, API and frontend proxy. No shared database, original academic records, frozen model/preprocessing/calibration, or previous research results were changed. Nothing was staged, committed, pushed or merged.

## Verified workflow

- Bootstrap restarted the existing isolated cluster without reseeding; API and frontend were started using documented ports/environment.
- 100 synthetic students and 179 active enrollments retrieved. There are 69 students with multiple active courses.
- Original student routes and fixture endpoint remain registered and regression-tested.
- Real inference uses the frozen model and sigmoid artifacts, with hash verification and no fitting.
- Automated live React/JSDOM integration selected student 10015, displayed two active courses, and obtained/rendered actual PostgreSQL-backed model responses through the Vite proxy.
- Separate component tests verified scored plus missing-coverage courses, partial HTTP failures, academic information, engagement/completion evidence, warnings and retry after initial backend failure.
- Direct API/PostgreSQL tests verify read-only access, referential integrity, hand-calculated 7/14/28-day features, future/late-event isolation and incomplete coverage.

## Defects fixed

1. Promise.all previously discarded all course results if one request failed. Per-course client error states now preserve successful courses.
2. Submission counts/late-rate evidence could look complete despite missing schedule coverage. All dependent evidence now requires both sources; unaffected activity evidence remains visible.
3. Ineligible early/ended/not-known enrollments could still reach feature calculation for descriptive evidence. They now return a specific reason without derived features/evidence.
4. Initial backend failure required page reload. A student-list retry control now recovers without a reload.
5. FastAPI validation arrays could render as [object Object]. Messages are now readable.
6. Missing score information is labeled unavailable rather than being confused with a verified absence of released scores.

No generated data was changed to alter prediction distributions. Post-fix probabilities match every pre-fix probability exactly.

## Actual cohort inference audit

Cutoff: 2027-02-08T23:59:59.999999+00:00. Evaluated 179; scored 156; unscored 23. All 23 unscored cases have incomplete activity coverage. They retain trustworthy submission/assessment evidence and null probability.

| Statistic | Probability |
|---|---:|
| Min | 0.146993 |
| Max | 0.944254 |
| Mean | 0.379249 |
| Median | 0.315176 |

| Probability interval (report bins only) | Enrollments |
|---|---:|
| [0.0, 0.1) | 0 |
| [0.1, 0.2) | 18 |
| [0.2, 0.3) | 52 |
| [0.3, 0.4) | 26 |
| [0.4, 0.5) | 24 |
| [0.5, 0.6) | 19 |
| [0.6, 0.7) | 6 |
| [0.7, 0.8) | 2 |
| [0.8, 0.9) | 5 |
| [0.9, 1.0] | 4 |

## Pattern comparisons

| Generation pattern | Scored count | Mean | Median |
|---|---:|---:|---:|
| declining | 18 | 0.270775 | 0.274077 |
| high | 37 | 0.251423 | 0.219096 |
| improving | 18 | 0.309489 | 0.294198 |
| late | 26 | 0.506290 | 0.499391 |
| missed | 20 | 0.708939 | 0.670516 |
| moderate | 37 | 0.326301 | 0.286941 |

Feed-gap pattern: 23 unscored, not assigned a replacement probability. Pattern labels are construction metadata, not truth labels. The improving pattern affects synthetic scores, which are excluded from the frozen model; it is not evidence that improved grades caused lower risk.

| Observed submission grouping | Scored count | Mean | Median |
|---|---:|---:|---:|
| no observed late submissions | 65 | 0.282003 | 0.236324 |
| no overdue work | 108 | 0.304157 | 0.281047 |
| no submissions | 7 | 0.905123 | 0.903520 |
| observed late submissions | 84 | 0.410676 | 0.403643 |
| overdue work present | 48 | 0.548206 | 0.516476 |

Submission groupings overlap; these are descriptive comparisons, not causal effects or accuracy estimates. Histogram bins are not operational risk thresholds.

## Suspicious-behavior investigation

- No identical probability groups, duplicate complete feature vectors, nonfinite features/probabilities, or exact zero/one outputs were found.
- Expected nulls: lateness rate and days since submission for seven enrollments with confirmed no submissions; days since activity for one enrollment with confirmed no positive activity. No unexplained null patterns were found.
- All 156 vectors match the frozen feature order and unchanged feature function. Hand-calculated and leakage tests additionally verify the database mapping.
- The largest high-engagement estimate (enrollment 20604, 0.668117) coexists with two overdue assessments and all observed submissions late. Other input signals vary; high engagement is not a risk guarantee or a causal explanation.
- Declining-engagement cases have lower mean output than moderate cases at this day-28 cutoff. The generator declines over an 85-day sequence, early activity can remain substantial, and submission patterns vary. No data was manipulated to force a different ranking.
- Full audit elapsed 4.48 seconds, including extracting features twice per enrollment for inspection/inference. This is a local batch observation, not an API latency SLA.

## Tests and verification limits

- 19 backend/API/PostgreSQL tests: PASS, including original endpoint regression and real artifacts.
- 41 existing ML tests: PASS. Tiny test fixtures exercise training code, but real models were not retrained or reevaluated on the consumed holdout.
- Eight frontend tests: PASS, comprising helper tests, React DOM interaction tests and explicit live proxy/PostgreSQL/model component integration.
- Production frontend build: PASS. npm audit: zero vulnerabilities. pip check: no broken requirements. git diff --check: PASS.
- Interactive browser verification was not performed because of the earlier Computer Use browser-URL policy block. No alternate browser-control mechanism was used. Live DOM integration is automated and does not establish real-browser layout/accessibility/interaction correctness.
- Existing Starlette/httpx TestClient deprecation warning persists but is non-failing.

## Advisor improvements

Added interactions over 7/28 days, raw change versus prior 7 days, completion percentage for work due, per-course request errors, and backend retry. Zero remains distinct from unknown. Academic facts, released scores and engagement indicators remain separated from model estimates; no risk bands, automated actions or causal explanations were added.

## Changes in this verification pass

New: backend/risk_mvp/audit.py; backend/tests/test_risk_audit.py; frontend/tests/academic-risk.test.js; backend/risk_mvp/API_CONTRACT.md; this report.
Modified: backend/risk_mvp/service.py; backend/tests/test_risk_mvp.py; frontend/src/pages/advisor/AcademicRisk.jsx; frontend/src/research/api.js; frontend/tests/research-api.test.js; frontend/package.json/package-lock.json (pinned jsdom 30.1.3 and test command); backend/RISK_MVP.md.
Generated before/after audit JSON and local patch/integrity scripts are under ignored ml/outputs/risk-mvp-verification or ml/outputs; they must not be committed.

## Integration readiness and remaining boundaries

Authored source, tests, contracts, manifests, fixtures and reports are ready for review. Include the narrowly scoped existing router/page/proxy additions and pinned dependency changes. Exclude ml/outputs, PostgreSQL data/logs, model files, original raw OULAD data, environments, node_modules, dist, credentials and temporary scripts. Nothing has been staged.
Datta approval is still required for backend/migrations/proposed/001_risk_mvp.sql, schema naming/conventions and shared ingestion cross-offering constraints. No shared migration was executed. Current application remains loopback/disposable only; deployment authentication and institutional data governance are not implemented.
Frontend teammates should use backend/risk_mvp/API_CONTRACT.md. Response evidence fields are nullable and availability-specific; request_error is a client-only per-course state. Keep synthetic source, cutoff, model version and warnings visible.
Trusted frozen model files must be provisioned separately on another checkout, matching hashes. Current calendars are UTC, courses last 112 simulated days, and coverage exists only at declared checkpoints; noncovered dates may legitimately remain unscored.
Next high-value work: manual real-browser layout/accessibility check; Datta schema/ingestion review; package trusted artifacts for teammates; add identity/authorization before any nonlocal deployment. Persisted prediction history or fallback-model experiments require separate scope/evaluation decisions. Do not retune using the consumed holdout.

Synthetic results demonstrate functioning integration, not accuracy, calibration or intervention benefit for real students.
