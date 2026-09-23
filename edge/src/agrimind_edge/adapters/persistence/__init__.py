"""Local persistence adapters."""

from agrimind_edge.adapters.persistence.sqlite import SqliteEventOutboxStore

__all__ = ["SqliteEventOutboxStore"]
