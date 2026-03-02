"""Gap analysis routes for Meridian API."""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from backend.state import (
    get_gap_analysis_service,
)
from backend.models.schemas import (
    GapAnalysisRequest,
    GapAnalysisResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache: (circular_doc_id, baseline_id, is_policy_baseline) -> result
_gap_cache: Dict[tuple, Any] = {}


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(
    request: GapAnalysisRequest, service=Depends(get_gap_analysis_service)
):
    """
    Perform a gap analysis between a new circular and a baseline.
    Results are cached in-memory so repeat calls (e.g. during demos) return instantly.
    """
    logger.info(f"Gap Analysis: {request.circular_doc_id} vs {request.baseline_id}")

    cache_key = (request.circular_doc_id, request.baseline_id, request.is_policy_baseline)
    if cache_key in _gap_cache and not request.no_llm:
        logger.info("Gap analysis cache hit — returning cached result")
        return _gap_cache[cache_key]

    try:
        result = await service.perform_gap_analysis(
            circular_doc_id=request.circular_doc_id,
            baseline_id=request.baseline_id,
            is_policy_baseline=request.is_policy_baseline,
            no_llm=request.no_llm,
        )
        if not request.no_llm:
            _gap_cache[cache_key] = result
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error performing gap analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
