"""Migration script to migrate JSON data to DuckDB."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from backend.config import settings
from .database import init_db, get_connection
from .repositories import DocumentRepository, PolicyRepository, AuditLogRepository

logger = logging.getLogger(__name__)


def load_json_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load a JSON object (dict) from disk."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON dict from {path}: {e}")
        return {}


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON list from disk."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON list from {path}: {e}")
        return []


def migrate_json_to_duckdb() -> None:
    """Migrate all JSON data to DuckDB."""
    logger.info("Starting migration from JSON to DuckDB...")

    # Initialize database
    init_db()

    data_dir = settings.data_dir

    # Migrate documents
    docs_file = data_dir / "documents_db.json"
    if docs_file.exists():
        logger.info(f"Migrating documents from {docs_file}")
        docs = load_json_dict(docs_file)
        doc_repo = DocumentRepository()
        for doc_id, doc in docs.items():
            if isinstance(doc, dict):
                # Ensure doc_id is set
                doc["doc_id"] = doc.get("doc_id") or doc_id
                doc_repo.save(doc)
                logger.debug(f"Migrated document: {doc_id}")
        logger.info(f"Migrated {len(docs)} documents")

        # Rename old file to backup
        backup_path = docs_file.with_suffix(".json.bak")
        docs_file.rename(backup_path)
        logger.info(f"Renamed {docs_file.name} to {backup_path.name}")
    else:
        logger.info("No documents_db.json found to migrate")

    # Migrate policies
    policies_file = data_dir / "policies_db.json"
    if policies_file.exists():
        logger.info(f"Migrating policies from {policies_file}")
        policies = load_json_dict(policies_file)
        policy_repo = PolicyRepository()
        for policy_id, policy in policies.items():
            if isinstance(policy, dict):
                # Ensure policy_id is set
                policy["policy_id"] = policy.get("policy_id") or policy_id
                policy_repo.save(policy)
                logger.debug(f"Migrated policy: {policy_id}")
        logger.info(f"Migrated {len(policies)} policies")

        # Rename old file to backup
        backup_path = policies_file.with_suffix(".json.bak")
        policies_file.rename(backup_path)
        logger.info(f"Renamed {policies_file.name} to {backup_path.name}")
    else:
        logger.info("No policies_db.json found to migrate")

    # Migrate audit log
    audit_file = data_dir / "audit_log.json"
    if audit_file.exists():
        logger.info(f"Migrating audit log from {audit_file}")
        audit_entries = load_json_list(audit_file)
        conn = get_connection()
        for entry in audit_entries:
            if isinstance(entry, dict):
                conn.execute(
                    """
                    INSERT INTO audit_log (id, action, entity_type, entity_id, details, timestamp)
                    VALUES (nextval('audit_log_id_seq'), ?, ?, ?, ?, ?)
                """,
                    [
                        entry.get("action"),
                        entry.get("entity_type"),
                        entry.get("entity_id"),
                        json.dumps(entry.get("details"))
                        if entry.get("details")
                        else None,
                        entry.get("timestamp"),
                    ],
                )
        conn.commit()
        logger.info(f"Migrated {len(audit_entries)} audit log entries")

        # Rename old file to backup
        backup_path = audit_file.with_suffix(".json.bak")
        audit_file.rename(backup_path)
        logger.info(f"Renamed {audit_file.name} to {backup_path.name}")
    else:
        logger.info("No audit_log.json found to migrate")

    logger.info("Migration completed successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_json_to_duckdb()
