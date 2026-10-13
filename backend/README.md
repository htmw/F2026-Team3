# Acadmate API

REST backend for the Acadmate frontend (`../frontend`): Node.js 20+ / Express 5, PostgreSQL 16 (Docker), plain SQL with versioned migrations, zod validation, cookie sessions, TOTP two-step sign-in for staff, and a seeded demo world that matches the design prototypes in `Doumentation/Frontend prototypes/acadmate-static`.

## Quick start

```bash
# 1. Configure (then edit .env: set POSTGRES_PASSWORD, the same password inside DATABASE_URL/TEST_DATABASE_URL, and SEED_PASSWORD)
cd backend
cp .env.example .env

# 2. Install and start Postgres (Docker Desktop must be running)
npm install
npm run db:up

# 3. Create the schema and load demo data
npm run seed          # runs pending migrations, then wipes and reloads demo data

# 4. Run the API on http://localhost:4000
npm run dev           # auto-restarts on file changes; `npm start` for production

# 5. In another terminal, run the frontend on http://localhost:5173
cd ../frontend
npm install
npm run dev
```

Sign in at http://localhost:5173 with any demo account. All of them use the `SEED_PASSWORD` from `.env`:

| Role | Email |
|---|---|
| Student | `amara@school.edu` (also `dkowalski`, `pshah`, `mthompson`, `lhaddad`, `jpark`, `srossi`, `kasante`, `nkim`, `gliu`) |
| Advisor | `eramirez@school.edu` (also `mchen`, `spatel`, `ladeyemi`, `jlee`, `gradoffice`, `dfischer`) |
| Admin | `admin@school.edu` |

Advisors and admins have two-step sign-in. The first time each one signs in, the login screen shows a setup key: add it to any authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…) and enter the 6-digit code. Running `npm run seed` again clears the enrolment.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` / `npm start` | Start the API (with / without file watching) |
| `npm run db:up` / `npm run db:down` | Start / stop the Postgres container |
| `npm run migrate` | Apply pending migrations in `src/db/migrations` |
| `npm run seed` | Apply migrations, then **wipe** all data and load the demo data (refuses when `NODE_ENV=production`) |
| `npm run db:reset` | Drop every table, re-migrate and re-seed |
| `npm test` | Unit + end-to-end API tests against `TEST_DATABASE_URL` (wiped on every run) |

To add a schema change, create the next numbered file, e.g. `src/db/migrations/003_<name>.sql`; `npm run migrate` applies it once and records it in `schema_migrations`.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | for Docker | Used by `docker-compose.yml` to create the database |
| `TEST_DATABASE_URL` | for tests | Separate database the tests wipe (the container creates `acadmate_test` automatically) |
| `SEED_PASSWORD` | for seeding | Password given to every demo account (8+ characters) |
| `PORT` | no (4000) | API port |
| `CORS_ORIGINS` | no (`http://localhost:5173`) | Comma-separated browser origins allowed to call the API with credentials |
| `APP_URL` | no (`http://localhost:5173`) | Frontend URL used in emailed links and after Google sign-in |
| `API_URL` | no (`http://localhost:4000`) | Public API URL, used for the Google callback and calendar feed links |
| `TRUST_PROXY` | no (false) | Set `true` behind a reverse proxy / load balancer |
| `LOG_LEVEL` | no (info) | `debug`, `info`, `warn`, `error`, `silent` |
| `ALLOW_DEMO_RESET` | no (false) | Lets admins wipe and re-seed from `POST /api/admin/demo/reset`. Never enable in production |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional | Enables "Sign in with Google". Authorised redirect URI: `${API_URL}/api/auth/google/callback` |
| `ANTHROPIC_API_KEY` | optional | Lets the AI advisor answer with Claude. Without it, answers come from the rule-based engine. See *AI advisor* below before using real student data |
| `AI_MODEL` / `AI_EFFORT` / `AI_TIMEOUT_MS` | no (`claude-opus-5-5` / `medium` / 60000) | Claude model, reasoning effort (`low`, `medium`, `high`; higher costs more) and per-request timeout |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURE` / `SMTP_USER` / `SMTP_PASS` / `MAIL_FROM` | optional | Sends reset, invite and notification emails. Without `SMTP_HOST`, each email is printed to the API log, so reset links still work locally |

The frontend reads `VITE_API_URL` (default `/api`, proxied by Vite to `API_PROXY_TARGET`, default `http://localhost:4000`). See `frontend/.env.example`.

## Architecture

