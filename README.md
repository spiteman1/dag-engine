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

- [x] **Phase 1** -- Project Initialisation & Architecture (scaffolding, Docker Compose)
- [x] **Phase 2** -- The State Machine (database schema & SQLAlchemy async models)
- [x] **Phase 3** -- The Brain (graph algorithms: cycle detection & topological sort)
- [x] **Phase 4** -- The Command Tent (FastAPI REST endpoints)
- [x] **Phase 5** -- The Frontline Troops (distributed async workers)

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

## What's Not Done Yet

> This section is intentionally honest. The foundation is sound but the following gaps need to be addressed before this project could be considered complete or production-ready.

### Functional Gaps

| Gap | Description |
|-----|-------------|
| **FAILED task handling** | Workers do not currently mark tasks as `FAILED` when an exception occurs. A crashed task hangs in `RUNNING` indefinitely. |
| **FAILED fanout** | If a parent task fails, downstream dependent tasks should be marked `FAILED` automatically rather than left in `PENDING`. |
| **List DAGs endpoint** | No `GET /dags` endpoint exists to retrieve all DAG definitions. |
| **Per-run status filtering** | `GET /dags/{id}/status` returns all historical runs for a DAG. It should support filtering by `dag_run_id` to inspect a single execution. |

### Quality & Hardening Gaps

| Gap | Description |
|-----|-------------|
| **API integration tests** | `tests/test_graph.py` covers the graph algorithms but there are no integration tests for the REST endpoints using `httpx`. |
| **pytest configuration** | No `pytest.ini` or `pyproject.toml` to configure pytest-asyncio mode -- async tests may not run correctly without this. |
| **Real command execution** | Workers currently simulate execution with `asyncio.sleep()`. Real shell command execution via `asyncio.subprocess` is not implemented. |
| **Authentication** | The API has no authentication or authorisation layer. All endpoints are publicly accessible. |
| **Observability** | No structured logging, metrics, or distributed tracing is in place. |

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
