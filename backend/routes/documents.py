"""Document routes for RegAtlas API."""

import csv
import io
import logging
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.state import (
    DOCUMENTS_DB_PATH,
    _attach_evidence,
    _content_hash,
    _normalize_requirements,
    _normalize_text,
    _paginate,
    _sort_by_iso,
    documents_db,
    doc_processor,
    req_extractor,
    save_documents_db,
    vector_store,
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
):
    """
    Upload and process a regulatory document.

    Args:
        file: PDF or text file containing regulatory text
        jurisdiction: Jurisdiction this document belongs to

    Returns:
        Processing results including extracted requirements
    """
    logger.info(f"Received upload: {file.filename} for jurisdiction: {jurisdiction}")

    file_path = None
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        if Path(file.filename).suffix.lower() not in {".pdf", ".txt"}:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # Generate document ID
        doc_id = str(uuid.uuid4())

        # Save uploaded file temporarily
        temp_dir = settings.data_dir / "temp"
        temp_dir.mkdir(exist_ok=True)

        safe_name = Path(file.filename).name
        file_path = temp_dir / f"{doc_id}_{safe_name}"

        with open(file_path, "wb") as f:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            max_size = settings.max_upload_mb * 1024 * 1024
            if len(content) > max_size:
                raise HTTPException(
                    status_code=413, detail="Uploaded file is too large"
                )
            f.write(content)

        content_hash = _content_hash(content)
        if not allow_duplicate:
            for doc in documents_db.values():
                if doc.get("content_hash") == content_hash:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Duplicate document detected (doc_id={doc.get('doc_id')})",
                    )

        # Process document
        processed = doc_processor.process_file(file_path)

        # Extract requirements
        full_text = processed["full_text"]
        if not full_text.strip():
            raise HTTPException(
                status_code=400, detail="No text extracted from document"
            )
        requirements_payload = req_extractor.extract_requirements(
            full_text, jurisdiction, force_basic=no_llm
        )

        # Chunk and add to vector store
        chunks = doc_processor.chunk_text(full_text, chunk_size=1000, overlap=200)
        if not chunks:
            raise HTTPException(
                status_code=400, detail="Document text too short to index"
            )

        from datetime import datetime, timezone

        metadata = {
            **processed["metadata"],
            "jurisdiction": jurisdiction,
            "entity": _normalize_text(entity),
            "business_unit": _normalize_text(business_unit),
            "doc_id": doc_id,
            "content_hash": content_hash,
            "size_bytes": len(content),
        }

        chunks_added = vector_store.add_document(doc_id, chunks, metadata)
        if chunks_added == 0:
            raise HTTPException(
                status_code=400, detail="No chunks indexed for document"
            )

        # Normalize requirements and attach evidence
        requirements = _normalize_requirements(
            requirements_payload.get("requirements", []),
            doc_id=doc_id,
            jurisdiction=jurisdiction,
            filename=safe_name,
            entity=_normalize_text(entity),
            business_unit=_normalize_text(business_unit),
        )
        _attach_evidence(requirements, doc_id)

        # Store document info
        documents_db[doc_id] = {
            "doc_id": doc_id,
            "filename": safe_name,
            "jurisdiction": jurisdiction,
            "entity": _normalize_text(entity),
            "business_unit": _normalize_text(business_unit),
            "requirements": requirements,
            "raw_extraction": requirements_payload.get("raw_extraction"),
            "chunks_count": chunks_added,
            "metadata": metadata,
            "content_hash": content_hash,
            "size_bytes": len(content),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        save_documents_db(DOCUMENTS_DB_PATH, documents_db)

        logger.info(f"Successfully processed document {doc_id}")

        return {
            "doc_id": doc_id,
            "filename": safe_name,
            "jurisdiction": jurisdiction,
            "chunks_added": chunks_added,
            "requirements": requirements,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path and file_path.exists():
            file_path.unlink()


@router.get("/documents")
async def list_documents(
    jurisdiction: str | None = None,
    entity: str | None = None,
    business_unit: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
):
    """List all processed documents."""
    from backend.state import _all_jurisdictions

    docs = _sort_by_iso(list(documents_db.values()), "uploaded_at")
    filtered = []
    for doc in docs:
        if jurisdiction and doc.get("jurisdiction") != jurisdiction:
            continue
        if entity and doc.get("entity") != entity:
            continue
        if business_unit and doc.get("business_unit") != business_unit:
            continue
        if q:
            haystack = " ".join(
                [
                    doc.get("filename") or "",
                    doc.get("jurisdiction") or "",
                    doc.get("entity") or "",
                    doc.get("business_unit") or "",
                ]
            ).lower()
            if q.lower() not in haystack:
                continue
        filtered.append(doc)

    total = len(filtered)
    paged = _paginate(filtered, limit, offset)
    return {
        "documents": paged,
        "total": total,
        "limit": limit,
        "offset": offset or 0,
        "jurisdictions": _all_jurisdictions(),
    }


@router.get("/documents/export")
async def export_documents(format: str = "csv"):
    """Export document metadata."""
    docs = _sort_by_iso(list(documents_db.values()), "uploaded_at")
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
async def get_document(doc_id: str):
    """Get a single document with requirements."""
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its vector chunks."""
    doc = documents_db.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_document(doc_id)
    documents_db.pop(doc_id, None)
    save_documents_db(DOCUMENTS_DB_PATH, documents_db)

    return {"deleted": True, "doc_id": doc_id}
