"""Requirement decomposition routes."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import DecomposeRequest, DecomposeResponse
from backend.state import get_decompose_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Cache non-fresh decompositions for 5 minutes. Keyed by doc_id only — fresh
# results are never cached. Tuple value is (result, expiry_timestamp).
_CACHE_TTL_SECONDS = 300
_decompose_cache: dict[str, tuple[DecomposeResponse, float]] = {}


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose(
    request: DecomposeRequest,
    service=Depends(get_decompose_service),
):
    """Return atomic requirements for a document, using stored or fresh extraction."""
    if not request.fresh:
        cached = _decompose_cache.get(request.doc_id)
        if cached is not None:
            result, expiry = cached
            if time.monotonic() < expiry:
                return result
            del _decompose_cache[request.doc_id]

    try:
        result = await service.decompose(request.doc_id, fresh=request.fresh)
        if not request.fresh:
            _decompose_cache[request.doc_id] = (result, time.monotonic() + _CACHE_TTL_SECONDS)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Decompose error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
