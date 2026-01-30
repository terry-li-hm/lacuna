import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.storage.repositories import DocumentRepository
from backend.document_processor import DocumentProcessor
from backend.vector_store import VectorStore
from backend.services.llm_service import LLMService
from backend.state import (
    _content_hash,
    _normalize_text,
    _normalize_requirements,
    _attach_evidence,
)

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        vector_store: VectorStore,
        processor: DocumentProcessor,
        llm_service: LLMService,
    ):
        self.doc_repo = doc_repo
        self.vector_store = vector_store
        self.processor = processor
        self.llm_service = llm_service

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        jurisdiction: str,
        entity: Optional[str] = None,
        business_unit: Optional[str] = None,
        no_llm: bool = False,
        allow_duplicate: bool = True,
    ) -> Dict[str, Any]:
        """Upload and process a regulatory document."""
        doc_id = str(uuid.uuid4())
        content_hash = _content_hash(file_content)

        if not allow_duplicate:
            # Check for existing document with same hash
            # For now, we'll keep using the list_all and checking manually since the repo doesn't have get_by_hash
            all_docs = self.doc_repo.list_all()
            for doc in all_docs:
                if doc.get("content_hash") == content_hash:
                    return {"duplicate": True, "doc_id": doc.get("doc_id")}

        # Save temporarily for processing
        temp_dir = Path("data/temp")
        temp_dir.mkdir(exist_ok=True, parents=True)
        temp_path = temp_dir / f"{doc_id}_{filename}"

        try:
            temp_path.write_bytes(file_content)

            # Process document
            processed = self.processor.process_file(temp_path)
            full_text = processed["full_text"]

            if not full_text.strip():
                raise ValueError("No text extracted from document")

            # Extract requirements
            requirements_payload = self.llm_service.extract_requirements(
                full_text, jurisdiction, force_basic=no_llm
            )

            # Chunk and add to vector store
            chunks = self.processor.chunk_text(full_text, chunk_size=1000, overlap=200)
            if not chunks:
                raise ValueError("Document text too short to index")

            metadata = {
                **processed["metadata"],
                "jurisdiction": jurisdiction,
                "entity": _normalize_text(entity),
                "business_unit": _normalize_text(business_unit),
                "doc_id": doc_id,
                "content_hash": content_hash,
                "size_bytes": len(file_content),
            }

            chunks_added = self.vector_store.add_document(doc_id, chunks, metadata)
            if chunks_added == 0:
                raise ValueError("No chunks indexed for document")

            # Normalize requirements and attach evidence
            requirements = _normalize_requirements(
                requirements_payload.get("requirements", []),
                doc_id=doc_id,
                jurisdiction=jurisdiction,
                filename=filename,
                entity=_normalize_text(entity),
                business_unit=_normalize_text(business_unit),
            )
            _attach_evidence(requirements, doc_id)

            # Store document info
            doc_data = {
                "doc_id": doc_id,
                "filename": filename,
                "jurisdiction": jurisdiction,
                "entity": _normalize_text(entity),
                "business_unit": _normalize_text(business_unit),
                "requirements": requirements,
                "raw_extraction": requirements_payload.get("raw_extraction"),
                "chunks_count": chunks_added,
                "metadata": metadata,
                "content_hash": content_hash,
                "size_bytes": len(file_content),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }

            self.doc_repo.save(doc_data)

            return {
                "doc_id": doc_id,
                "filename": filename,
                "jurisdiction": jurisdiction,
                "chunks_added": chunks_added,
                "requirements": requirements,
            }
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def list_documents(
        self,
        jurisdiction: Optional[str] = None,
        entity: Optional[str] = None,
        business_unit: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all processed documents with filtering."""
        docs = self.doc_repo.list_all()
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
        return filtered

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a single document with requirements."""
        return self.doc_repo.get(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its vector chunks."""
        doc = self.doc_repo.get(doc_id)
        if not doc:
            return False

        self.vector_store.delete_document(doc_id)
        return self.doc_repo.delete(doc_id)

    def get_all_jurisdictions(self) -> List[str]:
        """Get all jurisdictions from documents and vector store."""
        repo_jurisdictions = set(self.doc_repo.get_all_jurisdictions())
        vector_jurisdictions = set(self.vector_store.list_jurisdictions())
        return sorted(list(repo_jurisdictions | vector_jurisdictions))
