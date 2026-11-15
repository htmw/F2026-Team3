# Sprint 2 visual review — 12 November 2026

## Scope and limits

Reviewed the local application at 127.0.0.1:5177 using native Chrome interaction and seeded synthetic accounts. Main desktop window was approximately 1462 by 1098 pixels. A narrower approximately 919-pixel window was checked on admin Settings, then the browser was maximized. This is a main-screen visual pass, not exhaustive device, accessibility, security or transaction acceptance testing.

Advisor Dashboard, Advisees and full student record were visually reviewed in the immediately preceding review sessions. This continuation inspected advisor Approvals, Meetings, Messages, Reports and Settings; student Dashboard, My courses, Degree plan, AI advisor, Schedule, Assignments, Messages, Book a meeting and Settings; admin Overview, Users, Advisors, Courses & catalog (courses, degree requirements and terms), AI settings, Integrations, Audit log and Settings; and the shared sign-in screen.

No messages, bookings, approval decisions, imports, reassignments, configuration changes or security changes were submitted. Navigation can mark opened conversations read, and sign-in/sign-out creates ordinary session/audit activity. No academic records were edited. Admin Settings remains open in maximized Chrome.

## Highest-priority findings

| Finding | Observed evidence | Recommendation |
|---|---|---|
| Integration health conflicts | Admin Overview calls email notifications Healthy; Integrations shows Email (SMTP) Off / Not connected | Use one effective integration status across both pages; distinguish enabled settings from configured/working service |
| Unsupported outcome wording | Student My courses says two office-hour visits before a midterm could lift a grade toward A-minus | Replace with a factual observation and optional support suggestion; do not imply a validated grade improvement |
| Narrow navigation dominates the screen | At ~919 px, the shared navigation becomes a full-width, roughly 700-pixel-tall block before Settings content | Use a compact responsive menu/header and confirm main tasks remain near the top; reproduce across roles before calling the mobile review complete |
| Configured choice differs from effective capability | AI settings selects Claude while a note says answers are rule-based because Claude is not configured; Google/staff two-step controls look enabled while their notes say unavailable/not configured | Display requested setting and effective state distinctly; unavailable capabilities should not look operational |

## Page observations

### Advisor

- Dashboard / Advisees / record: concern-led journey and counts were verified in earlier sessions; latest automated audit covers all four advisors. Keep administrative flags separate from model probabilities.
- Approvals: list/detail layout readable; warning on Marcus's drop request is prominent. Approve remains enabled despite the pre-check warning, whereas dashboard quick approval was disabled. This can represent deliberate advisor override, but the UI should explain that and make any acknowledgement behavior clear. No decision was tested.
- Meetings: agenda, requests and selected meeting detail readable. Save notes, completion, no-show and cancellation controls were not invoked. Office-hour editor inspected without edits.
- Messages: empty conversation state and student context links visible. Generic quick reply `Approved. Thanks!` can be ambiguous outside a formal approval workflow; consider removing or tailoring it.
- Reports: attention count five and independent graduation bar visible. For historical terms, clarify which statistics are term-specific and which caseload/attention figures remain current. No download triggered.
- Settings: profile and booking controls readable. Save bar remains visible while scrolling; no settings saved.

### Student

- Dashboard: academic context, next-term recommendation, requirements, timetable and deadlines render. GPA `On track`, grade/attendance indicators, and `reviewed by your department` wording need clear evidence/scope; they are separate from the OULAD risk estimate and do not establish overall student safety or human review.
- My courses: current/completed/planned views and selected course grade breakdown render. The outcome claim above is the main wording issue.
- Degree plan: credits, remaining requirements and roadmap are visible; no plan was sent or changed.
- AI advisor: empty/new conversation view, record context and human-advisor links render. Effective answer mode is shown as rule-based. No question was submitted.
- Schedule: events, selected detail, deadline list and calendar subscription controls render. Narrow event blocks truncate titles, with selected details available. No event or feed link was changed.
- Assignments: filters and detailed task checklist render. `Mark as submitted` and actual submission-page actions are distinct; no submission/checklist edits were made. These records are not mapped to the independently generated risk assessment records.
- Messages: conversation text and scheduling link render. Opening the existing conversation reduced unread count normally; no message was sent.
- Book a meeting: staff, topic, format and available-date flow render; confirmation disabled before choosing a slot. No booking created.
- Settings: profile, AI consent/sharing, sign-in and privacy sections inspected. No security, consent, retention or deletion action performed.

### Admin

- Overview: charts and pending-work sections render. Integration status mismatch needs correction; seeded operational metrics/logs must not be presented as proof of live external integration.
- Users: role/status columns and empty detail selection render. No import, invite, activation or role change attempted.
- Advisors: actual caseloads, pending count and capacity display. Reassignment controls were not used; a preview of affected students would improve reviewability before a batch move.
- Catalog: course editing, requirement groups and term-date screens render. `Not offered` means the next planning term on this screen, so including that term in the label would reduce confusion with currently running courses. Different catalog-year labels across admin/student views may reflect different cohorts and are not by themselves a defect.
- AI settings: feature switches, data sources, blocked topics and test box render; effective-mode mismatch noted above. No test question or change submitted.
- Integrations: CSV available, SMTP/calendar connections off, masked API key display. No upload, connection, key generation or revoke action performed.
- Audit: list/detail read clearly and show ordinary review login events; no export triggered.
- Settings: institution, timezone, retention and branding render. Unavailable sign-in capabilities should have unambiguous effective-state labels.

## Recommended Sprint 2 order

1. Fix operational status consistency and unsupported outcome claims.
2. Improve the shared responsive navigation for smaller laptop/projector windows.
3. Clarify effective AI mode and unavailable integration/authentication controls.
4. Clarify scope of administrative overrides, historical reports and separate synthetic data sources.
5. Rehearse the agreed advisor journey on the presentation machine.

No new feature expansion is required by these findings. Approval, scheduling, messaging, import/export, security and destructive workflows still need separate acceptance tests if included in the presentation; a readable screen is not proof of successful submission or external delivery.
