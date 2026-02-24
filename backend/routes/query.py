"""Query routes for Meridian API."""

import logging
from fastapi import APIRouter, HTTPException, Depends

from backend.state import get_query_service, documents_db
from backend.models.schemas import QueryRequest, QueryResponse, CompareRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest, service=Depends(get_query_service)):
    """Query regulatory documents using RAG."""
    from backend.config import settings

    if request.n_results < 1 or request.n_results > settings.max_query_results:
        raise HTTPException(
            status_code=400,
            detail=f"n_results must be between 1 and {settings.max_query_results}",
        )

    try:
        return service.query_documents(
            query=request.query,
            jurisdiction=request.jurisdiction,
            n_results=request.n_results,
            doc_id=request.doc_id,
            no_llm=request.no_llm,
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_jurisdictions(
    request: CompareRequest, service=Depends(get_query_service)
):
    """Compare regulatory requirements between two jurisdictions."""
    try:
        return service.compare_jurisdictions(
            jurisdiction1=request.jurisdiction1,
            jurisdiction2=request.jurisdiction2,
            documents_db=documents_db,
            no_llm=request.no_llm,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing jurisdictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
