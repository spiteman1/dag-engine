# DAG Engine

> **Status: Active Development (Phase A & B Complete, Phase C Underway)**

A custom Directed Acyclic Graph (DAG) task execution engine built from scratch in Python. Conceptually similar to a lightweight Apache Airflow: DAG definitions are submitted via a REST API, dependencies are resolved using graph algorithms, and workloads are distributed across multiple asynchronous workers via a Redis message broker.

**This is a learning-driven systems engineering project. Every component is written from scratch to deeply understand how distributed task orchestration works at a fundamental level. Phase A (critical runtime and ordering fixes) and Phase B (concurrency safety and data integrity) are complete, with Phase C (fault recovery, DagRun entity, and worker heartbeats) actively underway.**

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
        │ DFS Cycle│  │  Async   │  │  Heartbeats   │
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
| Testing          | pytest & pytest-asyncio       |
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
│   │   └── models.py          # DagDefinition, DagRun, TaskDefinition, TaskRun models
│   └── worker/
│       └── worker.py          # Standalone async worker with Redis BRPOP + fanout + heartbeats
├── alembic/                   # Database migrations
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_dagrun_and_error_columns.py
├── tests/
│   └── test_graph.py          # Unit tests for graph algorithms
├── .env.example               # Environment variable template
├── docker-compose.yml         # PostgreSQL 15 + Redis 7 services
├── pyproject.toml             # Project packaging, dependencies, and pytest configuration
└── requirements.txt           # Thin wrapper pointing to pyproject.toml
```

---

## Master Implementation Phases

- [x] **Phase A: Core Reliability & Runtime Fixes**
  - Project packaging and pytest-asyncio integration (`pyproject.toml`)
  - Cross-platform Windows signal handling with graceful shutdown
  - Transaction ordering fix (PostgreSQL commit before Redis `lpush`)
  - Dynamic Alembic database URL injection from application settings
  - Single-pass in-degree and dependency parsing for topological sort
- [x] **Phase B: Concurrency Safety & Data Integrity**
  - [x] Atomic task claiming using row-level pessimistic locks (`SELECT ... FOR UPDATE SKIP LOCKED`)
  - [x] Atomic downstream fanout with serialized row locks (`SELECT ... FOR UPDATE`)
  - [x] Compound unique constraint on `(dag_id, name)` to prevent ambiguous runtime task matching
  - [x] Graph algorithm dependency name validation to reject dangling references and typos at submission
- [ ] **Phase C: Fault Recovery & Lifecycle Management (In Progress)**
  - [x] Try/except execution wrapping with durable `FAILED` state persistence
  - [x] Breadth-first search (BFS) failure cascade across downstream dependent tasks
  - [x] `DagRun` database entity + `error_message` column + Alembic migration 002
  - [x] Worker heartbeat loop with configurable interval and TTL via Redis `SETEX`
  - [ ] Standalone Reaper process for zombie task detection and cleanup (`reaper.py`)
  - [ ] Worker retry logic with exponential backoff
- [ ] **Phase D: Production Hardening & Full API** (CRUD endpoints, subprocess execution, lifespan pools)
- [ ] **Phase E: Benchmarking & Load Testing** (Locust test suite, high concurrency validation)

---

## What's Working (v0.1 Foundation + Phase A, B, & C Progress)

- **DAG Submission via REST API**: Define DAGs and tasks through JSON payloads
- **Dangling Dependency Validation**: Rejects invalid DAGs referencing non-existent task names at submission
- **Cycle Detection**: DFS-based validation rejects circular dependencies before touching the database
- **Topological Sort**: Kahn's Algorithm resolves execution order grouped into parallel tiers
- **Distributed Workers**: Multiple async worker instances pull tasks from Redis concurrently via BRPOP
- **Atomic Task Claiming**: PostgreSQL row-level pessimistic locks (`FOR UPDATE SKIP LOCKED`) prevent duplicate execution across worker nodes
- **Atomic Dependency Fanout**: Serialized row-level locks prevent duplicate enqueues during diamond dependency completions
- **Failure Resilience**: Durable `FAILED` status commits prevent tasks from getting stuck in `RUNNING` on exception
- **BFS Downstream Failure Cascade**: When a parent task fails, all reachable downstream dependents transition to `FAILED`
- **First-Class DagRun Entity**: Dedicated table tracks run-level status, start/finish times, and failure diagnostics
- **Worker Heartbeats**: Background async tasks refresh expiring liveness keys in Redis with clean shutdown cleanup
- **Real-Time Status**: Query the execution state of a DAG and all its tasks at any point
- **Database Migrations**: Alembic with dynamic settings and async SQLAlchemy support
- **Interactive API Docs**: Auto-generated Swagger UI at `/docs`

---

## Roadmap

> Everything below represents the gap between the current foundation and a truly complete, production-grade system.

### 🔴 Critical (In Progress / Up Next)

| Item | Status | Description |
|------|--------|-------------|
| **Pessimistic task claiming** | Done | Row-level locking via `SELECT ... FOR UPDATE SKIP LOCKED` prevents race conditions between workers. |
| **Atomic downstream fanout** | Done | Serialized row-level locks prevent duplicate enqueues during diamond dependency completions. |
| **Unique task name constraint** | Done | Compound unique constraint on `(dag_id, name)` prevents ambiguous dependency resolution. |
| **Dependency name validation** | Done | Validates dependency references exist in DAG definition before persisting. |
| **FAILED task state** | Done | Workers catch exceptions and commit durable `FAILED` states to prevent zombie runs. |
| **BFS failure cascade** | Done | Downstream dependents transition to `FAILED` automatically when a parent fails. |
| **`DagRun` entity & run status** | Done | Dedicated model and migration tracking run lifecycle and task error messages. |
| **Worker heartbeat loop** | Done | Periodic Redis `SETEX` pings signal worker health with automatic TTL expiration. |
| **Zombie Reaper process** | Up Next | Standalone script recovering stalled tasks when worker heartbeats expire. |
| **Worker retry logic** | Up Next | Exponential backoff for transient task execution failures. |

### 🟡 Important

| Item | Description |
|------|-------------|
| **`GET /dags` list & CRUD** | List all DAG definitions with pagination, get single DAG, and delete DAG with cascade. |
| **Real command execution** | Workers execute shell commands via `asyncio.subprocess` with stdout/stderr capture. |
| **API integration tests** | Automated `httpx`-based tests for all REST endpoints covering happy path and error cases. |
| **Connection pooling** | Shared Redis connection pool across FastAPI request lifespans. |

### 🟢 Production Hardening

| Item | Description |
|------|-------------|
| **Authentication** | API has no auth layer. JWT-based authentication should protect all endpoints. |
| **Rate limiting** | No request throttling on the API. Required before any public deployment. |
| **Structured logging** | Replace `print`/basic logging with structured JSON logs (e.g. using `structlog`). |
| **Metrics & observability** | Instrument with Prometheus metrics: queue depth, task duration, success/failure rates. |
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
pip install -e ".[dev]"
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

**Donell** - Computer Science student at Aston University, Birmingham.
System QA Engineer Intern at Graphcore.