```
src/
  server.js           starts the HTTP server
  app.js              middleware stack and route mounting
  config.js           validated environment (fails fast on bad config)
  db/                 pool, migration runner, migrations/*.sql, demo seed
  lib/                crypto (scrypt, tokens), TOTP, time zones, CSV, mailer, audit log, settings, errors, logger
  middleware/         sessions, role guards, API keys, origin check, rate limits
  services/           academic rules (GPA, degree audit, graduation, risk flags, approval pre-checks), calendar, .ics, notifications
  services/ai/        AI advisor: blocked-topic guard, per-student data tools, Claude and rule-based engines, retention
  routes/             one router per area (auth, students, advisors, approvals, admin/…)
test/                 node:test + supertest
```

- **Auth.** Opaque 256-bit session tokens in an `httpOnly`, `SameSite=Lax` cookie (`Secure` in production). Only a SHA-256 hash of the token is stored, in `sessions`, so logging out, changing a password or deactivating an account revokes it immediately. Passwords use scrypt. "Keep me signed in" gives a 30-day cookie. Other sessions also expire after the admin's idle timeout.
- **Two-step sign-in.** Advisors and admins enter an RFC 6238 TOTP code (an admin setting can turn this off). The authenticator is enrolled on first sign-in.
- **Authorisation.** Every route checks the caller's role. Advisors see only their own advisees, approvals and meetings, students only their own records, and a record you can't access returns 404.
- **Derived, not stored.** GPA, credits, degree audit, expected graduation, on-time rate, attendance, study hours, advisee status and risk flags, and booking availability are all computed from enrollments, submissions, events and meetings.
- **Approval pre-checks.** Course plans, forms and drop requests are checked against the rules in `services/academics.js`: remaining requirements, prerequisites, course offered, full-time load, and form completeness. Approving or requesting changes updates the student's record. For example, an approved plan marks those courses approved and a drop removes the course.
- **AI advisor.** See the section below.
- **Errors.** Every error is `{"error": {"code", "message", "details?"}}` with the right HTTP status. Validation failures are `400 validation_error` with a field list.
- **Security.** `helmet` headers. CORS limited to `CORS_ORIGINS`. Cross-site writes are rejected by an Origin check. Rate limits on sign-in, reset and sign-up. Parameterised SQL only. CSV exports neutralise spreadsheet formulas. Audit log of sign-ins, decisions and admin changes. JSON request bodies are capped at 100 kB.

## API reference

All paths are under `/api`. 🔒 = requires a session, with the role in brackets.

**Auth**: `GET /auth/config` · `GET /auth/me` 🔒 · `POST /auth/signup` · `POST /auth/login` → `{user, home}` or `{mfaRequired, challenge, setup}` · `POST /auth/2fa/verify` · `GET /auth/2fa/challenge/:token` · `POST /auth/logout` · `POST /auth/password-reset` · `GET /auth/password-reset/:token` · `POST /auth/password-reset/confirm` · `GET /auth/google?intent=login|connect` · `GET /auth/google/callback`

**Account** 🔒: `GET/PATCH /users/me` · `PATCH /users/me/preferences` · `POST /users/me/password` · `POST /users/me/google/connect` · `DELETE /users/me/google` · `POST /users/me/export` · `DELETE /users/me` (students) · `GET /users/me/badges`

**Student** 🔒[student]: `GET /students/me/dashboard` · `GET /students/me/courses?status=current|completed|planned` · `GET /courses/:id/grades` · `GET /students/me/degree-audit` · `GET /students/me/plan` · `POST /students/me/plan` · `DELETE /students/me/plan/:enrollmentId` · `POST /students/me/plan/submit` · `POST /students/me/requests` (drop) · `GET /students/me/events?from=&to=` · `POST /students/me/events` · `PATCH/DELETE /students/me/events/:id` · `GET /students/me/calendar` (feed URL) · `POST /students/me/calendar/rotate` · `GET /students/me/calendar.ics` · `GET /calendar/:token.ics` (public feed) · `GET /students/me/assignments?status=&course=` · `GET /assignments/:id` · `PATCH /assignments/:id/progress` · `POST /assignments/:id/submit` · `GET /students/me/meetings` · `GET /catalog`

**AI advisor** 🔒[student]: `GET /students/me/ai/context` · `GET /students/me/ai/threads` · `POST /students/me/ai/threads` (`{ text }` answers the first question) · `GET/DELETE /students/me/ai/threads/:id` · `DELETE /students/me/ai/threads` (clear history) · `POST /students/me/ai/threads/:id/messages` · `POST /students/me/ai/messages/:id/rating` · `POST /students/me/ai/messages/:id/flag`

**Messages** 🔒: `GET /conversations?q=` · `GET /conversations/contacts?q=` · `POST /conversations` · `GET /conversations/:id/messages` (marks read) · `POST /conversations/:id/messages`

**Meetings** 🔒: `GET /staff?bookable=true` (each person: name, role, helps, office, meetingLength, bookingWindowWeeks, isMyAdvisor; plus topics/formats) · `GET /staff/:id/availability?week=YYYY-MM-DD` · `POST /meetings` [student] · `POST /meetings/:id/accept` [student] · `POST /meetings/:id/cancel` · `PUT /meetings/:id/notes` [staff] · `POST /bookings/:id/accept|propose|decline` [staff]

