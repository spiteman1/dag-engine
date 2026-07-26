"""
Database Layer - SQLAlchemy async models, session management, and Alembic migrations.

This package owns all database concerns: table definitions (models),
the async session factory, and migration scripts. The API and worker
layers interact with the database exclusively through this package.
"""
