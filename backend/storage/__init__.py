"""Storage module for DuckDB-based persistence."""

from .database import get_connection, init_db
from .repositories import DocumentRepository, PolicyRepository, AuditLogRepository

__all__ = [
    "get_connection",
    "init_db",
    "DocumentRepository",
    "PolicyRepository",
    "AuditLogRepository",
]
