import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.state import STARTED_AT, _all_jurisdictions
from backend.storage.repositories import DocumentRepository, AuditLogRepository
from backend.vector_store import VectorStore

logger = logging.getLogger(__name__)


class SystemService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        audit_repo: AuditLogRepository,
        vector_store: VectorStore,
        req_extractor: Any,
    ):
        self.doc_repo = doc_repo
        self.audit_repo = audit_repo
        self.vector_store = vector_store
        self.req_extractor = req_extractor

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        all_docs = self.doc_repo.list_all()
        requirements_count = sum(len(doc.get("requirements", [])) for doc in all_docs)

        return {
            "total_chunks": self.vector_store.get_document_count(),
            "total_documents": len(all_docs),
            "jurisdictions": _all_jurisdictions(),
            "llm_available": self.req_extractor.client is not None,
            "total_requirements": requirements_count,
            "total_audit_events": self.audit_repo.count(),
            "total_sources": 0,  # Placeholder as sources_db is not in repo yet
            "total_evidence": 0,  # Placeholder
            "started_at": STARTED_AT.isoformat(),
            "uptime_seconds": int(
                (datetime.now(timezone.utc) - STARTED_AT).total_seconds()
            ),
        }

    def get_entities(self) -> Dict[str, List[str]]:
        """List entities and business units found in data."""
        entities = set()
        business_units = set()
        all_docs = self.doc_repo.list_all()
        for doc in all_docs:
            if doc.get("entity"):
                entities.add(doc["entity"])
            if doc.get("business_unit"):
                business_units.add(doc["business_unit"])
        return {"entities": sorted(entities), "business_units": sorted(business_units)}

    def get_audit_log(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return audit log entries."""
        return self.audit_repo.filter_entries(
            entity_type=entity_type, entity_id=entity_id, action=action
        )
