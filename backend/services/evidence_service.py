"""Evidence service for managing compliance evidence."""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, UploadFile

from backend.config import settings

logger = logging.getLogger(__name__)


class EvidenceService:
    def __init__(self, evidence_db, audit_repo):
        self.evidence_db = evidence_db
        self.audit_repo = audit_repo

    async def upload_evidence(
        self, entity_type: str, entity_id: str, file: UploadFile
    ) -> Dict[str, Any]:
        from backend.state import save_json_list, EVIDENCE_DB_PATH

        allowed = {"requirement", "change", "policy"}
        if entity_type not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"entity_type must be one of: {', '.join(sorted(allowed))}",
            )

        evidence_id = str(uuid.uuid4())
        base_dir = settings.data_dir / "evidence" / entity_type / entity_id
        base_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename).name
        file_path = base_dir / f"{evidence_id}_{safe_name}"

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Evidence file is empty")

        max_size = settings.max_upload_mb * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail="Evidence file is too large")

        with open(file_path, "wb") as f:
            f.write(content)

        entry = {
            "evidence_id": evidence_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "filename": safe_name,
            "path": str(file_path),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(content),
        }
        self.evidence_db.append(entry)
        save_json_list(EVIDENCE_DB_PATH, self.evidence_db)
        self.audit_repo.append(
            action="evidence_uploaded",
            entity_type=entity_type,
            entity_id=entity_id,
            details={"evidence_id": evidence_id, "filename": safe_name},
        )
        return entry

    def list_evidence(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        from backend.state import _sort_by_iso, _paginate

        filtered = []
        for entry in _sort_by_iso(self.evidence_db, "uploaded_at"):
            if entity_type and entry.get("entity_type") != entity_type:
                continue
            if entity_id and entry.get("entity_id") != entity_id:
                continue
            path = Path(entry.get("path") or "")
            enriched = {
                **entry,
                "file_exists": path.exists(),
                "file_size": path.stat().st_size if path.exists() else None,
            }
            filtered.append(enriched)

        return {
            "evidence": _paginate(filtered, limit, offset),
            "total": len(filtered),
            "limit": limit,
            "offset": offset or 0,
        }

    def get_evidence_path(self, evidence_id: str) -> tuple[Path, str]:
        entry = next(
            (
                item
                for item in self.evidence_db
                if item.get("evidence_id") == evidence_id
            ),
            None,
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Evidence not found")
        path = Path(entry.get("path") or "")
        evidence_root = settings.data_dir / "evidence"
        if not path.resolve().is_relative_to(evidence_root.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Evidence file missing on disk")
        return path, entry.get("filename") or path.name

    def delete_evidence(self, evidence_id: str) -> Dict[str, Any]:
        from backend.state import save_json_list, EVIDENCE_DB_PATH

        entry = next(
            (
                item
                for item in self.evidence_db
                if item.get("evidence_id") == evidence_id
            ),
            None,
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Evidence not found")

        path = Path(entry.get("path") or "")
        if path.exists():
            path.unlink()

        self.evidence_db.remove(entry)
        save_json_list(EVIDENCE_DB_PATH, self.evidence_db)
        self.audit_repo.append(
            action="evidence_deleted",
            entity_type=entry.get("entity_type") or "evidence",
            entity_id=entry.get("entity_id") or evidence_id,
            details={"evidence_id": evidence_id},
        )
        return {"deleted": True, "evidence_id": evidence_id}
