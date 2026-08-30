"""Persistent database layer owned by Plan A."""

from backend.app.database.client import get_db, init_db

__all__ = ["get_db", "init_db"]
