# Shared PostgreSQL integration plan (documentation only)

No shared-database connection, Neon configuration, migration or CSV import is part of
this task. Datta owns the shared schema and connection setup. This plan requires review
before implementation; no importer or destructive reset is supplied.

## Preconditions

1. Review all technical validation results and approve the academic conventions separately.
2. Datta verifies the target database/branch and schema: enum in_progress/completed/failed/
   withdrawn; requirement column eligible_course_ids; removed course_ids; compatible
   keys, lengths, types and nullability. Do not use create_all as a schema migration.
3. Re-run the fixed CSV validator and verify manifest SHA-256 values before importing.
4. Agree who performs the import and how the isolated target is selected. Never put
   a Neon URL or password in CSVs, source code, console output or the validation report.
5. Determine which records already exist. Source-workspace conflict checks were historical
   snapshots and cannot establish that a shared target is conflict-free now.

## Order and foreign-key dependencies

| Step | CSV | Must already exist |
| --- | --- | --- |
| 1 | programs.csv | None |
| 2 | users.csv | None |
| 3 | students.csv | users.user_id, programs.program_id |
| 4 | advisors.csv | users.user_id |
| 5 | courses.csv | None |
| 6 | enrollments.csv | students.student_id, courses.course_id |
| 7 | advisor_student_assignments.csv | students.student_id, advisors.advisor_id |
| 8 | program_requirements.csv | programs.program_id; validate every eligible_course_ids element against courses |

Do not import student_scenarios.csv, manifests, references, reports or tests as tables.
Parse empty CSV cells as SQL NULL, booleans as true/false, numerics with Decimal,
timestamps as timezone-aware datetimes, and arrays with json.loads (never eval).

## Idempotency and existing seeds

The fixed counts include Datta's demo seeds; they are not additional records beyond
the demo. Preserve users 1/2, program 1, student 101, advisor 201, courses 11/12/13,
attempts 301/302/303, assignment 101 -> 201 and requirement 401.

For every row, compare typed values before deciding whether to insert:

- Existing primary key and identical fields: skip, recording an identical-row count.
- New primary key with no conflicting unique values: insert in dependency order.
- Existing key with a different academic/identity value, or a different primary key
  colliding on a unique email/name/user reference/course code: reject the import and
  roll back. Do not silently update, merge, replace or delete records.
- Compare array order/content and NULL versus empty array deliberately. Normalize decimal
  representations and timezone-equivalent instants so formatting alone is not a conflict.

### Dynamic assignment timestamp

seed_data.py creates updated_at using datetime.now(timezone.utc); independent seed runs
can produce different instants even when the student/advisor relationship is identical.
This is operational metadata and does not by itself indicate academic-data corruption.
The fixed CSV timestamp and checksum must remain unchanged.

Proposed exception for Datta's review: when student_id and advisor_id match and every
other non-timestamp assignment field matches, log a timestamp-only difference and skip
the existing assignment, retaining its database timestamp. Do not update either the CSV
or database timestamp. A different advisor relationship remains a real conflict. This
exception is documented, not implemented; approve it before writing an importer.

## Atomicity and duplicate prevention

Use one database transaction covering preflight, seed comparisons, insertions and
verification, with a reviewed locking/isolation strategy to prevent concurrent import
races. Retain normal FK/unique constraints. Parameterize statements. Do not use an
unconditional ON CONFLICT DO NOTHING: it can hide conflicting data. Do not use blanket
upserts, disable constraints, truncate tables, reset the database or rewrite schemas.

Any constraint error, missing reference, mismatch, unexpected count or verification
failure must roll back the entire transaction. Report which record key/check failed,
without printing secrets. On success report per-table inserted, identical-skipped,
timestamp-only-skipped and conflicting counts. A second run should insert zero rows
when nothing has changed. Test this strategy in an authorized isolated environment first.

Explicit IDs may leave sequences behind the highest stored key. Datta must separately
review sequence alignment before later automatic inserts; this task changes no sequence.
Never overwrite unrelated IDs/records to resolve a collision.

## Verify before committing the import transaction

- Verify all expected CSV primary keys exist with matching typed fields, applying only
  any explicitly approved timestamp exception. Confirm seeded names, relationships,
  statuses, grades and Core eligibility remain intact.
- Verify zero missing scalar FKs, valid eligible arrays and no duplicate primary/unique
  keys. Confirm exactly one intended assignment per CSV student and the expected role map.
- Verify the imported subset contains 105 users, 100 students, four advisors, one program,
  30 courses, 800 attempts, 100 assignments and three requirements. Shared-table totals
  may be higher if unrelated valid records already exist; validate the subset by fixed
  primary-key membership instead of treating unrelated rows as duplicate dataset records.
- Check 606 completed, 179 in-progress, 10 failed and five withdrawn dataset attempts;
  no grades on in-progress/withdrawn rows; distinct-term repeat attempts; all eight
  scenario groups; requirement credits 9+18+3=30. Scenario metadata stays outside SQL.
- Reconcile observed insert/skip counts with the preflight plan and retain a sanitized
  audit receipt. Do not commit a partially verified import.

After an authorized successful import, exercise the actual academic-profile API for a
known student, missing ID, no-GPA student and repeat-course student. Compare returned
records with the imported subset. Validate GPA/credits against the approved policy;
do not substitute provisional rules for institutional decisions. Student 101's profile
will include its five extra historical electives (eight attempts total), while its
original three attempts remain intact. No API/shared-database tests were executed by
this preparation task and no import approval is implied.
