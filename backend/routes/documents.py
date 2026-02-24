"""Document routes for Meridian API."""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Depends
from fastapi.responses import StreamingResponse

from backend.state import (
    get_document_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    jurisdiction: str = Query(
        ..., description="Regulatory jurisdiction (e.g., 'Hong Kong', 'Singapore')"
    ),
    entity: str | None = Query(None, description="Entity or subsidiary name"),
    business_unit: str | None = Query(None, description="Business unit or line"),
    no_llm: bool = Query(False, description="Disable LLM extraction"),
    allow_duplicate: bool = Query(
        True, description="Allow duplicate uploads for same content"
    ),
    service=Depends(get_document_service),
):
    """
    Upload and process a regulatory document.
    """
    logger.info(f"Received upload: {file.filename} for jurisdiction: {jurisdiction}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = await service.upload_document(
            file_content=content,
            filename=file.filename,
            jurisdiction=jurisdiction,
            entity=entity,
            business_unit=business_unit,
            no_llm=no_llm,
            allow_duplicate=allow_duplicate,
        )

        if result.get("duplicate"):
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate document detected (doc_id={result.get('doc_id')})",
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    service=Depends(get_document_service),
):
    """List all processed documents."""
    from backend.state import _paginate

    docs = service.list_documents(
        jurisdiction=jurisdiction,
        entity=entity,
        business_unit=business_unit,
        q=q,
    )

    total = len(docs)
    paged = _paginate(docs, limit, offset)

    return {
        "documents": paged,
        "total": total,
        "limit": limit,
        "offset": offset or 0,
        "jurisdictions": service.get_all_jurisdictions(),
    }


@router.get("/documents/export")
async def export_documents(format: str = "csv", service=Depends(get_document_service)):
    """Export document metadata."""
    docs = service.list_documents()

    if format.lower() == "json":
        return {"documents": docs, "total": len(docs)}
    if format.lower() != "csv":
        raise HTTPException(
            status_code=400, detail="Only CSV or JSON export is supported"
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "doc_id",
            "filename",
            "jurisdiction",
            "entity",
            "business_unit",
            "chunks_count",
            "requirements_count",
            "size_bytes",
            "content_hash",
            "uploaded_at",
        ],
    )
    writer.writeheader()
    for doc in docs:
        writer.writerow(
            {
                "doc_id": doc.get("doc_id"),
                "filename": doc.get("filename"),
                "jurisdiction": doc.get("jurisdiction"),
                "entity": doc.get("entity"),
                "business_unit": doc.get("business_unit"),
                "chunks_count": doc.get("chunks_count"),
                "requirements_count": len(doc.get("requirements") or []),
                "size_bytes": doc.get("size_bytes"),
                "content_hash": doc.get("content_hash"),
                "uploaded_at": doc.get("uploaded_at"),
            }
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, service=Depends(get_document_service)):
    """Get a single document with requirements."""
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{doc_id}/requirements")
async def get_document_requirements(doc_id: str, service=Depends(get_document_service)):
    """Get requirements extracted from a specific document."""
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    requirements = doc.get("requirements", [])
    return {"doc_id": doc_id, "requirements": requirements, "total": len(requirements)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, service=Depends(get_document_service)):
    """Delete a document and its vector chunks."""
    success = service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"deleted": True, "doc_id": doc_id}
