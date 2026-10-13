# F2026-Team3

Acadmate: academic advising for students, faculty advisors and administrators.

- `frontend/`: React + Vite + Tailwind web app
- `backend/`: Node.js/Express REST API with PostgreSQL. Setup, environment variables, demo accounts and the API reference are in [backend/README.md](backend/README.md)
- `Doumentation/`: project documents, presentations and the static design prototypes

Quick start (Docker Desktop and Node.js 20+ required):

```bash
cd backend && cp .env.example .env   # set the passwords in .env
npm install && npm run db:up && npm run seed && npm run dev
# new terminal
cd frontend && npm install && npm run dev   # http://localhost:5173
```