**Advisor** 🔒[advisor, admin]: `GET /advisors/me/dashboard` · `GET /advisors/me/advisees?status=&q=` · `GET /students/:id/record` · `POST /students/:id/notes` · `GET /students/:id/ai/threads` (only if the student shares them) · `GET /approvals?status=` · `GET /approvals/:id` · `POST /approvals/:id/approve` · `POST /approvals/:id/request-changes` (comment required) · `POST /approvals/:id/reopen` · `GET /advisors/me/meetings?range=today|week` · `PUT /advisors/me/office-hours` · `GET /advisors/me/reports?term=` · `GET /advisors/me/reports.csv` · `GET/PATCH /advisors/me/settings`

**Admin** 🔒[admin]: `GET /admin/overview` · `GET /admin/overview/report` (CSV) · `GET /admin/users?role=&status=&q=&page=` · `GET/PATCH /admin/users/:id` · `POST /admin/users/:id/password-reset` · `POST /admin/invites` · `POST /admin/imports/users|courses|grades` (`Content-Type: text/csv`) · `GET/POST /admin/advisors` · `PATCH /admin/advisors/:id` · `POST /admin/advisors/:id/reassign` · `GET/POST /admin/courses` · `GET/PATCH /admin/courses/:code` · `GET /admin/programs` · `GET/PUT /admin/programs/:id/requirements` · `GET /admin/terms` · `GET/PUT /admin/terms/:id/dates` · `POST /admin/catalog/publish` · `GET/PATCH /admin/ai/settings` · `POST /admin/ai/test` · `GET /admin/ai/flags` · `POST /admin/ai/flags/:id/resolve` · `GET /admin/integrations` · `POST /admin/integrations/:id/connect|disconnect|sync` · `POST /admin/api-keys` · `DELETE /admin/api-keys/:id` · `GET /admin/audit?role=&since=&q=` · `GET /admin/audit/:id` · `GET /admin/audit.csv` · `GET/PATCH /admin/settings` · `POST /admin/demo/reset`

The two report exports (`/admin/overview/report`, `/admin/audit.csv`) also accept `Authorization: Bearer <API key>` from `POST /admin/api-keys`. Keys can't call anything else.

### Trying it with curl

```bash
curl -c jar.txt -H 'content-type: application/json' \
  -d '{"email":"amara@school.edu","password":"<SEED_PASSWORD>"}' http://localhost:4000/api/auth/login
curl -b jar.txt http://localhost:4000/api/students/me/dashboard
```

## AI advisor

Students ask questions in `/student/ai-advisor`; answers are grounded in their own records.

- **Pipeline** (`services/ai/index.js`): the school's on/off switch → blocked topics → Claude, if `ANTHROPIC_API_KEY` is set and the admin engine is "Claude" → otherwise the rule-based engine. If a Claude request fails, the rule-based engine answers instead.
- **Blocked topics** (`guard.js`) are matched before any engine runs. Those questions are handed to a person and never sent to Claude.
- **Data tools** (`tools.js`) are the only way either engine reads data. Each tool is bound to the signed-in student, so there is no student id a prompt could change. A tool is offered only when the admin's data sources and the student's own preferences allow it. The "Based on" line shows the tools that actually ran.
- **Plans** (`plan.js`): course codes in an answer are kept only if they are real catalog courses or on the student's plan. Names, terms and the requirement filled come from the database.
- **Claude** (`claudeEngine.js`) uses the SDK tool runner (`claude-opus-5-5` by default, at most 6 tool rounds) with a structured final answer, a cached system prompt, and the server-side refusal fallback. Token usage is stored per answer. Expect very roughly a few US cents per question. The per-student daily limit (admin setting) and the rate limiter cap spend.
- **Storage.** `ai_threads` / `ai_messages` keep conversations as they were said. Retention follows Admin → Settings → AI history, purged daily. Students can rate, report or delete answers. Admins review reports in AI settings, and advisors can read a student's conversations only if the student turns on sharing.
- **Privacy.** With the Claude engine, a student's question and the parts of their academic record needed to answer it are sent to Anthropic's API. The seed data is invented. **Get approval before using real student records (FERPA).**

## Not included yet

- **Calendar integrations.** Google Calendar and Outlook work by subscribing to each student's `.ics` feed URL. The admin connect/disconnect switches only record the setting; there is no direct calendar-API sync.
- **Placeholder screens.** The frontend has only the Login and Student dashboard screens. The other 23 routes still show "This screen isn't built yet", and their endpoints above are ready for them.
- **Sample data only.** The seed uses invented people and grades. Get approval before loading real student records (FERPA).
