# Acadmate — static pages for backend development

These are the 26 Acadmate screens exported from the design canvas as plain HTML and CSS: no framework and no JavaScript. Each page shows its **starting state** filled with sample data, so the backend team can see exactly what every screen needs.

## Run it

Open `index.html` in a browser (it redirects to `Login.html`), or serve the folder:

```bash
cd acadmate-static
python3 -m http.server 8000
# then open http://localhost:8000
```

## Folder layout

```
acadmate-static/
├── index.html            → redirects to Login.html
├── Login.html            → sign-in, two-step code, reset, sign-up (first screen only)
├── Main.html … Settings.html            → student side (9 pages)
├── Advisor*.html                        → advisor side (8 pages)
├── Admin*.html                          → admin side (8 pages)
├── css/acadmate.css      → the one shared stylesheet
└── data/<Page>.json      → sample data for each page (the payload shape it needs)
```

## How to read the markup

| Marker | Meaning | What the backend does |
|---|---|---|
| `data-repeat="stats"` | This element is one item of a list called `stats` | Render it once per record |
| `data-bind="stats[].value"` | This text comes from field `value` of each `stats` item | Fill it from that field |
| `data-bind="sel.name"` | Text from a single object (here, the selected item) | Fill it from that object |
| `style="…"` left inline | A style that depends on data (progress-bar width, active tab, status color) | Set it from the data, or swap for a class |
| `class="…"` | Fixed styling from `css/acadmate.css` | Leave as is |
| `data/<Page>.json` | The sample values used on that page, with presentation-only values removed | Use as the response shape for that page's API |

Colors and fonts are CSS variables in `:root` at the top of `css/acadmate.css` (`--accent`, `--ink`, `--muted`, and so on). Change them there to retheme every page. Class names other than the obvious ones (`card`, `btn-primary`, `btn-secondary`, `sidebar`, `main`, `page-title`) are generated, so treat them as fixed hooks rather than meaningful names.

## Pages and suggested API endpoints

Endpoints are suggestions for a REST API; rename to fit your stack. `{me}` means the signed-in user.

### Sign in
| Page | Shows | Suggested endpoints |
|---|---|---|
| Login | Google sign-in, email and password, staff 6-digit code, password reset, student sign-up | `GET /auth/google` (OpenID Connect redirect) · `POST /auth/login` · `POST /auth/2fa/verify` · `POST /auth/password-reset` · `POST /auth/signup` |

### Student side
| Page | Shows | Suggested endpoints |
|---|---|---|
| Main (dashboard) | GPA history, on-time rate, credits, attendance, graduation date, AI recommendation, requirements, study hours, today's events, deadlines, current courses | `GET /students/{me}/dashboard` |
| MyCourses | Current, completed and planned courses; grade breakdown; timetable | `GET /students/{me}/courses?status=current\|completed\|planned` · `GET /courses/{id}/grades` |
| DegreePlan | Requirement groups and semester roadmap | `GET /students/{me}/degree-audit` · `GET /students/{me}/plan` |
| AIAdvisor | Chat, plan cards, sources, context panel | `GET /ai/conversations` · `POST /ai/conversations/{id}/messages` · `POST /students/{me}/plan` (add to plan) |
| Schedule | Week calendar, deadlines, study-block suggestion | `GET /students/{me}/events?from=&to=` · `POST /students/{me}/events` · `GET /students/{me}/calendar.ics` |
| Assignments | Assignment list, filters, AI step plan | `GET /students/{me}/assignments?status=&course=` · `GET /assignments/{id}` |
| Messages | Conversations and replies | `GET /conversations` · `GET /conversations/{id}/messages` · `POST /conversations/{id}/messages` |
| BookMeeting | Who to meet, topic, free slots, confirmation, upcoming meetings | `GET /staff?bookable=true` · `GET /staff/{id}/availability?week=` · `POST /meetings` · `GET /students/{me}/meetings` |
| Settings | Profile, notifications, AI permissions, Google connection, privacy | `GET/PATCH /users/{me}` · `PATCH /users/{me}/preferences` · `POST /users/{me}/google/connect` · `DELETE /users/{me}/google` · `POST /users/{me}/export` · `DELETE /ai/conversations` · `DELETE /users/{me}` |

