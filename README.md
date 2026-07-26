# DAG Engine

A custom Directed Acyclic Graph (DAG) task execution engine built from scratch. Think of it as a lightweight Apache Airflow -- accept DAG definitions via a REST API, resolve task dependencies using topological sorting, and distribute workloads across multiple asynchronous Python workers using a message broker.

**This project is a hands-on learning build. Every component is written from scratch to understand distributed systems at a fundamental level.**

## Architecture Overview

```
                    ┌─────────────────┐
                    │   FastAPI REST   │
                    │      API         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │  Graph   │  │ PostgreSQL│  │    Redis      │
        │  Engine  │  │   (State) │  │ (Task Queue)  │
        │ (Topo    │  │           │  │               │
        │  Sort +  │  │           │  │               │
        │  Cycle   │  │           │  │               │
        │  Detect) │  │           │  │               │
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

## Tech Stack

| Component       | Technology                      |
| --------------- | ------------------------------- |
| Backend API     | FastAPI (Python 3.11+)          |
| Database        | PostgreSQL 15                   |
| ORM             | SQLAlchemy (Async)              |
| Migrations      | Alembic                         |
| Message Broker  | Redis 7                         |
| Workers         | Custom Python AsyncIO           |
| Testing         | pytest                          |
| Containerisation| Docker & Docker Compose         |

## Project Structure

```
/dag_engine
├── api/            # FastAPI routes and dependency injection
├── core/           # Topological sort, cycle detection, configuration
├── db/             # SQLAlchemy models, session management, Alembic migrations
├── worker/         # Standalone async worker scripts, Redis polling logic
├── tests/          # pytest suite
├── docker-compose.yml
└── requirements.txt
```

## Build Phases

- [ ] **Phase 1** -- Project Initialisation & Architecture (scaffolding, Docker Compose)
- [ ] **Phase 2** -- The State Machine (database schema & SQLAlchemy async models)
- [ ] **Phase 3** -- The Brain (graph algorithms: cycle detection & topological sort)
- [ ] **Phase 4** -- The Command Tent (FastAPI REST endpoints)
- [ ] **Phase 5** -- The Frontline Troops (distributed async workers)

## Key Features

- **DAG Submission via REST API** -- Define DAGs and their tasks through JSON payloads
- **Cycle Detection** -- DFS-based validation ensures no infinite loops exist before saving
- **Topological Sort** -- Kahn's Algorithm resolves execution order grouped by parallel tiers
- **Distributed Workers** -- Multiple async workers pull tasks from Redis and execute concurrently
- **Dependency Fanout** -- Workers automatically enqueue downstream tasks when all parents succeed
- **Real-Time Status** -- Query the execution state of any DAG and its tasks at any time

## Getting Started

> Coming soon -- Phase 1 will add Docker Compose and dependency setup instructions.

## Author

**Donell** -- Computer Science student at Aston University, Birmingham.
