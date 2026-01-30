"""DuckDB database connection and schema initialization."""

import logging
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

# Database path
DB_PATH: Path = settings.data_dir / "regatlas.duckdb"

# Connection singleton
_connection: Optional["duckdb.DuckDBPyConnection"] = None


def get_connection() -> "duckdb.DuckDBPyConnection":
    """Get a DuckDB connection, initializing if necessary."""
    global _connection
    if _connection is None:
        import duckdb

        _connection = duckdb.connect(str(DB_PATH))
    return _connection


def close_connection() -> None:
    """Close the global connection if open."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_db() -> None:
    """Initialize database schema."""
    conn = get_connection()

    # Documents table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id VARCHAR PRIMARY KEY,
            filename VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL,
            entity VARCHAR,
            business_unit VARCHAR,
            chunks_count INTEGER DEFAULT 0,
            requirements JSON,
            raw_extraction JSON,
            metadata JSON,
            content_hash VARCHAR,
            size_bytes INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Policies table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            path VARCHAR,
            summary TEXT,
            status VARCHAR DEFAULT 'active',
            version VARCHAR DEFAULT '1.0',
            owner VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # Audit log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            action VARCHAR NOT NULL,
            entity_type VARCHAR,
            entity_id VARCHAR,
            details JSON,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create sequence for audit_log id
    conn.execute("CREATE SEQUENCE IF NOT EXISTS audit_log_id_seq START 1")

    # Sources table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            source_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            url VARCHAR,
            type VARCHAR,
            description TEXT,
            last_crawled_at TIMESTAMP,
            status VARCHAR DEFAULT 'active',
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Webhooks table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhooks (
            webhook_id VARCHAR PRIMARY KEY,
            url VARCHAR NOT NULL,
            events JSON,
            secret VARCHAR,
            status VARCHAR DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")
