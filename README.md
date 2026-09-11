# University Management API

Backend system for managing a university: colleges, departments, courses, teachers, students, and course enrollments — with **asynchronous transcript generation** built on a PostgreSQL-backed job queue with leases, heartbeats, retries, and crash recovery.

Built as a demonstration of production-grade backend engineering: the system is not a simple CRUD app, but a distributed system that handles concurrency, failures, and recovery scenarios correctly.

---

## The Problem

A university management system looks deceptively simple, but hides hard distributed-systems problems:

- **Concurrent enrollment races**: two simultaneous enrollment requests for the same seat, or the same enrollment code, must not both succeed.
- **Lost updates**: two admins editing the same student record must not silently overwrite each other.
- **Long-running report generation**: transcripts must not block HTTP requests; they must be generated in the background, survive worker crashes, and never be produced twice.
- **Partial failures**: PostgreSQL, Redis, or a worker process can disappear at any moment. The system must converge to a consistent state without human intervention.
- **Access control**: students see only their own data; admins see everything. Rate limits must protect the authentication endpoints.

This project solves each of these explicitly and tests the solutions.

---

## Engineering Highlights

What separates this project from a standard CRUD API:

| Feature | How it is solved |
|---|---|
| **Optimistic locking** | `Student` uses SQLAlchemy `version_id`; concurrent updates are detected and rejected with `409 Conflict` instead of silently overwriting each other. |
| **Background jobs** | Reports run in a dedicated worker process (`app/workers/`). The API enqueues jobs by writing one row to PostgreSQL and returns `202` immediately. |
| **Atomic job claiming** | Workers claim jobs with a single `UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED)` statement — no Redis lock, no race window, safe with N workers. |
| **Leases & heartbeats** | Each claimed job holds a time-limited lease. A background thread renews it while generation runs. If a worker dies, its lease expires and another worker takes over. |
| **Job recovery** | On startup and on every claim, the worker reconciles jobs whose report was persisted but whose status was not finalized — no stuck `processing` rows, ever. |
| **Idempotent report persistence** | `report.job_id` is `UNIQUE`. Two workers racing to persist the same transcript collide on the constraint; the loser adopts the winner's result instead of failing. |
| **Fencing for stale workers** | Job state transitions are guarded by `(worker_token, job_version)`. A worker that lost its lease cannot mark a job completed/failed/queued. |
| **Retry with exponential backoff** | Transient failures re-queue the job with `retry_at = now + base * 2^attempt`; permanent failures (e.g., student deleted) fail immediately. `job_max_attempts` bounds retries. |
| **TOCTOU-safe enrollment** | Application-level pre-checks for friendly `409`s, plus a database `UNIQUE(student_id, course_offering_id)` constraint as the final arbiter — proven correct under interleaved transactions. |
| **PostgreSQL as source of truth** | Every status read comes from PostgreSQL. Redis is a disposable cache: killing it never fails a request. |
| **RBAC** | JWT auth with three roles (`admin` / `user` / `guest`). Users are scoped to their own linked student record via `user_id` filtering at the query level, not by post-filtering. |
| **Rate limiting** | `slowapi` limits on register/login. Storage defaults to Redis (shared across replicas) with automatic in-memory fallback if Redis is unreachable. |
| **Timing-safe login** | Non-existent emails run a dummy Argon2 verification so response time cannot reveal which emails exist. |

---

## Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │                  Clients                     │
                        └──────────────────────┬───────────────────────┘
                                               │ HTTPS / JWT
                                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  API (FastAPI, uvicorn)                                                  │
│                                                                          │
│  • REST endpoints (colleges, courses, students, enrollments, reports)     │
│  • RBAC: admin / user / guest                                             │
│  • Rate-limited auth endpoints (slowapi + Redis)                          │
│                                                                          │
│  POST /reports/export/{id}  ──writes──►  job row (status=queued)  ──► 202 │
└───────────────┬──────────────────────────────────────────────┬───────────┘
                │ SQLAlchemy (pool_pre_ping)                    │
                ▼                                               │
┌───────────────────────────────────────────────────────────────┴──────────┐
│  PostgreSQL — source of truth                                             │
│  job / report / student / enrollment / course / ...                       │
│  • UNIQUE(report.job_id)        → idempotent persistence                  │
│  • UNIQUE(student_id, offering) → enrollment arbiter                       │
│  • student.version_id           → optimistic locking                      │
│  • job.lease_until + token      → leases & fencing                         │
└───────────────▲──────────────────────────────────────────────┬───────────┘
                │ reads/writes                                │
                │                                             │ claim: FOR UPDATE
                │                                             │ SKIP LOCKED
