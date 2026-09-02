"""Shared column helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC. schema.md 3: every timestamp is stored in UTC and formatted in the browser."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
