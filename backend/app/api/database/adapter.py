"""Compatibility import for the single Plan A SQLite persistence client.

New code imports :mod:`backend.app.database.client` directly.  This module
preserves the existing E-router import path while ensuring it has no separate
schema, connection, or DDL implementation.
"""

from backend.app.database.client import *  # noqa: F403
