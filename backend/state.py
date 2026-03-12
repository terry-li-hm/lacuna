"""Shared state and utilities for Meridian backend."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from backend.config import settings
from backend.storage import (
    init_db,
    DocumentRepository,
    PolicyRepository,
    AuditLogRepository,
    ConfirmedRequirementRepository,
)

logger = logging.getLogger(__name__)

# Paths
DOCUMENTS_DB_PATH = settings.data_dir / "documents_db.json"
AUDIT_LOG_PATH = settings.data_dir / "audit_log.json"
SOURCES_DB_PATH = settings.data_dir / "sources_db.json"
EVIDENCE_DB_PATH = settings.data_dir / "evidence_db.json"
POLICIES_DB_PATH = settings.data_dir / "policies_db.json"
WEBHOOKS_DB_PATH = settings.data_dir / "webhooks_db.json"
CHANGES_DB_PATH = settings.data_dir / "changes_db.json"
STARTED_AT = datetime.now(timezone.utc)
ALLOWED_REQ_STATUS = {"new", "reviewed", "action_required"}


def load_documents_db(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load persisted document metadata from disk."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load documents DB from {path}: {e}")
        return {}


def save_documents_db(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Persist document metadata to disk atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def load_json_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load a JSON object (dict) from disk."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON dict from {path}: {e}")
        return {}


def save_json_dict(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Persist JSON dict atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON list from disk."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Could not load JSON list from {path}: {e}")
        return []


def save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    """Persist JSON list atomically."""
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def _paginate(
    items: List[Dict[str, Any]], limit: int | None, offset: int | None
) -> List[Dict[str, Any]]:
    if limit is None or limit <= 0:
        return items[offset or 0 :]
    return items[offset or 0 : (offset or 0) + limit]


def _sort_by_iso(items: Iterable[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    def _key(item: Dict[str, Any]) -> datetime:
        value = item.get(field)
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(list(items), key=_key, reverse=True)


def _validate_date_str(value: str | None, field: str) -> None:
    if not value:
        return
    try:
        datetime.fromisoformat(value)
    except ValueError:
        try:
            from datetime import date

            date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid {field} date format"
            ) from exc


def _normalize_severity(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_mandatory(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower()


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_choice(value: str | None, allowed: set[str], field: str) -> str | None:
    if value is None:
        return None
    normalized = value.lower()
    if normalized not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=400, detail=f"Invalid {field}. Allowed: {allowed_list}"
        )
    return normalized


def _validate_url(value: str) -> None:
    if not (value.startswith("http://") or value.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme — only http(s) allowed")


def _count_by_field(items: Iterable[Dict[str, Any]], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = item.get(field) or "Unknown"
        if isinstance(value, str):
            key = value.strip() or "Unknown"
        else:
            key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0].lower()))


def _summarize_policy(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return " ".join(lines[1:4])[:240] if len(lines) > 1 else ""


# Global state - will be initialized in main.py
documents_db: Dict[str, Dict[str, Any]] = {}
audit_log: List[Dict[str, Any]] = []
sources_db: Dict[str, Dict[str, Any]] = {}
evidence_db: List[Dict[str, Any]] = []
policies_db: Dict[str, Dict[str, Any]] = {}
webhooks_db: Dict[str, Dict[str, Any]] = {}
changes_db: Dict[str, Dict[str, Any]] = {}

# Repository instances
_document_repo: Optional[DocumentRepository] = None
_policy_repo: Optional[PolicyRepository] = None
_audit_log_repo: Optional[AuditLogRepository] = None
_confirm_repo: Optional[ConfirmedRequirementRepository] = None

# Service instances
_llm_service: Optional[Any] = None
_document_service: Optional[Any] = None
_requirement_service: Optional[Any] = None
_gap_analysis_service: Optional[Any] = None
_policy_service: Optional[Any] = None
_system_service: Optional[Any] = None
_query_service: Optional[Any] = None
_integration_service: Optional[Any] = None
_evidence_service: Optional[Any] = None
_change_service: Optional[Any] = None
_scan_service: Optional[Any] = None
_decompose_service: Optional[Any] = None
_confirm_service: Optional[Any] = None
_synthesis_service: Optional[Any] = None

# Components - will be initialized in main.py
doc_processor = None
req_extractor = None
vector_store = None
llm_api_key = None


def get_document_repo() -> DocumentRepository:
    """Get or create the document repository singleton."""
    global _document_repo
    if _document_repo is None:
        _document_repo = DocumentRepository()
    return _document_repo


def get_policy_repo() -> PolicyRepository:
    """Get or create the policy repository singleton."""
    global _policy_repo
    if _policy_repo is None:
        _policy_repo = PolicyRepository()
    return _policy_repo


def get_audit_log_repo() -> AuditLogRepository:
    """Get or create the audit log repository singleton."""
    global _audit_log_repo
    if _audit_log_repo is None:
        _audit_log_repo = AuditLogRepository()
    return _audit_log_repo


def get_confirm_repo() -> ConfirmedRequirementRepository:
    """Get or create the confirmed requirement repository singleton."""
    global _confirm_repo
    if _confirm_repo is None:
        _confirm_repo = ConfirmedRequirementRepository()
    return _confirm_repo


def get_llm_service():
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        from backend.services.llm_service import LLMService

        _llm_service = LLMService(extractor=req_extractor)
    return _llm_service


def get_document_service():
    """Get or create the document service singleton."""
    global _document_service
    if _document_service is None:
        from backend.services.document_service import DocumentService

        _document_service = DocumentService(
            doc_repo=get_document_repo(),
            vector_store=vector_store,
            processor=doc_processor,
            llm_service=get_llm_service(),
        )
    return _document_service


def get_requirement_service():
    """Get or create the requirement service singleton."""
    global _requirement_service
    if _requirement_service is None:
        from backend.services.requirement_service import RequirementService

        _requirement_service = RequirementService(
            doc_repo=get_document_repo(), audit_repo=get_audit_log_repo()
        )
    return _requirement_service


def get_gap_analysis_service():
    """Get or create the gap analysis service singleton."""
    global _gap_analysis_service
    if _gap_analysis_service is None:
        from backend.services.gap_analysis_service import GapAnalysisService

        _gap_analysis_service = GapAnalysisService(
            doc_repo=get_document_repo(),
            policy_repo=get_policy_repo(),
            vector_store=vector_store,
            llm_service=get_llm_service(),
        )
    return _gap_analysis_service


def get_policy_service():
    """Get or create the policy service singleton."""
    global _policy_service
    if _policy_service is None:
        from backend.services.policy_service import PolicyService

        _policy_service = PolicyService(policy_repo=get_policy_repo())
    return _policy_service


def get_system_service():
    """Get or create the system service singleton."""
    global _system_service
    if _system_service is None:
        from backend.services.system_service import SystemService

        _system_service = SystemService(
            doc_repo=get_document_repo(),
            audit_repo=get_audit_log_repo(),
            vector_store=vector_store,
            req_extractor=req_extractor,
        )
    return _system_service


def get_query_service():
    """Get or create the query service singleton."""
    global _query_service
    if _query_service is None:
        from backend.services.query_service import QueryService

        _query_service = QueryService(
            vector_store=vector_store, req_extractor=req_extractor
        )
    return _query_service


def get_integration_service():
    """Get or create the integration service singleton."""
    global _integration_service
    if _integration_service is None:
        from backend.services.integration_service import IntegrationService

        _integration_service = IntegrationService(
            sources_db=sources_db,
            webhooks_db=webhooks_db,
            audit_repo=get_audit_log_repo(),
        )
    return _integration_service


def get_evidence_service():
    """Get or create the evidence service singleton."""
    global _evidence_service
    if _evidence_service is None:
        from backend.services.evidence_service import EvidenceService

        _evidence_service = EvidenceService(
            evidence_db=evidence_db, audit_repo=get_audit_log_repo()
        )
    return _evidence_service


def get_change_service():
    """Get or create the change service singleton."""
    global _change_service
    if _change_service is None:
        from backend.services.change_service import ChangeService

        _change_service = ChangeService(
            changes_db=changes_db, audit_repo=get_audit_log_repo()
        )
    return _change_service


def get_scan_service():
    """Get or create the scan service singleton."""
    global _scan_service
    if _scan_service is None:
        from backend.services.scan_service import ScanService

        _scan_service = ScanService(
            sources_db=sources_db, change_service=get_change_service()
        )
    return _scan_service


def get_decompose_service():
    """Get or create the decompose service singleton."""
    global _decompose_service
    if _decompose_service is None:
        from backend.services.decompose_service import DecomposeService

        _decompose_service = DecomposeService(
            doc_repo=get_document_repo(),
            req_extractor=req_extractor,
        )
    return _decompose_service


def get_confirm_service():
    """Get or create the confirm service singleton."""
    global _confirm_service
    if _confirm_service is None:
        from backend.services.confirm_service import ConfirmService

        _confirm_service = ConfirmService(
            doc_repo=get_document_repo(),
            confirm_repo=get_confirm_repo(),
        )
    return _confirm_service


def get_synthesis_service():
    """Get or create the synthesis service singleton."""
    global _synthesis_service
    if _synthesis_service is None:
        from backend.services.synthesis_service import SynthesisService

        _synthesis_service = SynthesisService(
            gap_analysis_service=get_gap_analysis_service(),
        )
    return _synthesis_service


def init_state():
    """Initialize global state from disk."""
    global documents_db, audit_log, sources_db, evidence_db, policies_db, webhooks_db, changes_db
    # Initialize DuckDB first
    init_db()
    # Load JSON as fallback / legacy support
    documents_db = load_documents_db(DOCUMENTS_DB_PATH)
    audit_log = load_json_list(AUDIT_LOG_PATH)
    sources_db = load_json_dict(SOURCES_DB_PATH)
    evidence_db = load_json_list(EVIDENCE_DB_PATH)
    policies_db = load_json_dict(POLICIES_DB_PATH)
    webhooks_db = load_json_dict(WEBHOOKS_DB_PATH)
    changes_db = load_json_dict(CHANGES_DB_PATH)


def init_components():
    """Initialize components."""
    global doc_processor, req_extractor, vector_store, llm_api_key
    from backend.document_processor import DocumentProcessor
    from backend.requirement_extractor import RequirementExtractor
    from backend.vector_store import VectorStore

    doc_processor = DocumentProcessor()
    llm_api_key = settings.openai_api_key or settings.openrouter_api_key
    req_extractor = RequirementExtractor(
        api_key=None if settings.no_llm else llm_api_key,
        model=settings.llm_model,
        gap_analysis_model=settings.gap_analysis_model,
        base_url=settings.openai_base_url,
    )
    vector_store = VectorStore(settings.chroma_persist_dir)


def _all_jurisdictions() -> List[str]:
    return get_document_repo().get_all_jurisdictions()


def _normalize_requirements(
    requirements: List[Dict[str, Any]],
    doc_id: str,
    jurisdiction: str,
    filename: str,
    entity: str | None = None,
    business_unit: str | None = None,
) -> List[Dict[str, Any]]:
    import uuid

    normalized = []
    for req in requirements:
        normalized.append(
            {
                "requirement_id": str(uuid.uuid4()),
                "jurisdiction": jurisdiction,
                "doc_id": doc_id,
                "filename": filename,
                "requirement_type": req.get("requirement_type") or "Unknown",
                "description": req.get("description"),
                "details": req.get("details"),
                "mandatory": req.get("mandatory") or "Unknown",
                "confidence": req.get("confidence", "Medium"),
                "source_snippet": req.get("source_snippet"),
                "entity": entity,
                "business_unit": business_unit,
                "status": "new",
                "reviewer": None,
                "review_notes": None,
                "tags": [],
                "controls": [],
                "policy_refs": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "evidence": {},
            }
        )
    return normalized


def _attach_evidence(requirements: List[Dict[str, Any]], doc_id: str) -> None:
    for req in requirements:
        query_text = " ".join(
            [
                req.get("requirement_type") or "",
                req.get("description") or "",
                req.get("details") or "",
            ]
        ).strip()
        if not query_text:
            continue
        results = vector_store.query(
            query_text=query_text, n_results=1, filters={"doc_id": doc_id}
        )
        if results:
            match = results[0]
            req["evidence"] = {
                "chunk_id": match.get("id"),
                "text": match.get("document"),
                "metadata": match.get("metadata"),
            }


def _gather_requirements() -> List[Dict[str, Any]]:
    import uuid

    requirements = []
    updated = False
    for doc_id, doc in documents_db.items():
        reqs = doc.get("requirements", [])
        if isinstance(reqs, dict) and reqs.get("requirements"):
            raw_extraction = reqs.get("raw_extraction")
            reqs = _normalize_requirements(
                reqs.get("requirements", []),
                doc_id=doc.get("doc_id") or doc_id,
                jurisdiction=doc.get("jurisdiction") or "Unknown",
                filename=doc.get("filename") or "Unknown",
                entity=doc.get("entity"),
                business_unit=doc.get("business_unit"),
            )
            _attach_evidence(reqs, doc.get("doc_id") or doc_id)
            doc["requirements"] = reqs
            doc["raw_extraction"] = doc.get("raw_extraction") or raw_extraction
            updated = True
        elif isinstance(reqs, list) and reqs and "requirement_id" not in reqs[0]:
            reqs = _normalize_requirements(
                reqs,
                doc_id=doc.get("doc_id") or doc_id,
                jurisdiction=doc.get("jurisdiction") or "Unknown",
                filename=doc.get("filename") or "Unknown",
                entity=doc.get("entity"),
                business_unit=doc.get("business_unit"),
            )
            _attach_evidence(reqs, doc.get("doc_id") or doc_id)
            doc["requirements"] = reqs
            updated = True

        if isinstance(doc.get("requirements"), list):
            requirements.extend(doc.get("requirements", []))

    if updated:
        save_documents_db(DOCUMENTS_DB_PATH, documents_db)
    return requirements


def _filter_requirements(
    requirements: List[Dict[str, Any]],
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    requirement_type: str | None = None,
    mandatory: str | None = None,
    status: str | None = None,
    doc_id: str | None = None,
    q: str | None = None,
) -> List[Dict[str, Any]]:
    filtered = []
    mandatory_norm = _normalize_mandatory(mandatory)
    status_norm = _normalize_status(status)
    for req in requirements:
        if jurisdiction and req.get("jurisdiction") != jurisdiction:
            continue
        if entity and req.get("entity") != entity:
            continue
        if business_unit and req.get("business_unit") != business_unit:
            continue
        if requirement_type and req.get("requirement_type") != requirement_type:
            continue
        if mandatory_norm and (req.get("mandatory") or "").lower() != mandatory_norm:
            continue
        if status_norm and (req.get("status") or "").lower() != status_norm:
            continue
        if doc_id and req.get("doc_id") != doc_id:
            continue
        if q:
            haystack = " ".join(
                [
                    req.get("requirement_type") or "",
                    req.get("description") or "",
                    req.get("details") or "",
                    req.get("source_snippet") or "",
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        filtered.append(req)
    return filtered


def _extract_requirements_from_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    reqs = doc.get("requirements", [])
    if isinstance(reqs, list):
        return reqs
    if isinstance(reqs, dict):
        return reqs.get("requirements", [])
    return []


def _ensure_policy_seeded() -> None:
    if policies_db:
        return
    policy_dir = settings.data_dir / "policies"
    if not policy_dir.exists():
        return
    for path in policy_dir.glob("*.md"):
        policy_id = path.stem
        content = path.read_text(encoding="utf-8")
        title = (
            content.splitlines()[0].replace("#", "").strip() if content else policy_id
        )
        policy = {
            "policy_id": policy_id,
            "title": title,
            "path": str(path),
            "summary": _summarize_policy(content),
            "status": "active",
            "version": "1.0",
            "owner": "Compliance",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        policies_db[policy_id] = policy
        # Also save to DuckDB
        try:
            repo = get_policy_repo()
            repo.save(policy)
        except Exception as e:
            logger.warning(f"Failed to save policy to DuckDB: {e}")
    save_json_dict(POLICIES_DB_PATH, policies_db)


def _dispatch_webhooks(event: str, payload: Dict[str, Any]) -> None:
    import urllib.request

    for webhook in webhooks_db.values():
        if event not in webhook.get("events", []):
            continue
        url = webhook.get("url")
        if not url:
            continue
        body = json.dumps({"event": event, "payload": payload}).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=5):
                pass
        except Exception as e:
            logger.warning(f"Webhook dispatch failed to {url}: {e}")


def _append_audit_log(
    action: str, entity_type: str, entity_id: str, details: Dict[str, Any] | None = None
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
    }
    # Save to JSON for fallback
    audit_log.append(entry)
    save_json_list(AUDIT_LOG_PATH, audit_log)
    # Also save to DuckDB
    try:
        repo = get_audit_log_repo()
        repo.append(action, entity_type, entity_id, details)
    except Exception as e:
        logger.warning(f"Failed to append to DuckDB audit log: {e}")
