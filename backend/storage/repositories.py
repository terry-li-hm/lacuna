"""Repository classes for DuckDB storage operations."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import get_connection

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for document operations."""

    def save(self, doc: Dict[str, Any]) -> None:
        """Save or update a document."""
        conn = get_connection()
        requirements = doc.get("requirements")
        if isinstance(requirements, (list, dict)):
            requirements = json.dumps(requirements)
        raw_extraction = doc.get("raw_extraction")
        if raw_extraction is not None:
            if isinstance(raw_extraction, dict):
                raw_extraction = json.dumps(raw_extraction)
            elif not isinstance(raw_extraction, str):
                raw_extraction = json.dumps(raw_extraction)
            elif not raw_extraction.strip().startswith(("{", "[")):
                # It's a plain string, wrap it in JSON
                raw_extraction = json.dumps({"message": raw_extraction})
        metadata = doc.get("metadata")
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)

        conn.execute(
            """
            INSERT OR REPLACE INTO documents
            (doc_id, filename, jurisdiction, entity, business_unit, chunks_count,
             requirements, raw_extraction, metadata, content_hash, size_bytes, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                doc["doc_id"],
                doc["filename"],
                doc["jurisdiction"],
                doc.get("entity"),
                doc.get("business_unit"),
                doc.get("chunks_count", 0),
                requirements,
                raw_extraction,
                metadata,
                doc.get("content_hash"),
                doc.get("size_bytes", 0),
                doc.get("uploaded_at", datetime.now(timezone.utc).isoformat()),
            ],
        )
        conn.commit()

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        conn = get_connection()
        result = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", [doc_id]
        ).fetchone()
        if result is None:
            return None
        return self._row_to_dict(result)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all documents, sorted by uploaded_at descending."""
        conn = get_connection()
        results = conn.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in results]

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        conn = get_connection()
        conn.execute("DELETE FROM documents WHERE doc_id = ?", [doc_id])
        conn.commit()
        return True

    def count(self) -> int:
        """Get total document count."""
        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        return result[0] if result else 0

    def get_all_jurisdictions(self) -> List[str]:
        """Get list of all jurisdictions."""
        conn = get_connection()
        results = conn.execute(
            "SELECT DISTINCT jurisdiction FROM documents WHERE jurisdiction IS NOT NULL"
        ).fetchall()
        return sorted([r[0] for r in results])

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        columns = [
            "doc_id",
            "filename",
            "jurisdiction",
            "entity",
            "business_unit",
            "chunks_count",
            "requirements",
            "raw_extraction",
            "metadata",
            "content_hash",
            "size_bytes",
            "uploaded_at",
        ]
        doc = dict(zip(columns, row))
        # Parse JSON fields
        for field in ["requirements", "raw_extraction", "metadata"]:
            value = doc.get(field)
            if isinstance(value, str):
                try:
                    doc[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass
        return doc


class PolicyRepository:
    """Repository for policy operations."""

    def save(self, policy: Dict[str, Any]) -> None:
        """Save or update a policy."""
        conn = get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO policies
            (policy_id, title, path, summary, content, status, version, owner, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                policy["policy_id"],
                policy["title"],
                policy.get("path"),
                policy.get("summary"),
                policy.get("content"),
                policy.get("status", "active"),
                policy.get("version", "1.0"),
                policy.get("owner"),
                policy.get("created_at", datetime.now(timezone.utc).isoformat()),
                policy.get("updated_at"),
            ],
        )
        conn.commit()

    def get(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Get a policy by ID."""
        conn = get_connection()
        result = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", [policy_id]
        ).fetchone()
        if result is None:
            return None
        return self._row_to_dict(result)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all policies, sorted by created_at descending."""
        conn = get_connection()
        results = conn.execute(
            "SELECT * FROM policies ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in results]

    def count(self) -> int:
        """Get total policy count."""
        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM policies").fetchone()
        return result[0] if result else 0

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        columns = [
            "policy_id",
            "title",
            "path",
            "summary",
            "content",
            "status",
            "version",
            "owner",
            "created_at",
            "updated_at",
        ]
        result = dict(zip(columns, row))
        # Handle case where content column may not exist in older rows
        if len(row) < len(columns):
            result = dict(zip(columns[:len(row)], row))
        return result


class AuditLogRepository:
    """Repository for audit log operations."""

    def append(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an entry to the audit log."""
        conn = get_connection()
        details_json = json.dumps(details) if details else None
        conn.execute(
            """
            INSERT INTO audit_log (id, action, entity_type, entity_id, details, timestamp)
            VALUES (nextval('audit_log_id_seq'), ?, ?, ?, ?, ?)
        """,
            [
                action,
                entity_type,
                entity_id,
                details_json,
                datetime.now(timezone.utc).isoformat(),
            ],
        )
        conn.commit()

    def list_all(self) -> List[Dict[str, Any]]:
        """List all audit log entries, sorted by timestamp descending."""
        conn = get_connection()
        results = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in results]

    def filter_entries(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter audit log entries."""
        conn = get_connection()
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        query += " ORDER BY timestamp DESC"

        results = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in results]

    def count(self) -> int:
        """Get total audit log count."""
        conn = get_connection()
        result = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        return result[0] if result else 0

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        columns = ["id", "action", "entity_type", "entity_id", "details", "timestamp"]
        entry = dict(zip(columns, row))
        if isinstance(entry.get("details"), str):
            try:
                entry["details"] = json.loads(entry["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        return entry


class ConfirmedRequirementRepository:
    """Repository for confirmed requirement list operations."""

    def save(
        self, doc_id: str, requirements: List[Dict[str, Any]], confirmed_by: str | None = None
    ) -> None:
        """Save or replace confirmed requirement list for a document."""
        conn = get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO confirmed_requirements
            (doc_id, confirmed_at, confirmed_by, requirements)
            VALUES (?, ?, ?, ?)
            """,
            [
                doc_id,
                datetime.now(timezone.utc).isoformat(),
                confirmed_by,
                json.dumps(requirements),
            ],
        )
        conn.commit()

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get confirmed requirement list by doc ID."""
        conn = get_connection()
        result = conn.execute(
            "SELECT * FROM confirmed_requirements WHERE doc_id = ?",
            [doc_id],
        ).fetchone()
        if result is None:
            return None
        return self._row_to_dict(result)

    def delete(self, doc_id: str) -> None:
        """Delete confirmed requirement list by doc ID."""
        conn = get_connection()
        conn.execute("DELETE FROM confirmed_requirements WHERE doc_id = ?", [doc_id])
        conn.commit()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        columns = ["doc_id", "confirmed_at", "confirmed_by", "requirements"]
        item = dict(zip(columns, row))
        value = item.get("requirements")
        if isinstance(value, str):
            try:
                item["requirements"] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                item["requirements"] = []
        elif value is None:
            item["requirements"] = []
        return item
