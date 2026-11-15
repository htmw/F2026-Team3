# Dataset usage audit ? 2026-11-12

Read-only audit of the local main integration demo, pinned to main commit 8c4b0843368b679ac3f3353f6332c73356888b14. No data was imported, regenerated, reassigned or deleted.

## Finding

The running main integration demo does not use data/synthetic as its academic population. It uses the frontend/main seed: 13 students, 4 advisors, 13 courses, 46 enrollments and 11 advisor assignments. The preserved fixed CSV deliverable contains 100 students, 4 advisors, 30 courses, 800 enrollments and 100 assignments. These are separate populations, not two views of the same dataset.

## Advisor counts in the running demo

| Advisor | Assigned | Capacity | Capacity status | Account |
|---|---:|---:|---|---|
| Sarah Smith (201) | 8 | 45 | Has room | Active |
| Daniel Kim (203) | 3 | 2 | Over capacity | Active |
| Maya Brooks (204) | 0 | 25 | Has room | Active |
| Priya Natarajan (202) | 0 | 40 | Has room | Inactive/invited |

Eleven is the total number of assigned students, not an individual advisor's load. Kofi Mensah (102) and Lena Fischer (103) have no advisor assignment. Hana Sato (105) and Marcus Reed (106) have no enrollments, so academic progress and course risk are explicitly unassessed. Capacity labels compare assignments with configured limits, not the total number of students in a dataset. Daniel's deliberately small capacity is present in the main seed as an admin demonstration case.

## Advisor counts in the fixed CSV dataset

Sarah Smith (201), Rowan Flint (10200), Sage Linden (10201), and Quinn Meadow (10202) each have exactly 25 assigned students. Advisors beyond Sarah are different accounts from those in the main demo. Do not blindly append these CSVs to the main database: shared numeric identifiers do not guarantee the same person. For example, main student 101 is Amara, whereas the original academic fixture uses its existing seed identity.

## What each source supplies

- Main seed/database: current student/admin/advisor academic pages, authentication, assignments, capacity settings, enrollment history and planning records.
- Main risk sidecars: synthetic activity/submission/schedule records linked to all 46 existing main enrollments. There are 46 links, 21 offerings, 202 assessments, 202 assessment versions, 2,830 activity events, 382 submission versions, 14,601 coverage records and 79 enrollment-history records.
- Fixed data/synthetic CSVs: preserved and validated 100-student deliverable; not automatically imported into the running main demo.
- ml/fixtures/simulated_lms: earlier four-enrollment demonstration fixtures; separate from the database-backed main advisor endpoint.
- OULAD and frozen artifacts: historical model training/evaluation and fixed inference/preprocessing/calibration. OULAD is not the live student population and does not supply institutional student records.

## Verification and remaining gaps

The live academic fingerprint matches the generated sidecar manifest. Every one of the 46 existing enrollments has exactly the expected risk linkage, with no extra linked IDs. All risk table counts match the recorded manifest. Recent all-advisor audits validated 4 advisors, 11 assigned records, matching attention counts/reasons, missing-record categories and 41 denied assignment checks. Fixed CSV integrity, relationship and count checks also passed with all original counts preserved.

The smaller seed's displayed counts are correct. This does not establish that the full 100-student deliverable is integrated. Student Assignments/Courses pages still use main Assignment/AssignmentSubmission data, while prediction explanations use the synthetic risk tables. Those sources have not been given a shared assessment-ID crosswalk; their deadline/submission totals must not be presented as interchangeable. The earlier conflicting advisor overdue check was aligned to the risk source, but that did not unify all student coursework screens.

Recommended next step: agree on one canonical Sprint 2 demo population, then prepare a reviewed mapping of student/user/advisor/course/enrollment identities, account/login requirements, program requirements, terms and course sections before any isolated database import. Reconcile assessment identities and submission semantics across student and advisor pages, retain missing-data states, then rerun cross-role counts, links, permissions and real-inference checks. Preserve the current working demo as a checkpoint. No database integration is performed by this audit.


## Subsequent integration completed

The full CSV population is now served separately at 127.0.0.1:5178 with API 8004 and database acadmate_risk_csv_sprint2. The findings above continue to describe the preserved 5177/8003 small demo. See CSV_POPULATION_DEMO.md for exact population, identity mappings, shared assessment projections, snapshot assumptions, setup and validation evidence. Do not confuse the two local URLs.
