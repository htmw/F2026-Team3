# AcadMate fixed synthetic academic dataset

Status: ready for team review. Database import and academic-policy approval are separate steps.

This is the existing Sprint 1 dataset, authored once and transferred from
`C:/Users/nhesv/Projects/AcadMate/data/synthetic` to
`C:/Users/nhesv/Documents/AcadMate-Team/data/synthetic`.
All eight table CSVs and the scenario metadata CSV are byte-identical to the source.
Records have not been regenerated. CSVs are the permanent source of truth.

The current repository is `htmw/F2026-Team3`, branch
`feature/synthetic-academic-dataset`, based on `feature/backend-integration`.
The latest fetched integration commit at review was
`5f19acc5e2dd4c26cd44d76036f3d0329bf92ece`; local backend files matched it.
No branch switch, commit, push, merge or PR was performed.

## Contents and counts

| Model CSV | Rows | Purpose |
| --- | ---: | --- |
| users.csv | 105 | 100 student accounts, four advisor accounts, one admin account |
| programs.csv | 1 | Preserved MS Computer Science program, 30 required credits |
| students.csv | 100 | Student identity, user and program references |
| advisors.csv | 4 | Advisor-to-user references |
| advisor_student_assignments.csv | 100 | Exactly one advisor per student, 25 students per advisor |
| courses.csv | 30 | Course catalog; three credits per course in this fixed dataset |
| enrollments.csv | 800 | Individual attempts across the fixed synthetic term timeline |
| program_requirements.csv | 3 | Core 9, Electives 18, Capstone 3; provisional MVP allocation |

`student_scenarios.csv` has 100 metadata rows, one primary label per student. It is not
a database table. Other files include the schema dictionary, validator, mutation tests,
manifest/checksums, reviewed schema references, transfer evidence and validation reports.
`INTEGRATION_GUIDE.md` describes a proposed safe import; it is not an importer.

## Canonical schema and seed preservation

The validator checks this checkout's actual `backend/models.py` and parses
`backend/seed_data.py` with AST, without executing the seed script. It additionally
checks the reviewed reference sources and CSV checksums in `DATASET_MANIFEST.json`.

- Enrollment statuses: `in_progress`, `completed`, `failed`, `withdrawn`.
- Requirement arrays use only `eligible_course_ids`; `course_ids` is absent.
- CSV headers match the model columns and order. No stored GPA or calculated-credit
  fields were added to students.csv.
- Original IDs and literal values are preserved: users 1/2, program 1, student 101,
  advisor 201, courses 11/12/13, enrollments 301/302/303, assignment 101 -> 201,
  and Core requirement 401. Enrollment 303 is `in_progress`; Core eligibility is [11,12,13].
- The assignment timestamp in the fixed CSV remains
  `2026-10-13T17:46:30.595292-04:00`. Datta's script uses `datetime.now(timezone.utc)`,
  so another database execution can legitimately have a different timestamp. That is
  operational metadata, not evidence of academic-data corruption. Do not rewrite the
  fixed CSV or an existing database timestamp to make them equal; see the proposed
  timestamp-only exception in the integration guide.

The earlier ZIP workspace used the legacy spellings. Its approved canonical transition
is recorded in the original manifest; this transfer does not repeat that transition.
The creation hashes in the manifest are historical provenance, not a requirement that
the genuine clone contain the ZIP workspace's old backend implementation.

## Academic scenarios

| Mutually exclusive primary label | Students |
| --- | ---: |
| high_performing | 20 |
| average_performing | 25 |
| low_performing | 15 |
| declining | 10 |
| improving | 10 |
| failed_and_repeated | 10 |
| withdrawals | 5 |
| new_without_completed | 5 |

The fixed histories include 606 completed, 179 in-progress, 10 failed and five withdrawn
attempts. Five students have no GPA; 15 have 27 completed credits under the current
completed-and-graded filter. Returning students have multiple terms, and declining/
improving students have at least three strictly directional graded terms. New students
have only Spring 2027 in-progress attempts. There are no duplicate student/course/term
attempts. Ten student/course pairs have repeats in distinct terms; five students have
two completed attempts after a failed attempt, deliberately exercising repeat-credit behavior.

