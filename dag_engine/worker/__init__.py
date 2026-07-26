"""
Worker Layer - Standalone async worker scripts and Redis polling logic.

Workers run as separate processes from the API server. They continuously
poll the Redis task queue, claim tasks, execute them, and handle
downstream dependency resolution. This separation allows horizontal
scaling -- spin up as many worker instances as needed.
"""
