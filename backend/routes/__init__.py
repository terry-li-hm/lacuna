"""Route exports for RegAtlas API."""

from fastapi import APIRouter
from .documents import router as documents_router
from .requirements import router as requirements_router
from .gap_analysis import router as gap_analysis_router
from .policies import router as policies_router
from .system import router as system_router

__all__ = [
    "documents_router",
    "requirements_router",
    "gap_analysis_router",
    "policies_router",
    "system_router",
]
