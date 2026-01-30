"""Integration service for sources and webhooks."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from backend.config import settings

logger = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, sources_db, webhooks_db, audit_repo):
        self.sources_db = sources_db
        self.webhooks_db = webhooks_db
        self.audit_repo = audit_repo

    def add_source(
        self,
        name: str,
        url: str,
        jurisdiction: str,
        entity: str,
        business_unit: str,
        default_severity: str = "medium",
    ) -> Dict[str, Any]:
        from backend.state import (
            _validate_url,
            _normalize_text,
            save_json_dict,
            SOURCES_DB_PATH,
        )

        _validate_url(url)
        source_id = str(uuid.uuid4())
        source = {
            "source_id": source_id,
            "name": name,
            "url": url,
            "jurisdiction": jurisdiction,
            "entity": _normalize_text(entity),
            "business_unit": _normalize_text(business_unit),
            "default_severity": default_severity or "medium",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sources_db[source_id] = source
        save_json_dict(SOURCES_DB_PATH, self.sources_db)
        self.audit_repo.append(
            action="source_added",
            entity_type="source",
            entity_id=source_id,
            details={"name": name},
        )
        return source

    def list_sources(
        self,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        from backend.state import _sort_by_iso, _paginate

        sources = _sort_by_iso(list(self.sources_db.values()), "created_at")
        if q:
            q_lower = q.lower()
            sources = [
                s
                for s in sources
                if q_lower
                in f"{s.get('name', '')} {s.get('url', '')} {s.get('jurisdiction', '')} {s.get('entity', '')} {s.get('business_unit', '')}".lower()
            ]
        return {
            "sources": _paginate(sources, limit, offset),
            "total": len(sources),
            "limit": limit,
            "offset": offset or 0,
        }

    def get_source(self, source_id: str) -> Dict[str, Any]:
        source = self.sources_db.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        return source

    def delete_source(self, source_id: str) -> Dict[str, Any]:
        from backend.state import save_json_dict, SOURCES_DB_PATH

        if source_id not in self.sources_db:
            raise HTTPException(status_code=404, detail="Source not found")
        self.sources_db.pop(source_id, None)
        save_json_dict(SOURCES_DB_PATH, self.sources_db)
        self.audit_repo.append(
            action="source_deleted", entity_type="source", entity_id=source_id
        )
        return {"deleted": True, "source_id": source_id}

    def add_webhook(
        self, url: str, events: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        from backend.state import save_json_dict, WEBHOOKS_DB_PATH

        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=400, detail="Invalid webhook URL scheme")
        webhook_id = str(uuid.uuid4())
        webhook = {
            "webhook_id": webhook_id,
            "url": url,
            "events": events or ["document.uploaded", "gap_analysis.completed"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.webhooks_db[webhook_id] = webhook
        save_json_dict(WEBHOOKS_DB_PATH, self.webhooks_db)
        return webhook

    def list_webhooks(
        self,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        from backend.state import _sort_by_iso, _paginate

        webhooks = _sort_by_iso(list(self.webhooks_db.values()), "created_at")
        if q:
            q_lower = q.lower()
            webhooks = [
                w
                for w in webhooks
                if q_lower
                in f"{w.get('url', '')} {','.join(w.get('events', []))}".lower()
            ]
        return {
            "webhooks": _paginate(webhooks, limit, offset),
            "total": len(webhooks),
            "limit": limit,
            "offset": offset or 0,
        }

    def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        webhook = self.webhooks_db.get(webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return webhook

    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        from backend.state import save_json_dict, WEBHOOKS_DB_PATH

        if webhook_id not in self.webhooks_db:
            raise HTTPException(status_code=404, detail="Webhook not found")
        self.webhooks_db.pop(webhook_id, None)
        save_json_dict(WEBHOOKS_DB_PATH, self.webhooks_db)
        return {"deleted": True, "webhook_id": webhook_id}
