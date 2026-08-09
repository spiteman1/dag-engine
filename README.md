# DAG Engine

> **Status: Active Development -- v0.1.0 Foundation**

A custom Directed Acyclic Graph (DAG) task execution engine built from scratch in Python. Conceptually similar to a lightweight Apache Airflow -- DAG definitions are submitted via a REST API, dependencies are resolved using graph algorithms, and workloads are distributed across multiple asynchronous workers via a Redis message broker.

**This is a learning-driven systems engineering project. Every component is written from scratch to deeply understand how distributed task orchestration works at a fundamental level. The foundation is complete and functional, but this is explicitly a v0.1 -- significant work remains before this would be considered production-grade.**

---

## Architecture Overview

```
                    ┌─────────────────┐
                    │   FastAPI REST   │
                    │   API (/docs)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │  Graph   │  │PostgreSQL│  │    Redis      │
        │  Engine  │  │  (State) │  │ (Task Queue)  │
        │ Topo Sort│  │SQLAlchemy│  │    BRPOP      │
        │ DFS Cycle│  │  Async   │  │               │
        └──────────┘  └──────────┘  └───────┬───────┘
                                            │
                              ┌─────────────┼─────────────┐
                              │             │             │
                              ▼             ▼             ▼
                        ┌──────────┐  ┌──────────┐  ┌──────────┐
                        │ Worker 1 │  │ Worker 2 │  │ Worker N │
                        │ (Async)  │  │ (Async)  │  │ (Async)  │
                        └──────────┘  └──────────┘  └──────────┘
```

---

## Tech Stack

| Component        | Technology                    |
| ---------------- | ----------------------------- |
| Backend API      | FastAPI (Python 3.11+)        |
| Database         | PostgreSQL 15                 |
| ORM              | SQLAlchemy 2.0 (Async)        |
| Migrations       | Alembic                       |
| Message Broker   | Redis 7                       |
| Workers          | Custom Python AsyncIO         |
| Validation       | Pydantic v2                   |
| Testing          | pytest                        |
| Containerisation | Docker & Docker Compose       |

---

## Project Structure

```
/dag_engine
├── dag_engine/
│   ├── api/
│   │   ├── main.py            # FastAPI app entry point, CORS, health check
│   │   ├── schemas.py         # Pydantic request/response models
│   │   └── routes/
│   │       └── dags.py        # POST /dags, POST /dags/{id}/run, GET /dags/{id}/status
│   ├── core/
│   │   ├── config.py          # Pydantic-settings config (env vars, .env file)
│   │   └── graph.py           # DFS cycle detection + Kahn's topological sort
│   ├── db/
│   │   ├── base.py            # Async engine, session factory, Base class
│   │   └── models.py          # DagDefinition, TaskDefinition, TaskRun ORM models
│   └── worker/
│       └── worker.py          # Standalone async worker with Redis BRPOP + fanout
├── alembic/                   # Database migrations
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   └── test_graph.py          # Unit tests for graph algorithms
├── .env.example               # Environment variable template
├── docker-compose.yml         # PostgreSQL 15 + Redis 7 services
└── requirements.txt           # Pinned dependencies
```

---

## Build Phases

✅ **Phase 1** -- Project Initialisation & Architecture (scaffolding, Docker Compose)
✅ **Phase 2** -- The State Machine (database schema & SQLAlchemy async models)
✅ **Phase 3** -- The Brain (graph algorithms: cycle detection & topological sort)
✅ **Phase 4** -- The Command Tent (FastAPI REST endpoints)
✅ **Phase 5** -- The Frontline Troops (distributed async workers)

---

## What's Working (v0.1 Foundation)

- **DAG Submission via REST API** -- Define DAGs and tasks through JSON payloads
- **Cycle Detection** -- DFS-based validation rejects invalid DAGs before they touch the database
- **Topological Sort** -- Kahn's Algorithm resolves execution order grouped into parallel tiers
- **Distributed Workers** -- Multiple async worker instances pull tasks from Redis concurrently via BRPOP
- **Dependency Fanout** -- Workers automatically enqueue downstream tasks once all parent tasks succeed
- **Real-Time Status** -- Query the execution state of a DAG and all its tasks at any point
- **Database Migrations** -- Alembic with async SQLAlchemy support, initial schema in place
- **Interactive API Docs** -- Auto-generated Swagger UI at `/docs`

---

## Roadmap

> Everything below represents the gap between the current v0.1 foundation and a truly complete, production-grade system.

### 🔴 Critical -- Must Fix

