"""Evidence routes for Meridian API."""

import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse

from backend.state import get_evidence_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/evidence/upload")
async def upload_evidence(
    entity_type: str = Query(..., description="requirement"),
    entity_id: str = Query(..., description="Target entity ID"),
    file: UploadFile = File(...),
    service=Depends(get_evidence_service),
):
    """Upload evidence file and link it to a requirement."""
    return await service.upload_evidence(entity_type, entity_id, file)


@router.get("/evidence")
async def list_evidence(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_evidence_service),
):
    """List evidence records."""
    return service.list_evidence(entity_type, entity_id, limit, offset)


@router.get("/evidence/{evidence_id}/download")
async def download_evidence(evidence_id: str, service=Depends(get_evidence_service)):
    """Download an evidence file by ID."""
    path, filename = service.get_evidence_path(evidence_id)
    return FileResponse(path, filename=filename)


@router.delete("/evidence/{evidence_id}")
async def delete_evidence(evidence_id: str, service=Depends(get_evidence_service)):
    """Delete an evidence record and file."""
    return service.delete_evidence(evidence_id)
