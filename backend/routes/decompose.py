"""Requirement decomposition routes."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import DecomposeRequest, DecomposeResponse
from backend.state import get_decompose_service

logger = logging.getLogger(__name__)
router = APIRouter()

_decompose_cache: Dict[tuple[str, bool], Any] = {}


@router.post("/decompose", response_model=DecomposeResponse)
async def decompose(
    request: DecomposeRequest,
    service=Depends(get_decompose_service),
):
    """Return atomic requirements for a document, using stored or fresh extraction."""
    cache_key = (request.doc_id, request.fresh)
    if cache_key in _decompose_cache and not request.fresh:
        return _decompose_cache[cache_key]

    try:
        result = await service.decompose(request.doc_id, fresh=request.fresh)
        if not request.fresh:
            _decompose_cache[cache_key] = result
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Decompose error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