| Item | Description |
|------|-------------|
| **FAILED task state** | Workers do not mark tasks `FAILED` when an exception occurs. A crashed task hangs in `RUNNING` indefinitely. |
| **FAILED fanout propagation** | If a parent task fails, all downstream dependents must be marked `FAILED` automatically, not left in `PENDING`. |
| **`GET /dags` endpoint** | No endpoint to list all DAG definitions -- a basic omission. |
| **Per-run status filtering** | `GET /dags/{id}/status` returns all historical runs. Needs filtering by `dag_run_id` to inspect a specific execution. |

### 🟡 Important -- Should Do

| Item | Description |
|------|-------------|
| **API integration tests** | No tests for the REST layer. Need `httpx`-based tests for all three endpoints covering happy path and error cases. |
| **`pytest.ini` / `pyproject.toml`** | pytest-asyncio mode is not configured -- async tests may silently not execute correctly. |
| **Real command execution** | Workers simulate tasks with `asyncio.sleep()`. Real shell execution via `asyncio.subprocess` is the actual goal. |
| **`GET /dags` list endpoint** | Ability to paginate and filter all stored DAG definitions. |
| **DAG deletion endpoint** | `DELETE /dags/{dag_id}` with cascade cleanup of tasks and runs. |

### 🟢 Production Hardening

| Item | Description |
|------|-------------|
| **Authentication** | API has no auth layer. JWT-based authentication should protect all endpoints. |
| **Rate limiting** | No request throttling on the API. Required before any public deployment. |
| **Structured logging** | Replace `print`/basic logging with structured JSON logs (e.g. using `structlog`). |
| **Metrics & observability** | Instrument with Prometheus metrics -- queue depth, task duration, success/failure rates. |
| **Worker retry logic** | Failed tasks should be retried N times with exponential backoff before being marked permanently `FAILED`. |
| **Idempotent task claiming** | Add a database-level lock when a worker claims a task to prevent two workers processing the same task under high load. |

### 🚀 Deployment

| Item | Description |
|------|-------------|
| **Dockerise the application** | Add `Dockerfile` for the API server and worker so everything runs in containers, not just the infrastructure. |
| **Production `docker-compose.yml`** | A production compose override that includes the API and worker services alongside Postgres and Redis. |
| **VPS deployment** | Deploy to a DigitalOcean or Hetzner droplet. Target: public URL with live Swagger UI accessible. |
| **Environment secrets management** | Move secrets out of `.env` into proper secrets management (e.g. Docker secrets or a vault solution). |

### 💡 Algorithmic Improvements

| Item | Description |
|------|-------------|
| **Weighted task scheduling** | Allow tasks to declare an estimated duration. The scheduler could prioritise longer tasks first (critical path scheduling) to minimise total DAG execution time. |
| **Task timeout enforcement** | Workers should enforce a per-task maximum execution time and mark the task `FAILED` if exceeded. |
| **Priority queue** | Replace the simple Redis list with a sorted set to support task priority levels. |
| **Dead letter queue** | Tasks that fail repeatedly should be moved to a dead letter queue for manual inspection rather than being silently dropped. |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/dags` | Create a new DAG definition (validates for cycles) |
| `POST` | `/dags/{dag_id}/run` | Trigger a DAG execution |
| `GET` | `/dags/{dag_id}/status` | Real-time status of all task runs |
| `GET` | `/health` | Liveness probe |
| `GET` | `/docs` | Interactive Swagger UI |

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### 1. Clone and configure environment

```bash
git clone https://github.com/spiteman1/dag-engine.git
cd dag-engine
cp .env.example .env
```

### 2. Start infrastructure services

```bash
docker compose up -d
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the API server

```bash
uvicorn dag_engine.api.main:app --reload
```

### 6. Start one or more workers (in separate terminals)

```bash
WORKER_ID=worker-1 python -m dag_engine.worker.worker
WORKER_ID=worker-2 python -m dag_engine.worker.worker
```

### 7. Open the interactive API docs

Visit [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Example Usage

### Create a DAG

```bash
curl -X POST http://localhost:8000/dags \
  -H "Content-Type: application/json" \
  -d '{
    "name": "data_pipeline",
    "description": "Daily ETL pipeline",
    "tasks": [
      {"name": "extract",   "command": "python extract.py",   "dependencies": []},
      {"name": "transform", "command": "python transform.py", "dependencies": ["extract"]},
      {"name": "load",      "command": "python load.py",      "dependencies": ["transform"]}
    ]
  }'
```

### Trigger a run

```bash
curl -X POST http://localhost:8000/dags/{dag_id}/run
```

### Check status

```bash
curl http://localhost:8000/dags/{dag_id}/status
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Author

**Donell** -- Computer Science student at Aston University, Birmingham.
System QA Engineer Intern at Graphcore.
