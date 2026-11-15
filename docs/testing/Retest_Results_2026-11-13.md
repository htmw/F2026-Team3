# AcadMate Retest Results

Tester: Pragnan Chintu
Testing dates: November 12-13, 2026
Branch: test/acadmate-local-testing
Fix commit: f4ef781

## Environment

- Local PostgreSQL database: acadmate_test
- Backend: http://127.0.0.1:8010/api/v1
- Frontend: http://localhost:5173
- Application date pinned to 2026-10-01
- Local SMTP capture: Mailpit

## Code fixes verified on November 12

| Case | Verified result | Status |
|---|---|---|
| FE-04 Capacity validation | -1 and 2.5 display an error; valid value 2 clears it | Pass |
| FE-12 Required event title | Blank title displays a required-title message; valid event saves and persists after refresh | Pass |
| FE-11 Requested course timing | CS 691 move requests use Fall 2027 and Spring 2028, with conditional graduation estimates and unconfirmed-offering explanations | Pass |

Regression checks: 353 backend tests passed in 75.30 seconds.
Frontend production build passed, with a bundle-size warning.
These runs occurred before the November 13 follow-up tests.

## Follow-up checks verified on November 13

| Check | Observed result | Status |
|---|---|---|
| RT-02 Mark complete | Meeting 1508 returned HTTP 200 after preparing a confirmed past meeting | Pass |
| RT-03 Mark no-show | Meeting 1509 returned HTTP 200 after preparing a confirmed past meeting | Pass |
| AI sharing disabled | HTTP 403 NOT_SHARED | Pass |
| AI sharing enabled | HTTP 200 with a threads list | Pass |
| AI sharing revoked | HTTP 403 NOT_SHARED again | Pass |
| Public calendar feed | Valid returned feed URL gave HTTP 200, calendar events, BEGIN:VCALENDAR and END:VCALENDAR | Pass |
| Student Google disabled | HTTP 400 GOOGLE_DISABLED | Pass for disabled configuration |
| Admin Google disabled | HTTP 400 GOOGLE_DISABLED | Pass for disabled configuration |
| Proposal and acceptance | Advisor proposed October 6 at 13:00 UTC for meeting 1501; student accepted with HTTP 200; confirmed time persisted in database and fresh meeting list | Pass |
| Local SMTP | HTTP 200 Connected; Acadmate test email received in Mailpit for jordan.lee@pac.edu | Pass for local delivery |
| Invalid event edit | Start 15:00 / end 14:00 displayed the expected error; dialog remained open; original 13:00-14:00 persisted after Cancel and refresh | Pass |
| CSV comparison | Credits, GPA, status and next meeting matched the displayed fields for all 8 advisees; aggregate status counts matched Reports | Pass for compared fields |
| User pagination | 72 users; Next moved from 1-50 to 51-72; last-page Next stayed on that page; Previous returned to 1-50 | Pass |
| Demo reset | HTTP 202 with reset message; meetings 1501, 1508 and 1509 restored to checked seed dates and confirmed status; calling admin session remained valid | Pass for checked effects |

## Limits and test-data notes

- Successful Google OAuth was not tested because Google sign-in is disabled.
- External SMTP delivery, authentication and TLS were not tested.
- CSV fields not visible in the screenshots were not individually compared.
- The demo reset was checked using selected seeded records and admin-session continuity, not every table.
- Postman follow-up results were manually inspected; they are not a new full collection-run assertion total.
- Earlier 404/409 responses involved unset feed tokens, unsuitable meeting IDs or meeting states.
- Demo reset replaced the local test data after the other checks.
- A pre-reset database backup was saved in Downloads as acadmate_test_before_demo_reset.dump.
