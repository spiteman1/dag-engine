"""
api/main.py - FastAPI application entry point.

Instantiates the FastAPI app, registers routers, and adds middleware.
Run with: uvicorn dag_engine.api.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dag_engine.api.routes import dags

app = FastAPI(
    title="DAG Engine",
    description=(
        "A lightweight distributed DAG task execution engine. "
        "Submit DAG definitions, trigger runs, and monitor task status in real time."
    ),
    version="0.1.0",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc",     # ReDoc at /redoc
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
# Allows browsers to make requests to the API from any origin.
# Tighten this down in production by listing specific allowed origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(dags.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple liveness probe -- returns 200 if the API is running."""
    return {"status": "ok", "service": "dag-engine"}
