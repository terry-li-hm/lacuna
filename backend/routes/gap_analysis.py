"""Gap analysis routes for Meridian API."""

import logging
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


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(
    request: GapAnalysisRequest, service=Depends(get_gap_analysis_service)
):
    """
    Perform a gap analysis between a new circular and a baseline.
    """
    logger.info(f"Gap Analysis: {request.circular_doc_id} vs {request.baseline_id}")

    try:
        return await service.perform_gap_analysis(
            circular_doc_id=request.circular_doc_id,
            baseline_id=request.baseline_id,
            is_policy_baseline=request.is_policy_baseline,
            no_llm=request.no_llm,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error performing gap analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
