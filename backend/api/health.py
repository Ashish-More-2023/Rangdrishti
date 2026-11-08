"""Health-check logic, kept out of the view so it can be tested and reused."""
from datetime import datetime, timezone

from django.conf import settings
from django.db import DatabaseError, connection


def database_is_available() -> bool:
    try:
        connection.ensure_connection()
    except DatabaseError:
        return False
    return True


def build_health_report(database_ok: bool) -> dict:
    return {
        "service": "rangdrishti-api",
        "version": settings.RANGDRISHTI_VERSION,
        "database": "ok" if database_ok else "unavailable",
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
