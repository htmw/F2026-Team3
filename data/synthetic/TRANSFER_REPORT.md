# Fixed dataset transfer report — October 14, 2026

Source: C:/Users/nhesv/Projects/AcadMate/data/synthetic
Destination: C:/Users/nhesv/Documents/AcadMate-Team/data/synthetic
Branch: feature/synthetic-academic-dataset. HEAD: 5f19acc5e2dd4c26cd44d76036f3d0329bf92ece.
origin/feature/backend-integration is an ancestor. Working tree was clean before transfer.

## Verification

All eight table CSVs plus student_scenarios.csv are byte-identical to the existing fixed
dataset. SHA-256 equality was verified for every CSV. The original manifest and reviewed
schema-reference files are also byte-identical. No records were regenerated or edited.

| File | Records |
| --- | ---: |
| advisor_student_assignments.csv | 100 |
| advisors.csv | 4 |
| courses.csv | 30 |
| enrollments.csv | 800 |
| program_requirements.csv | 3 |
| programs.csv | 1 |
| students.csv | 100 |
| users.csv | 105 |

The scenario sidecar has 100 rows, one per student. Status vocabulary is in_progress,
completed, failed and withdrawn (179/606/10/5 rows respectively). Requirements have only
requirement_id, program_id, group_name, required_credits and eligible_course_ids.
course_ids is absent. Original seed IDs, values and relationships match this clone's
updated seed_data.py. The assignment timestamp remains the exact captured original value;
the dynamic datetime.now() seed expression was never executed.

## Validation performed

- All 16 dataset validation groups passed against the actual cloned backend models.
- All 31 validator tests passed; no failures, errors or skips. Existing mutation tests
  plus two new checks verify actual checkout model and seed changes are rejected.
- No backend code or tracked repository files changed. No PostgreSQL module was imported,
  no database accessed, no migration/import executed and no records regenerated.
- No branch switch, commit, push or merge occurred. New files are untracked under data/.

The first run of the unmodified copied validator failed its four historical backend-hash
gates: they referenced the older ZIP workspace, not this checkout. Only the copied
validator/tests were adapted: validate actual checkout models, compare their AST to the
reviewed canonical schema, parse actual checkout seed literals, and retain every fixed
CSV checksum, pinned-source checksum, FK, grade, scenario and preservation check.
Creation hashes stay untouched in the manifest as provenance; they are not assertions
that this new checkout must contain the old ZIP backend. Neither backend nor CSVs were
changed to make validation pass. The original workspace remains unchanged.

Used interpreter: C:/Users/nhesv/Projects/AcadMate/backend/venv/Scripts/python.exe.
The new clone has no virtual environment. Its requirements.txt does not declare
SQLAlchemy or a PostgreSQL driver; no dependency/backend files were changed. Resolve
environment dependencies separately before independent backend setup. For now, run
from the new project root using the existing interpreter:

```powershell
& 'C:\Users\nhesv\Projects\AcadMate\backend\venv\Scripts\python.exe' data/synthetic/validate_dataset.py
& 'C:\Users\nhesv\Projects\AcadMate\backend\venv\Scripts\python.exe' data/synthetic/test_validate_dataset.py -v
```

## Files transferred

- COMPATIBILITY_REVIEW.json
- DATASET_MANIFEST.json
- DATA_DICTIONARY.md
- README.md
- VALIDATION_REPORT.md
- advisor_student_assignments.csv
- advisors.csv
- compatibility-test-results.txt
- courses.csv
- enrollments.csv
- program_requirements.csv
- programs.csv
- schema_reference/README.md
- schema_reference/models.py
- schema_reference/seed_data.py
- student_scenarios.csv
- students.csv
- test_validate_dataset.py
- users.csv
- validate_dataset.py
- validation-results.json
- validator-test-results.txt

Added transfer evidence: TRANSFER_REPORT.md and TRANSFER_VERIFICATION.json. The copied
validator/tests and destination documentation/results were updated for this checkout;
CSV, manifest and pinned-reference contents remain identical. Generated Python caches
were excluded from transfer.

## Remaining integration considerations

The dataset is schema-compatible with the cloned backend, but no claim is made about
the schema/migration state of a target PostgreSQL database. Before a separately authorized
import, check the real target, compare existing seeds (including timestamp differences),
skip identical records and reject conflicts within one transaction. Review explicit-ID
sequences separately. Academic grading/retake conventions remain provisional. Review Git
line-ending conversion before a future commit/checkout so fixed CSV hashes stay valid.
Do not commit/push/import merely because this transfer passed validation.
