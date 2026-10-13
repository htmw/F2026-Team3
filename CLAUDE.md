# Acadmate — CLAUDE.md

Academic advising platform for students, faculty advisors, and administrators.
Team project (F2026-Team3).

## Stack

- `frontend/` — React + Vite + Tailwind CSS (JSX)
- `backend/` — Node.js 20+ / Express 5, PostgreSQL 16 (via Docker), plain SQL with
  versioned migrations, Zod validation, cookie sessions, TOTP two-step sign-in for staff
- `Doumentation/` — sprint docs, presentations, design prototypes, Jira exports (note the
  folder name is misspelled in the repo — keep it as-is, don't rename)

## Quick start

```bash
cd backend && cp .env.example .env   # set POSTGRES_PASSWORD, DATABASE_URL/TEST_DATABASE_URL, SEED_PASSWORD
npm install && npm run db:up && npm run seed && npm run dev
# new terminal
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Backend API: http://localhost:4000 · Frontend: http://localhost:5173

Demo accounts (password = `SEED_PASSWORD` from `.env`):

| Role | Email |
|---|---|
| Student | `amara@school.edu` (+ 9 more, see `backend/README.md`) |
| Advisor | `eramirez@school.edu` (+ 5 more) |
| Admin | `admin@school.edu` |

Advisors/admins have TOTP 2FA; the setup key is shown on first login.

## Backend architecture

```
backend/src/
  server.js       starts the HTTP server
  app.js          middleware stack and route mounting
  config.js       validated environment (fails fast on bad config)
  db/             pool, migration runner, migrations/*.sql, demo seed
  lib/            crypto (scrypt, tokens), TOTP, time zones, CSV, mailer, audit log, settings, errors, logger
  middleware/     sessions, role guards, API keys, origin check, rate limits
  services/       academic rules (GPA, degree audit, graduation, risk flags, approval pre-checks), calendar, .ics, notifications
  services/ai/    AI advisor: blocked-topic guard, per-student data tools, Claude + rule-based engines, retention
  routes/         one router per area (auth, students, advisors, approvals, admin/…)
backend/test/     node:test + supertest
```

Key behaviors:
- **Auth**: opaque 256-bit session tokens, httpOnly/SameSite=Lax cookies, only a SHA-256
  hash is stored server-side. Passwords use scrypt. "Keep me signed in" = 30-day cookie.
- **Two-step sign-in**: RFC 6238 TOTP for advisors/admins (admin setting can disable it).
- **Authorization**: every route checks caller role; records outside a caller's scope
  return 404 (not 403).
- **Derived, not stored**: GPA, credits, degree audit, graduation estimate, risk flags,
  booking availability are computed from enrollments/submissions/events/meetings — never
  cached as separate columns.
- **Approval pre-checks** (`services/academics.js`): plans/forms/drops are validated
  against remaining requirements, prerequisites, course offering, full-time load, and
  form completeness before approval.
- **AI advisor**: answers come from Claude (`@anthropic-ai/sdk`, only when `ANTHROPIC_API_KEY` is set
  and the admin engine is "Claude") or the rule-based engine (fallback, and always in tests). Both read
  data only through `services/ai/tools.js`, which is bound to the signed-in student and gated by the admin's
  data sources and the student's preferences. Blocked topics are handed off before any engine runs.
  Plan course codes are validated against the database (`services/ai/plan.js`).
- **Errors**: always `{"error": {"code", "message", "details?"}}` with correct HTTP status.
- **Security**: helmet headers, CORS limited to `CORS_ORIGINS`, origin check on
  cross-site writes, rate limits on auth endpoints, parameterized SQL only, CSV export
  formula-injection neutralization, audit log, 100 kB JSON body cap.

Full API reference, env var list, and script table: `backend/README.md`.

## Frontend architecture

```
frontend/src/
  App.jsx                  route tree
  auth/                    AuthContext, RequireRole (role-based route guards)
  components/layout/       AppShell, Sidebar, PageHeader, MasterDetail
  components/ui/           Button, Card, Icon, Logo, Pill, ProgressBar, Status, Tabs, Switch, Avatar,
                           Field, Notice, Dialog, Toast, BarChart, SearchInput, ChatBubble (props: components/README.md)
  components/ai/           AiMessage, PlanBlock, FlaggedAnswers (shared by the AI screens)
  components/messages/     ConversationList, MessageThread, Composer, NewConversationDialog (student + advisor Messages)
  config/nav.js            sidebar navigation config
  lib/api.js                API client (talks to backend via VITE_API_URL, default proxied /api)
  lib/useApi.js             GET hook with abort/error/reload — use for every screen's data
  lib/dates.js              relativeDate ("Today", "Sep 14"), clockTime, addDays/mondayOf/shortDay for YYYY-MM-DD
  pages/
    auth/Login.jsx
    student/Dashboard.jsx
    student/Courses.jsx
    student/DegreePlan.jsx
    student/AiAdvisor.jsx
    student/Schedule.jsx   week grid, personal events, deadlines, .ics feed link
    student/Assignments.jsx  list/detail with status + course filters, step checklist, submit (forms open a dialog)
    student/Messages.jsx   inbox list + thread, optimistic replies, new-conversation dialog; system threads read-only
    student/Settings.jsx   profile, notifications, AI prefs (one Save), sign-in, privacy/account actions
    student/BookMeeting.jsx  person/topic/format/day/slot booking from real availability, upcoming meetings (accept/cancel)
    admin/Overview.jsx     AI sections only
    admin/AiSettings.jsx
    dev/UiKit.jsx          dev-only component showcase at /dev/ui
    Placeholder.jsx        shown for the ~15 routes not built yet
    NotFound.jsx
```

**Implemented:** Login, the Student Dashboard, My courses, Degree plan, AI advisor, Schedule, Assignments, Messages, Student Settings, Book a meeting, Admin AI settings, and
the AI sections of Admin Overview (its other sections show a "coming soon" notice).
All other routes render `Placeholder.jsx` ("This screen isn't built yet") — their backend endpoints
already exist and are documented in `backend/README.md`.

## Not built yet (by design, not a bug)

- **AI advisor extras**: no streaming replies; advisors' "Student record" screen (which would show
  shared AI conversations from `GET /students/:id/ai/threads`) is still a placeholder.
- **Calendar integrations**: Google Calendar/Outlook work only via each student's `.ics`
  feed URL subscription — no direct calendar-API push/sync.
- **Most frontend screens**: see above.
- **Sample data only**: seed data is invented. Get approval before loading real student
  records (FERPA applies).

## Commands

Backend (`cd backend`):
| Command | Purpose |
|---|---|
| `npm run dev` / `npm start` | Run API, with/without file watch |
| `npm run db:up` / `npm run db:down` | Start/stop Postgres container |
| `npm run migrate` | Apply pending migrations |
| `npm run seed` | Migrate, then wipe + reload demo data (refuses in production) |
| `npm run db:reset` | Drop all tables, re-migrate, re-seed |
| `npm test` | Unit + API tests against `TEST_DATABASE_URL` |

Frontend (`cd frontend`):
| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server (http://localhost:5173) |
| `npm run build` | Production build |

## Conventions / gotchas

- New backend schema changes go in the next numbered file, `backend/src/db/migrations/003_<name>.sql`
  (sequential, applied once, tracked in `schema_migrations`).
- `.env` files (backend and frontend) are gitignored — never commit secrets; copy from
  the respective `.env.example`.
- The `Doumentation/` folder name is a pre-existing typo in the repo structure — leave it.
- `ANTHROPIC_API_KEY` sends students' questions and the academic data needed to answer them to
  Anthropic. Fine for the invented seed data; get approval before real student records (FERPA).
- `ALLOW_DEMO_RESET` and other destructive admin settings must stay `false` outside
  local/demo use.

## Local project structure

- `.claude/specs/` — feature/change specs for this project (gitignored, local only).
