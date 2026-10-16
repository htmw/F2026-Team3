# Fixed dataset data dictionary

Authoritative source: this checkout's backend/models.py, compared with the reviewed feature/backend-integration copy in schema_reference/models.py. The validator parses this checkout's seed_data.py without executing it. Every table CSV has exactly the model columns in model order.
CSV empty cells mean SQL NULL; literal NULL/None are not used. true/false are lowercase booleans.
JSON arrays are quoted as needed by CSV, e.g. cell [11,12,13]. Parse with json.loads, never eval.
Numeric cells use decimal text; use Decimal when importing. Timestamps are fixed timezone-aware ISO 8601 values.
No GPA or calculated-credit columns exist in students.csv.

## users.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| user_id | INTEGER | Yes | PK | `1` |
| name | VARCHAR(100) | Yes | UNIQUE | `Santos Shel` |
| email | VARCHAR(100) | Yes | UNIQUE | `santos.shel@pac.edu` |
| password_hash | VARCHAR(255) | Yes | Nonfunctional demo placeholder; not a valid authentication hash | `demo_hash_student` |
| role | PostgreSQL user_role enum | Yes | student, advisor, admin | `student` |
| is_active | BOOLEAN | Yes | Model type/length only | `true` |

## programs.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| program_id | INTEGER | Yes | PK | `1` |
| program_name | VARCHAR(100) | Yes | Model type/length only | `MS Computer Science` |
| total_required_credits | NUMERIC | Yes | Model type/length only | `30` |

## students.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| student_id | INTEGER | Yes | PK | `101` |
| user_id | INTEGER | Yes | UNIQUE; FK users.user_id | `1` |
| name | VARCHAR(100) | Yes | Model type/length only | `Santos Shel` |
| email | VARCHAR(200) | Yes | UNIQUE | `santos.shel@pac.edu` |
| program_id | INTEGER | Yes | FK programs.program_id | `1` |

## advisors.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| advisor_id | INTEGER | Yes | PK | `201` |
| user_id | INTEGER | Yes | UNIQUE; FK users.user_id | `2` |

## advisor_student_assignments.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| student_id | INTEGER | Yes | PK; FK students.student_id | `101` |
| advisor_id | INTEGER | Yes | FK advisors.advisor_id | `201` |
| updated_at | TIMESTAMP WITH TIME ZONE | Yes | Model type/length only | `2026-10-13T17:46:30.595292-04:00` |

## courses.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| course_id | INTEGER | Yes | PK | `11` |
| course_code | VARCHAR(100) | Yes | UNIQUE | `CS501` |
| course_name | VARCHAR(200) | Yes | Model type/length only | `Programming Foundations with Java` |
| credits | NUMERIC | Yes | Dataset convention: 3; model defines no positive-credit check | `3` |

## enrollments.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| enrollment_id | INTEGER | Yes | PK | `301` |
| student_id | INTEGER | Yes | FK students.student_id | `101` |
| course_id | INTEGER | Yes | FK courses.course_id | `11` |
| term | VARCHAR(50) | Yes | Model type/length only | `Fall 2026` |
| status | PostgreSQL enrollment_status enum | Yes | in_progress, completed, failed, withdrawn | `completed` |
| grade | VARCHAR(5) | No | Provisional grade mapping in README; NULL for withdrawn/in_progress | `A` |
| grade_points | NUMERIC | No | Provisional grade mapping in README; NULL for withdrawn/in_progress | `4` |

## program_requirements.csv

| Column | SQLAlchemy / PostgreSQL type | Required | Keys / allowed values | Example |
| --- | --- | --- | --- | --- |
| requirement_id | INTEGER | Yes | PK | `401` |
| program_id | INTEGER | Yes | FK programs.program_id | `1` |
| group_name | VARCHAR(100) | Yes | Model type/length only | `Core` |
| required_credits | NUMERIC | Yes | Model type/length only | `9` |
| eligible_course_ids | INTEGER[] (PostgreSQL ARRAY) | Yes | Model type/length only | `[11,12,13]` |

## student_scenarios.csv (metadata only)

| Column | Type | Required | Allowed values / role | Example |
| --- | --- | --- | --- | --- |
| student_id | INTEGER | Yes | Metadata reference to students.student_id; exactly one label per student | 101 |
| scenario | String | Yes | high_performing, average_performing, low_performing, declining, improving, failed_and_repeated, withdrawals, new_without_completed | average_performing |

This sidecar is not an SQLAlchemy table and must not be imported into the database.

## Canonical schema and local deployment

- Verified branch: feature/backend-integration. Status values: in_progress, completed, failed, withdrawn.
- Requirement array: eligible_course_ids, required PostgreSQL INTEGER[]. course_ids is removed.
- The cloned backend uses these canonical names. PostgreSQL was not inspected or changed during transfer.
- Exact reference sources and blob identities are recorded in DATASET_MANIFEST.json.
- No external Data Dictionary/API Contract was available; this comparison uses actual reviewed source.
- Array course references are checked explicitly; PostgreSQL arrays are not scalar foreign keys.
- Scenario thresholds, 3-credit values, the 12-credit workload convention, grading/status combinations
  and snapshot chronology remain provisional synthetic conventions, not official university policy.


## Assignment timestamp interpretation

The CSV updated_at value is fixed provenance and must remain byte-identical to the
source dataset. Datta's seed uses datetime.now(timezone.utc), so independent database
executions can legitimately differ in this operational timestamp without academic-data
corruption. Seed comparisons verify all literal academic/identity fields; this task
does not execute the seed or compare against a database. See INTEGRATION_GUIDE.md for
the proposed, not implemented, timestamp-only skip exception retaining existing DB time.

## Review and policy boundaries

The local clone is a genuine Git repository on feature/synthetic-academic-dataset based
on feature/backend-integration. All eight model CSVs are technically compatible with
the inspected models. Grading, failed/repeated-attempt GPA/credit treatment, null-grade
completion treatment and the 9/18/3 allocation still require team approval. No database
or Neon connection, import, .env change or schema modification was part of this review.