### Advisor side
| Page | Shows | Suggested endpoints |
|---|---|---|
| AdvisorDashboard | Summary, approval queue, today's meetings, students needing attention, caseload | `GET /advisors/{me}/dashboard` |
| AdvisorAdvisees | Roster with filters and preview | `GET /advisors/{me}/advisees?status=&q=` |
| AdvisorStudent | One student's full record, notes, activity | `GET /students/{id}/record` · `POST /students/{id}/notes` |
| AdvisorApprovals | Requests with AI pre-check; approve or request changes | `GET /approvals?status=` · `POST /approvals/{id}/approve` · `POST /approvals/{id}/request-changes` (comment required) · `POST /approvals/{id}/reopen` |
| AdvisorMeetings | Agenda, booking requests, office hours, notes | `GET /advisors/{me}/meetings?range=` · `POST /bookings/{id}/accept` · `POST /bookings/{id}/propose` · `PUT /advisors/{me}/office-hours` · `PUT /meetings/{id}/notes` |
| AdvisorMessages | Conversations, quick replies | same as student Messages |
| AdvisorReports | Term stats, status breakdown, meetings per week, at-risk list | `GET /advisors/{me}/reports?term=` · `GET /advisors/{me}/reports.csv?term=` |
| AdvisorSettings | Profile, notifications, pre-checks, booking rules | `GET/PATCH /advisors/{me}/settings` |

### Admin side
| Page | Shows | Suggested endpoints |
|---|---|---|
| AdminDashboard | Active students, AI quality, flagged answers, system status, advisor workload | `GET /admin/overview` · `GET /admin/overview/report` |
| AdminUsers | User list, role and advisor changes, deactivate, password reset, invites, CSV import | `GET /admin/users?role=&q=` · `PATCH /admin/users/{id}` · `POST /admin/users/{id}/password-reset` · `POST /admin/invites` · `POST /admin/imports/users` (CSV upload) |
| AdminAdvisors | Caseloads, reassignment, add advisor | `GET /admin/advisors` · `POST /admin/advisors` · `POST /admin/advisors/{id}/reassign` |
| AdminCatalog | Courses, degree requirements, term dates, publish | `GET/PATCH /admin/courses/{code}` · `GET/PUT /admin/programs/{id}/requirements` · `GET/PUT /admin/terms/{id}/dates` · `POST /admin/catalog/publish` |
| AdminAI | Feature and data-source switches, guardrail topics, test console, flagged answers | `GET/PATCH /admin/ai/settings` · `POST /admin/ai/test` · `GET /admin/ai/flags` · `POST /admin/ai/flags/{id}/resolve` |
| AdminIntegrations | CSV import, email, calendars, API keys | `GET /admin/integrations` · `POST /admin/integrations/{id}/connect\|disconnect\|sync` · `POST /admin/imports/{type}` · `POST /admin/api-keys` · `DELETE /admin/api-keys/{id}` |
| AdminAudit | Event log with filters and export | `GET /admin/audit?role=&since=&q=` · `GET /admin/audit.csv` |
| AdminSettings | Institution, term, time zone, security, retention, branding, demo reset | `GET/PATCH /admin/settings` · `POST /admin/demo/reset` |

## Not included (needs front-end work later)

- **Interactivity.** Tabs, filters, toggles, chat sending and form steps were live in the prototype but are frozen at their first state here. Each other state (for example the Login page's code, reset and sign-up screens) still needs building in your front-end framework.
- **Placeholder links** still pointing to `#`: Schedule (Add event, Edit, Set reminder), Book a meeting (Reschedule ×2), My courses (Open course site, office hours link, one more), Assignments (Open submission page), Messages (New message), AI advisor (4 conversation history links).
- **Google sign-in button.** Replace the placeholder icon with Google's official "Sign in with Google" button from Google Identity Services, as Google's branding rules require.

## Data and privacy

All names, grades and dates are sample data. Bracketed text such as `[Advisor]` and `[school].edu` marks placeholders. Keep using sample data until the project has approval to handle real student records, which are protected under FERPA.
