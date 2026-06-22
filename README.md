# Work Schedule Optimization System

A full-stack web app that generates employee shift schedules with two optimization
approaches — a **Genetic Algorithm (GA)** and a **CP-SAT** constraint solver (Google
OR-Tools) — and formally benchmarks them against each other. Bachelor's thesis project.

A manager configures the workforce (employees, shift types, working rules, leave) and
triggers schedule generation for a planning period. Both solvers are scored by one
shared constraint checker, so their results are directly comparable.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) |
| Data | PostgreSQL 16 · SQLAlchemy 2.0 · Alembic |
| Async | Celery · Redis |
| Optimization | OR-Tools CP-SAT + hand-written GA |
| Frontend | React 18 · TypeScript · Vite |
| Deploy | Docker Compose + nginx |

## Getting started

Create your environment file once, then pick **one** way to run — Option A or Option B.
You do **not** need to do both.

```bash
cp .env.example .env        # set SECRET_KEY (>=32 chars) + INITIAL_MANAGER_EMAIL/PASSWORD
```

### Option A — Docker (recommended)

**Prerequisites:** Docker only (no Python or Node.js needed — the images install everything).

One command builds and runs the whole stack behind an nginx reverse proxy
(single origin, no CORS):

```bash
docker compose up --build
```

Open **http://localhost:8080** (API docs at `/docs`).

Everything is automatic: `db` + `redis` → `migrate` (Alembic + seed defaults) →
`backend` + `worker` → `frontend`. Stop with `docker compose down`
(data persists in the `pgdata` volume).

### Option B — Native (for development)

**Prerequisites:** Docker (for the datastores) + Python 3.12 + Node.js 18+.

Run only the datastores in Docker and the app processes yourself.

```bash
# one-time setup
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1          # Windows (use bin/activate on macOS/Linux)
pip install -r backend/requirements.txt

docker compose up -d db redis               # start PostgreSQL + Redis only
cd backend && alembic upgrade head && python seed.py
```

Then run these three processes, each in its own terminal:

```bash
uvicorn app.main:app --reload                                            # API at http://localhost:8000
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo   # worker (drop --pool=solo on Linux)
cd frontend && npm install && npm run dev                                # frontend at http://localhost:3000
```

## How it works

The manager submits `POST /api/schedules/generate`; the API runs pre-flight validations and
returns a `task_id` (HTTP 202). A Celery worker builds the `ScheduleContext`, runs the chosen
solver, and persists the schedule, while the frontend polls task status until it finishes.

Both algorithms enforce the same hard constraints (one shift per day, minimum rest, max
consecutive days, monthly hours cap, exact staffing, approved leave, non-working days, and
night-work limits from the Bulgarian Labour Code) and minimize a weighted soft-penalty
objective (unmet preferences, under-utilization, long runs, weekend/night fairness, and
hours balance). Scoring lives in one shared evaluator — `backend/app/optimization/evaluate.py`;
objective weights are defined once in `weights.py`.

## Project layout

```
backend/    FastAPI app, Alembic migrations, seed.py
  app/optimization/   evaluate.py · ga.py · cpsat.py · weights.py
benchmark/  GA-vs-CP-SAT comparison harness (run from repo root)
frontend/   React + TypeScript + Vite SPA (served by nginx in production)
docker-compose.yml · .env.example
```

## Authentication

JWT bearer tokens. The first manager is bootstrapped from `INITIAL_MANAGER_EMAIL` /
`INITIAL_MANAGER_PASSWORD` on first backend start; new accounts receive a server-generated
temporary password to change on first login. In Swagger, get a token from
`POST /api/auth/login` and paste it into **Authorize → HTTPBearer**.
