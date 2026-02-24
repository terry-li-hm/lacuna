"""Horizon scanning service — fetches RSS/Atom feeds from registered sources."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import feedparser

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(self, sources_db: Dict[str, Dict[str, Any]], change_service: Any):
        self.sources_db = sources_db
        self.change_service = change_service

    def scan_all_sources(self) -> Dict[str, Any]:
        """Scan all registered RSS/Atom sources for new items."""
        results = []
        total_created = 0
        errors = []

        for source_id, source in self.sources_db.items():
            url = source.get("url", "")
            if not url:
                continue

            try:
                created = self._scan_source(source)
                total_created += created
                results.append(
                    {
                        "source_id": source_id,
                        "name": source.get("name"),
                        "items_created": created,
                        "status": "ok",
                    }
                )
            except Exception as e:
                logger.error(f"Error scanning source {source.get('name')}: {e}")
                results.append(
                    {
                        "source_id": source_id,
                        "name": source.get("name"),
                        "items_created": 0,
                        "status": "error",
                        "error": str(e),
                    }
                )
                errors.append(str(e))

        return {
            "scanned": len(results),
            "total_created": total_created,
            "results": results,
            "errors": errors,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    def _scan_source(self, source: Dict[str, Any]) -> int:
        """Scan a single RSS/Atom source and create change items for new entries."""
        url = source["url"]
        jurisdiction = source.get("jurisdiction", "Unknown")
        default_severity = source.get("default_severity", "medium")

        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed parse error: {feed.bozo_exception}")

        created = 0
        existing_hashes = {
            self.change_service.content_hash(c.get("title", ""), c.get("source_url", ""))
            for c in self.change_service.changes_db.values()
        }

        for entry in feed.entries[:20]:  # Cap at 20 per source
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")

            content_hash = self.change_service.content_hash(title, link)
            if content_hash in existing_hashes:
                continue

            self.change_service.create_change(
                title=title,
                jurisdiction=jurisdiction,
                severity=default_severity,
                status="new",
                summary=summary[:500] if summary else None,
                source=source.get("name"),
                source_url=link,
                effective_date=published or None,
            )
            created += 1

        return created
