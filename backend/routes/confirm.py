"""Routes for confirmed requirement list operations."""

from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import ConfirmedListResponse, ConfirmRequest, ConfirmResponse
from backend.state import get_confirm_service

router = APIRouter()


@router.post("/confirm/{doc_id}", response_model=ConfirmResponse)
async def save_confirmed(
    doc_id: str,
    request: ConfirmRequest,
    service=Depends(get_confirm_service),
):
    """Save or overwrite the confirmed requirement list for a document."""
    try:
        return service.save(
            doc_id=doc_id,
            requirements=request.requirements,
            confirmed_by=request.confirmed_by,
        )
    except ValueError as e:
        message = str(e)
        raise HTTPException(
            status_code=404 if "not found" in message.lower() else 400,
            detail=message,
        )


@router.get("/confirm/{doc_id}", response_model=ConfirmedListResponse)
async def get_confirmed(doc_id: str, service=Depends(get_confirm_service)):
    """Get confirmed requirement list for a document."""
    try:
        return service.get(doc_id)
    except ValueError as e:
        message = str(e)
        raise HTTPException(
            status_code=404 if "not found" in message.lower() else 400,
            detail=message,
        )
