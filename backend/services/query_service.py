"""Query service for RAG and comparison logic."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from backend.config import settings

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, vector_store, req_extractor):
        self.vector_store = vector_store
        self.req_extractor = req_extractor

    def query_documents(
        self,
        query: str,
        jurisdiction: str,
        n_results: int = 5,
        doc_id: Optional[str] = None,
        no_llm: bool = False,
    ) -> Dict[str, Any]:
        """Query regulatory documents using RAG."""
        filters = {}
        if doc_id:
            filters["doc_id"] = doc_id

        results = self.vector_store.query(
            query_text=query,
            n_results=n_results,
            jurisdiction=jurisdiction,
            filters=filters or None,
        )

        summary = None
        if self.req_extractor.client and results and not no_llm:
            context = "\n\n".join([r["document"] for r in results[:3]])
            try:
                response = self.req_extractor.client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a regulatory compliance expert. Provide concise, accurate answers based on the provided regulatory text.",
                        },
                        {
                            "role": "user",
                            "content": f"Based on the following regulatory text, answer this question: {query}\n\nContext:\n{context}",
                        },
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )
                summary = response.choices[0].message.content or "No summary generated"
            except Exception as e:
                logger.warning(f"Could not generate summary: {e}")

        return {"query": query, "results": results, "summary": summary}

    def compare_jurisdictions(
        self,
        jurisdiction1: str,
        jurisdiction2: str,
        documents_db: Dict[str, Any],
        no_llm: bool = False,
    ) -> Dict[str, Any]:
        """Compare regulatory requirements between two jurisdictions."""
        from backend.state import _extract_requirements_from_doc, get_document_repo

        # Prefer doc_repo (DuckDB) over in-memory documents_db
        all_docs = documents_db.values()
        if not documents_db:
            all_docs = get_document_repo().list_all()

        docs1 = [doc for doc in all_docs if doc.get("jurisdiction") == jurisdiction1]
        docs2 = [doc for doc in all_docs if doc.get("jurisdiction") == jurisdiction2]

        if not docs1:
            raise HTTPException(
                status_code=404, detail=f"No documents found for {jurisdiction1}"
            )
        if not docs2:
            raise HTTPException(
                status_code=404, detail=f"No documents found for {jurisdiction2}"
            )

        req1 = {"jurisdiction": jurisdiction1, "requirements": []}
        req2 = {"jurisdiction": jurisdiction2, "requirements": []}

        for doc in docs1:
            req1["requirements"].extend(_extract_requirements_from_doc(doc))
        for doc in docs2:
            req2["requirements"].extend(_extract_requirements_from_doc(doc))

        comparison = self.req_extractor.compare_requirements(
            req1, req2, force_basic=no_llm
        )

        return {
            "jurisdiction1": jurisdiction1,
            "jurisdiction2": jurisdiction2,
            "comparison": comparison,
            "documents_compared": {
                jurisdiction1: len(docs1),
                jurisdiction2: len(docs2),
            },
        }