┌───────────────┴──────────────────────────────────────────────┴───────────┐
│  Worker (python -m app.workers.runner)                                   │
│                                                                          │
│  claim ─► heartbeat thread ─► generate ─► persist report + complete job  │
│  • lease renewal every N sec           • retry with backoff on failure   │
│  • takeover of expired leases          • reconciliation of reported jobs │
└──────────────────────────────────────────────────────────────────────────┘

┌────────────────────────┐
│  Redis (cache/limiter) │  student read-cache (60s TTL) + rate-limit
│  counts, never truth   │  storage. Full outage → degraded, not down.
└────────────────────────┘
```

**Job lifecycle:** `queued` → (worker claims atomically) → `processing` → `completed` | `queued` (retry w/ backoff) | `failed` (permanent / attempts exhausted). Abandoned leases are reclaimed; reported-but-unfinalized jobs are reconciled to `completed`.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Framework | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 (typed mappings) |
| Database | PostgreSQL 16 (Alembic migrations) |
| Cache / rate-limit storage | Redis 7 (optional — graceful fallback) |
| Auth | PyJWT (HS256), pwdlib/Argon2 |
| Rate limiting | slowapi |
| Packaging | uv |
| Runtime | Docker / Docker Compose (web + worker + db + redis) |
| Testing | pytest (+ real-Postgres integration tests) |
| Quality | ruff (lint + format), bandit (SAST), GitHub Actions CI |

---

## Testing

**206 tests**, including integration tests that run against a real PostgreSQL instance:

```powershell
uv run pytest -q
```

Coverage beyond unit tests:

- **Concurrency tests** — two workers claiming simultaneously get *different* jobs; expired-lease takeover increments `job_version`; a fenced (stale) worker cannot mutate the job.
- **Race-condition demos** — interleaved transactions proving the enrollment TOCTOU pre-check alone is insufficient and the DB constraint is the real arbiter.
- **Job lifecycle tests** — transient failure → retry → success; attempts exhaustion → `failed`; existing report → adopted, never regenerated.
- **Degradation tests** — Redis completely offline: jobs still complete, reads still served, rate limiter falls back to in-memory.
- **API tests** — full auth matrix (admin/user/guest), response schemas, pagination bounds.

Quality gates (all must pass locally and in CI):

```powershell
uv run ruff check .        # lint
uv run ruff format --check .  # formatting
uv run bandit -q -r app    # security (SAST)
```

CI (`.github/workflows/ci.yml`) runs on every push/PR: lint → Alembic migration on a fresh Postgres → full test suite.

---

## Running the Project

### Requirements
- Python 3.14, uv
- Docker + Docker Compose (or a local PostgreSQL 16 + Redis 7)

### Quick start (Docker — recommended)

```powershell
Copy-Item .env.example .env   # edit values
docker compose up --build
```

This starts: **web** (API on `:8000`), **worker** (report processor), **db** (Postgres 16), **redis** (7). Migrations run automatically on the web container's entrypoint.

Interactive docs: `http://127.0.0.1:8000/docs`

### Local development

```powershell
Copy-Item .env.example .env   # point DATABASE_URL/REDIS_URL at your services
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In a second terminal, run the worker:

```powershell
uv run python -m app.workers.runner
```

> Without the worker, `/reports/export` jobs stay `queued` forever — the API never executes them in-process by design.

### Bootstrap admin

```powershell
# interactive (prompts for password):
uv run python -m app.cli create-admin --email admin@example.com --username admin

# or via environment variables:
$env:ADMIN_EMAIL="admin@example.com"; $env:ADMIN_USERNAME="admin"; $env:ADMIN_PASSWORD="SuperSecretPass123!"
uv run python -m app.cli create-admin
```

### Key configuration (`app/config.py` / env)

| Setting | Default | Purpose |
|---|---|---|
| `job_poll_interval_seconds` | 1.0 | Worker poll cadence |
| `job_lease_seconds` | 120 | Job lease duration |
| `job_heartbeat_seconds` | 30 | Lease renewal interval |
| `job_max_attempts` | 3 | Retry bound per job |
| `job_retry_base_seconds` | 5 | Backoff base (`5, 10, 20s`) |
| `worker_retry_attempts` | 3 | Worker retries on transient DB errors |
| `RATE_LIMIT_STORAGE_URI` | `memory://` | `redis://…` to share limits across replicas |

### API quick reference

| Method & Path | Auth | Description |
|---|---|---|
| `POST /users/register` · `POST /users/login` | — | Auth (rate-limited) |
| `GET /students/{id}` | admin/user | Student (user → own record only) |
| `POST /enrollments/` | admin | Enroll student (TOCTOU-safe) |
| `GET /reports/transcript/{id}` | admin/user | Synchronous transcript |
| `POST /reports/export/{id}` | admin/user | Queue async transcript → `202` + `job_id` |
| `GET /reports/jobs/{job_id}` | admin/user | Job status/result (owner or admin) |

Full schema: `/docs` (OpenAPI/Swagger).
