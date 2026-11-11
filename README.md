# F2026-Team3 AcadMate

Acadmate: academic advising for students, faculty advisors and administrators.

- `frontend/`: React + Vite + Tailwind web app
- `backend/`: FastAPI (Python) REST API with PostgreSQL through SQLAlchemy
- `Doumentation/`: project documents, presentations and the static design prototypes

Quick start (Python 3.10+ and Node.js 20+ required). The database is hosted on Neon (Postgres): get the
connection strings from the Neon console (project → Connect, database `acadmate_sprint2`).

```bash
cd backend
cp .env.example .env               # paste the Neon pooled string into DATABASE_URL (keep ?sslmode=require)
python -m venv venv
venv\Scripts\activate              # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python test_db.py                  # checks the database connection
python reset_db.py --yes && python seed_data.py   # ONLY for an empty database: drops every table, loads demo data
uvicorn main:app --reload          # http://localhost:8000, API docs at /docs (--port 8001 if 8000 is taken)

# new terminal
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

To send frontend API calls to the FastAPI server, create `frontend/.env.local` with:

```
VITE_API_URL=/api/v1
API_PROXY_TARGET=http://localhost:8000
```

Try it: `GET http://localhost:8000/api/v1/students/101/academic-profile` returns the seeded demo student.

### Demo accounts

Seeded by `seed_data.py`. All use the password `Acadmate!2026` (demo only, never real data).

| Role | Email |
|---|---|
| Student (id 101) | amara.okafor@pac.edu |
| Advisor (id 201) | sarah.smith@pac.edu |
| Admin | jordan.lee@pac.edu |
| Deactivated student (sign-in is refused) | sam.rivera@pac.edu |

Pending advisor invite (Dr. Priya Natarajan): open <http://localhost:5173/reset-password?token=demo-invite-token>
to set a password and activate the account. Password reset emails aren't sent yet: the reset link is printed in the
uvicorn log (logger `acadmate.mail`). Five wrong passwords lock an email for 15 minutes.

Sign in as Jordan Lee and open <http://localhost:5173/admin> for the platform overview: usage, AI answer quality,
flagged answers, system status and advisor workload (Prof. Daniel Kim is seeded over capacity). **Export report**
downloads the same figures as a CSV. **Users** (`/admin/users`) lists every account: invite people by email, import a CSV
(`name,email,role,program`), change a student's advisor, or deactivate an account (invite and reset links are printed
in the uvicorn log, like password resets). **Advisors** (`/admin/advisors`) shows each advisor's caseload against
capacity: add an advisor (by invite), change a capacity, or move advisees to another advisor (moved students get a
notice and an email, and their pending approvals move with them).

### Changing the database schema

There are no migrations. After changing `backend/models.py`, rebuild the tables and reload the demo data
(this deletes everything in the database):

```bash
python reset_db.py --yes && python seed_data.py
```

### Backend settings

`backend/.env.example` lists every variable with a comment. Only `DATABASE_URL` is required.

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
(the commented lines in `.env.example`):

```bash
docker run -d --name acadmate-fastapi-db -e POSTGRES_USER=acadmate -e POSTGRES_PASSWORD=<choose-one> \
  -e POSTGRES_DB=acadmate -p 5433:5432 -v acadmate-fastapi-pg:/var/lib/postgresql/data postgres:16-alpine
docker exec acadmate-fastapi-db createdb -U acadmate acadmate_test
```
