# Publication verification — October 16, 2026

PASSED: 16 dataset validation groups and all 31 tests (zero failures, errors or skips)
ran in the new ignored clone-local .venv with SQLAlchemy 2.1.1. Existing CSV bytes,
counts, seed records, backend code and academic rules remain unchanged. The previous
Application Control error affected SQLAlchemy 2.1.4 in the old workspace environment;
the fresh working environment resolves it without changing any security setting.

requirements-validation.txt pins dataset-only dependencies. No PostgreSQL/Neon connection,
.env change or import occurred. backend/test_db.py was not executed because it connects
to a database; all dataset tests were executed. Academic policy/import approval remains
pending. Publication is limited to the feature branch; no PR or merge is part of it.
Evidence: PUBLICATION_CHECKS.json and validator-test-results.txt. Earlier report follows.

---

# Dataset validation and review-readiness report

Review date: October 14, 2026 (America/New_York).

| Area | Status | Evidence / boundary |
| --- | --- | --- |
| Repository/branch/remote/base | PASSED | Genuine clone; feature/synthetic-academic-dataset; htmw/F2026-Team3; integration ancestry verified |
| Latest integration comparison | PASSED | Fetched integration HEAD 5f19acc5e2dd4c26cd44d76036f3d0329bf92ece; no backend differences |
| Fixed dataset transfer | PASSED | Already present from prior transfer; all nine CSVs match original SHA-256, no overwrite/regeneration needed |
| Canonical schema and seeds | PASSED | Current models/seed literals checked; canonical status/array column; removed column absent |
| Executed validation/tests | PASSED | All 16 groups and 31 tests; no failures/errors/skips |
| Ready for team review | PASSED | Dataset, dictionary, policies and proposed safe integration steps documented |
| Academic policy decisions | PENDING APPROVAL | Provisional scale, failed/repeated-attempt GPA/credits, null-grade treatment, requirement allocation |
| Shared Neon import | PENDING APPROVAL | Not authorized, attempted or verified; Datta owns setup/migrations |
| Independent clone environment | BLOCKED | No venv; backend requirements omit SQLAlchemy/PG drivers; existing source-workspace interpreter used |
| Technical validation failures | None | No failed final checks; pending policies are not technical validation failures |

## Locations and preservation

Source: C:/Users/nhesv/Projects/AcadMate/data/synthetic.
Destination: C:/Users/nhesv/Documents/AcadMate-Team/data/synthetic.
HEAD: 5f19acc5e2dd4c26cd44d76036f3d0329bf92ece. No tracked modifications existed at the start; data/ was
already untracked. Existing destination contents were compared before any documentation
updates. No CSV was overwritten, edited or regenerated. Original source files remain
unchanged. The original manifest and pinned model/seed sources remain unchanged.

## Exact table counts

| CSV | Records | Result |
| --- | ---: | --- |
| users.csv | 105 | PASSED |
| programs.csv | 1 | PASSED |
| students.csv | 100 | PASSED |
| advisors.csv | 4 | PASSED |
| advisor_student_assignments.csv | 100 | PASSED |
| courses.csv | 30 | PASSED |
| enrollments.csv | 800 | PASSED |
| program_requirements.csv | 3 | PASSED |

Users contain 100 student accounts, four advisor accounts and one administrator.
student_scenarios.csv adds 100 metadata rows, not a database table.

## Executed technical checks

| Check group | Result |
| --- | --- |
| Record counts | PASSED |
| Primary keys | PASSED |
| Foreign keys | PASSED |
| Unique emails and fields | PASSED |
| Enrollment statuses | PASSED |
| Grade-point combinations | PASSED |
| Course credits | PASSED |
| Enrollment chronology | PASSED |
| Repeated courses | PASSED |
| Advisor assignments | PASSED |
| Program requirement totals | PASSED |
| Eligible course references | PASSED |
| Seed preservation | PASSED |
| SQLAlchemy compatibility | PASSED |
| Scenario coverage | PASSED |
| Fixed-file integrity | PASSED |

The existing validator ran against this checkout's actual models and seed script and
the pinned canonical references. Its old-workspace hash portability correction was made
in the previous transfer; validation logic and academic rules were not changed in this
review. All 31 mutation/regression tests ran again successfully, including bad keys,
FKs, grades, chronology, repeats, assignments, seeds, canonical names and source integrity.
Evidence: PREPARATION_REVIEW.json, validation-results.json, validator-test-results.txt.