The snapshot term is Spring 2027, independent of wall-clock date. Earlier terms are
Fall 2025, Spring 2026, Summer 2026 and Fall 2026. Each student has at most four
three-credit courses in one term as a synthetic realism convention, not a registration rule.

## Academic decisions pending team approval

These conventions are not official Pace University policy and were not changed by this review.

| Grade | Provisional grade points |
| --- | ---: |
| A | 4.0 |
| A- | 3.7 |
| B+ | 3.3 |
| B | 3.0 |
| B- | 2.7 |
| C+ | 2.3 |
| C | 2.0 |
| C- | 1.7 |
| D | 1.0 |
| F | 0.0 |

Completed rows have passing provisional grades. Failed rows are F/0.0. Withdrawn and
in-progress rows have NULL grades/points and do not contribute earned credits under
the current completed-and-graded filter. Do not infer an official passing threshold.
Confirm failed-attempt inclusion in the GPA denominator; grade-repeat replacement,
highest/latest-attempt selection and repeated-course credit deduplication; completed
records with null grade points; the grade scale and scenario bands; and the proposed
Core 9/Electives 18/Capstone 3 allocation. No prerequisites or graduation approval are inferred.

Synthetic scenario bands are high 3.7-4.0, average 2.5-3.5 and low 1.0-2.3 under the
existing filter. Labels are test cases, not institutional risk classifications. Numerical
ranges can overlap another student's primary situation without assigning two labels.

After a future approved import, student 101's five additional historical electives
will yield eight attempts, 21 completed credits and GPA approximately 3.23 under the
documented filter. The three seed attempts themselves remain unchanged. The dataset
does not store these calculated values in students.csv.

## Validate locally without a database connection

From the project root, create a virtual environment only if one does not already exist:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r data/synthetic/requirements-validation.txt
.\.venv\Scripts\python.exe -B data/synthetic/validate_dataset.py
.\.venv\Scripts\python.exe -B data/synthetic/test_validate_dataset.py -v
```

The ignored clone-local environment was verified on October 16, 2026 with Python 3.13.14,
SQLAlchemy 2.1.1 and typing_extensions 4.16.0. The older workspace environment's 2.1.4
binaries were blocked by Windows Application Control; a fresh environment with the working
version resolved validation without changing security settings. Backend requirements were
not changed. requirements-validation.txt is only for dataset validation, not backend startup.

The validator checks actual checkout models and seed literals plus pinned references
and fixed CSV checksums. It does not load .env, import database.py, connect to PostgreSQL/
Neon, execute seed scripts or write CSVs. Tests mutate temporary copies only. All 16
check groups and 31 tests passed. The database-connect diagnostic backend/test_db.py
is intentionally not part of this database-free test run. Use -B to avoid caches.

Scoped .gitattributes preserves fixed CSV and reviewed-source bytes across checkouts.
Do not normalize exact reference files or rewrite CSVs just to remove upstream formatting.

## Files and fictional identities

New identities use `example.invalid`; the existing demo @pac.edu addresses remain
unchanged. All new names are fictional constructions. password_hash fields contain
nonfunctional demo placeholders, not real passwords or usable authentication hashes.
The dataset does not implement authentication. No .env, real credentials, virtual
environments or cache files belong in the Git review. Do not execute reference seed files.

The original manifest, schema references and transfer evidence are retained. Older
machine-readable evidence explicitly labeled historical describes the prior workspace;
VALIDATION_REPORT.md describes this review. No replacement dataset was generated.

## Shared database preparation

Datta owns Neon/schema setup. This task did not connect to Neon, inspect a target
database, change DATABASE_URL/.env, import records, create tables or run migrations.
The dataset is technically ready for review, not approved for a shared import.
See INTEGRATION_GUIDE.md for order, FK dependencies, duplicate handling, atomic rollback
and post-import verification. No importer or reset operation is implemented here.
