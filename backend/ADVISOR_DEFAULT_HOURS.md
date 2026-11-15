# Advisor availability defaults for the reviewed Sprint 2 candidate

User decision, November 14, 2026: advisors start with Monday?Friday 08:00?17:00 office hours in the configured school timezone, unless adjusted. The guarded local team host enables ACADMATE_ADVISOR_DEFAULT_HOURS=true. Other hosts remain opt-in; normal team adoption still requires review.

## Behavior

- Default windows are transient read-only values, not seeded appointments or new database rows. No academic CSV or database schema changes.
- Advisors with saved office hours use those hours. With no separate saved appointment schedule, booking follows their effective office hours. Existing appointment windows retain their times.
- Default drop-in windows do not block an existing appointment schedule. Existing custom drop-in windows and an explicitly stored bookDuringOfficeHours preference retain their booking behavior.
- Authorized office-hour updates continue through the existing service. Explicit custom/empty schedules are remembered in the existing preferences JSON, including after audit retention; defaults never repopulate an intentional clear. Earlier audit events also identify pre-existing clears.
- Active/bookable/assignment permissions, school timezone, 30-minute default meeting length (or staff override), booking horizon, 12-hour lead time, classes, existing meetings and simultaneous-booking protections remain in the existing scheduling service.
- Weekends have no default slots. No location, meeting or video connection is invented. A past/too-soon day can legitimately have no slots even with default hours.

Implementation: risk_mvp/advisor_defaults.py, guarded tools/apply_advisor_defaults.py, team_host opt-in and prepare_team_review integration. The overlay touches only the ignored review export. Advisor settings are changed only on an actual schedule save; rendering defaults writes nothing. Existing backend models remain unchanged.

## Verification

Seven new scheduling tests cover read-only defaults, custom/cleared schedules, audit-retention independence, existing booking windows, explicit preferences, feature-off/nonadvisor behavior, actual slot bounds/lead time and staff discovery permissions. Existing booking tests retain class and meeting conflict assertions. An initial enabled full run found default drop-in hours blocking an existing appointment slot; corrected implementation passes the unchanged failing scheduling test.

Focused scheduling suite after correction: 28 passed. Live local verification: four advisors show weekday 08:00?17:00; all 100 assigned students have next-day slots on February 17, 2027 within those bounds; Saturday slots empty; zero bookings created. Evidence: ml/outputs/advisor-default-hours-live-v2.json. Full enabled suite: 433 passed, zero failures/errors/skips in 134.54 seconds with actual artifact smoke (ml/outputs/advisor-defaults-enabled-backend-v2.xml).

Reproduce without creating a meeting:

```powershell
.\ml\outputs\handoff-venv-v1\Scripts\python.exe tools/verify_advisor_default_hours.py --output ml/outputs/advisor-default-hours-live-new.json
```

Choose a new output path. The verifier uses fixed loopback demo routes and public synthetic accounts, and performs login/logout plus read-only schedule requests. It never publishes hours, books, sends messages or changes academic records.

## Demo preparation

Refresh the Meetings page. To show booking availability, choose February 17, 2027 rather than assuming the pinned current day has slots after the lead time. Do not change the clock or bypass conflicts to force a booking. A real booking/approval demonstration should use an agreed designated synthetic scenario and explicit user action. External calendar/video/email delivery is not implied by local meeting persistence.

Final cross-role availability verification passed: all four advisors and all 100 student booking views agree on next-day open-slot counts, each student can discover their assigned advisor, weekday time bounds hold and weekends have no default slots. Evidence: ml/outputs/advisor-default-hours-live-v3.json. No bookings were created. Overlay reapplication is byte-identical.