Enrollment statuses are 606 completed, 179 in_progress, 10 failed and five withdrawn.
Requirements use eligible_course_ids; course_ids is absent. All headers follow model
order. The validator checks scalar types, nullability, enum values, primary/unique keys,
FKs and array references. No calculated GPA/credit columns exist in students.csv.

## Verified scenarios

| Primary scenario | Students | Result |
| --- | ---: | --- |
| average_performing | 25 | PASSED |
| high_performing | 20 | PASSED |
| low_performing | 15 | PASSED |
| declining | 10 | PASSED |
| improving | 10 | PASSED |
| failed_and_repeated | 10 | PASSED |
| withdrawals | 5 | PASSED |
| new_without_completed | 5 | PASSED |

Five students have no GPA; 15 have 27 completed credits under the documented filter.
Ten student/course pairs have repeat attempts in distinct terms; five students have
multiple passing attempts after a failure. Returning histories span multiple terms,
and declining/improving students have at least three directional graded terms. These
are synthetic test labels, not institutional risk classifications or graduation approval.

## Seed preservation and timestamp semantics

All 13 original seed rows retain their IDs and literal values: users 1/2, program 1,
student 101, advisor 201, courses 11/12/13, attempts 301/302/303, assignment 101 -> 201,
and requirement 401. Attempt 303 is in_progress; Core 401 uses eligible_course_ids
[11,12,13]. Seed literals were inspected with AST; seed_data.py was not executed.
The fixed CSV assignment timestamp remains 2026-10-13T17:46:30.595292-04:00.

Datta's datetime.now(timezone.utc) generates a different timestamp on another execution.
That timestamp-only difference is expected operational metadata, not academic corruption.
No database was compared and the fixed CSV remains immutable. Proposed import behavior,
pending Datta's review: skip a matching assignment with only a timestamp difference,
retain its database timestamp, and record the exception; reject a changed advisor
relationship. This proposal is documented only, not implemented.

## Academic assumptions requiring approval

The provisional 4.0 scale, three-credit catalog, workload/scenario bands and requirement
allocation Core 9/Electives 18/Capstone 3 are unchanged synthetic conventions, not official
Pace University policy. Confirm failed-attempt GPA inclusion, repeated-grade selection/
replacement, repeated-course earned-credit deduplication, completed-null-grade handling
and the allocations. Technical checks passing do not approve these rules.

## Integration preparation, not execution

INTEGRATION_GUIDE.md documents programs -> users -> students -> advisors -> courses ->
enrollments -> assignments -> requirements; FK dependencies; typed comparisons; identical
seed skips; conflict rejection; one transaction with full rollback and race protection;
and post-import subset/count/reference/API checks. Unrelated shared rows must be preserved.
Only model CSVs are imported in a future authorized task; metadata/reference/test files
are not tables. Sequence alignment needs separate review. No importer/reset is supplied.

No Neon/PostgreSQL connection, target database inspection, .env/DATABASE_URL change,
table creation, migration, record deletion/import, commit, push, merge or PR occurred.
Python network-connect audit guards were active during validation, and project database.py
was never imported. All tracked backend file hashes remained unchanged.

## Git/file review

Only intended data/synthetic files are candidates for Git review. No .env, credentials,
venvs or caches are included. Known password_hash values are nonfunctional demo placeholders,
not credentials. Every untracked candidate was read and inspected. Generated dataset cache
directories were removed; Python -B prevented new ones. Exact schema copies are provenance
only and their seed script must not be run.

core.autocrlf=true could change fixed CSV/reference bytes on a later checkout. A scoped
data/synthetic/.gitattributes now sets -text for *.csv and schema_reference/*.py; Git
filtered/raw hashes match for every protected file. No Git configuration changed.

git status: feature/synthetic-academic-dataset with untracked data/ only. git diff --stat,
git diff --check and cached-diff checks are clean; untracked additions remain unstaged.
The original reviewed reference models.py contains a pre-existing trailing-space line;
it is retained exactly for its source checksum, not silently reformatted. New/updated
documentation is whitespace-clean. No approval to commit, push or create a PR is implied.

## Reproduce

From the cloned project root:

```powershell
& 'C:\Users\nhesv\Projects\AcadMate\backend\venv\Scripts\python.exe' -B data/synthetic/validate_dataset.py
& 'C:\Users\nhesv\Projects\AcadMate\backend\venv\Scripts\python.exe' -B data/synthetic/test_validate_dataset.py -v
```

The reused interpreter has SQLAlchemy installed. The clone's dependency setup remains
separate; requirements/backend code were not edited. Dataset/schema readiness is PASSED
for review; shared import and academic-rule approval are still pending.
