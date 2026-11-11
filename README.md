# F2026-Team3 AcadMate

Acadmate: academic advising for students, faculty advisors and administrators.

- `frontend/`: React 19 + Vite 8 + Tailwind CSS 4 web app (JSX, react-router-dom 7)
- `backend/`: FastAPI (Python 3.10+) REST API with PostgreSQL (hosted on Neon) through SQLAlchemy 2
- `Doumentation/`: sprint docs, personas, Jira exports, presentations and wiki diagrams

## Features 

| Role | Screens |
|---|---|
| Student | Dashboard, My courses (grades, insights), Degree plan (audit, roadmap, submit for approval), Assignments, Schedule (with an `.ics` calendar feed), Messages, Book a meeting, AI advisor, Settings |
| Advisor | Dashboard, Advisees, Student record (private notes), Approvals queue, Meetings and office hours, Messages (incl. the advising team group), Reports (CSV export), Settings |
| Admin | Platform overview, Users (add users with a temporary password, reset passwords, CSV import), Advisors (capacity, reassignment), Catalog (drafts and publish), Integrations (CSV imports, mail, calendars, API keys), AI settings and flagged answers, Audit log, Settings |

## Quick start

Python 3.10+ and Node.js 20+ required. The database is hosted on Neon (Postgres): get the connection strings
from the Neon console (project → Connect, database `acadmate_sprint2`).

> `acadmate_sprint2` is shared by the whole team and already holds the demo data. Don't run `reset_db.py`,
> `seed_data.py` or a demo reset against it unless you mean to wipe everyone's data.

```bash
cd backend
cp .env.example .env               # paste the Neon pooled string into DATABASE_URL (keep ?sslmode=require)
python -m venv venv
venv\Scripts\activate              # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python test_db.py                  # checks the database connection
python scripts/add_must_change_password.py   # once, on a database created before spec 31 revision 2 (safe to re-run)
uvicorn main:app --reload --port 8010   # http://localhost:8010, API docs at /docs

# new terminal
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

To send frontend API calls to the FastAPI server, create `frontend/.env.local` with:

```
VITE_API_URL=/api/v1
API_PROXY_TARGET=http://localhost:8010
```

Check the API: `GET http://localhost:8010/api/v1/health`, or browse every endpoint at <http://localhost:8010/docs>.

### Demo accounts

Seeded by `seed_data.py`. All use the password `Acadmate!2026` (demo only, never real data).

| Role | Name | Email |
|---|---|---|
| Student | Amara Okafor | amara.okafor@pac.edu |
| Student (Amara's classmate) | Kofi Mensah | kofi.mensah@pac.edu |
| Advisor (Computer Science) | Dr. Sarah Smith | sarah.smith@pac.edu |
| Advisor (Computer Science, over capacity) | Prof. Daniel Kim | daniel.kim@pac.edu |
| Advisor (Career services) | Maya Brooks | maya.brooks@pac.edu |
| Advisor (Data Science, new: must choose a password at first sign-in) | Dr. Priya Natarajan | priya.natarajan@pac.edu |
| Admin | Jordan Lee | jordan.lee@pac.edu |
| Admin (Graduate office, support) | Graduate office | grad.office@pac.edu |
| Deactivated student (sign-in is refused) | Sam Rivera | sam.rivera@pac.edu |

There is no sign-up and no *Forgot password?*: administrators create accounts and reset passwords (Admin → Users).
Both give the person a **temporary password** by email (also shown to the admin once); the first sign-in with it asks
for a new password. Dr. Priya Natarajan is seeded that way. Emails aren't sent until the mail integration is
connected: they're printed in the uvicorn log (logger `acadmate.mail`), temporary passwords included. Five wrong
passwords lock an email for 15 minutes.

### What to try

- **Student (Amara):** the dashboard shows today's 15:00 check-in with Dr. Smith, 3 unread messages and her
  Spring 2027 plan waiting for approval. Book another meeting, ask the AI advisor or check the degree audit.
- **Advisor (Dr. Smith):** 9 advisees (2 high risk, Jonah Weiss graduating), pending approvals (a plan, a capstone
  form with a missing field, a drop below full time), 3 unread messages and today's meetings at 11:00 and 13:00.
- **Admin (Jordan Lee):** `/admin` shows usage, AI answer quality, flagged answers, system status and advisor
  workload (Prof. Kim is over capacity). Add users (Users → **Add user**), reset a forgotten password (select a
  user → **Reset password**), manage advisors, edit and publish the catalog, connect
  integrations, change AI and institution settings, and read the audit log. Most screens export CSV.

### Optional backend features

`backend/.env.example` lists every variable with a comment. Only `DATABASE_URL` is required.

- `ANTHROPIC_API_KEY`: lets the AI advisor use Claude (pick the engine under Admin → AI settings). Without it
  the built-in rules engine answers.
- `DEMO_MODE=true`: enables **Reset demo data** under Admin → Settings (wipes and reseeds the database).
- `ACADMATE_TODAY=YYYY-MM-DD`: pins "today" for demos.
- `GOOGLE_*` / `MICROSOFT_*`: needed to connect Google or Outlook calendars under Integrations.
- Daily jobs (run from `backend/`): `python scripts/send_reminders.py` (meeting reminders, stale approval
  reminders) and `python scripts/prune.py` (deletes audit events and AI threads past their retention).

### Changing the database schema

There are no migrations. After changing `backend/models.py`, rebuild the tables and reload the demo data
(this deletes everything in the database `DATABASE_URL` points at):

```bash
python reset_db.py --yes && python seed_data.py
```

### Backend tests

Create the database `acadmate_sprint2_test` once in the Neon console (Databases → New), put its **direct**
connection string (no `-pooler`) in `TEST_DATABASE_URL`, then:

```bash
cd backend && pytest -q
```

Tests use `TEST_DATABASE_URL` (default: `DATABASE_URL` with `_test` appended to the database name) and drop and
recreate its tables on every run. They refuse to start unless that database's name ends in `_test` and differs
from the app database.

### Local Docker database (optional)

To work offline instead of Neon, run Postgres in Docker and point `DATABASE_URL` / `TEST_DATABASE_URL` at it
(the commented lines in `.env.example`), then run `python reset_db.py --yes && python seed_data.py` once:

```bash
docker run -d --name acadmate-fastapi-db -e POSTGRES_USER=acadmate -e POSTGRES_PASSWORD=<choose-one> \
  -e POSTGRES_DB=acadmate -p 5433:5432 -v acadmate-fastapi-pg:/var/lib/postgresql/data postgres:16-alpine
docker exec acadmate-fastapi-db createdb -U acadmate acadmate_test
```
