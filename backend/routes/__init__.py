"""Route exports for Meridian API."""

from .documents import router as documents_router
from .requirements import router as requirements_router
from .gap_analysis import router as gap_analysis_router
from .policies import router as policies_router
from .system import router as system_router
from .query import router as query_router
from .integrations import router as integrations_router
from .evidence import router as evidence_router
from .changes import router as changes_router
from .remediation import router as remediation_router
from .decompose import router as decompose_router
from .confirm import router as confirm_router

__all__ = [
    "documents_router",
    "requirements_router",
    "gap_analysis_router",
    "policies_router",
    "system_router",
    "query_router",
    "integrations_router",
    "evidence_router",
    "changes_router",
    "remediation_router",
    "decompose_router",
    "confirm_router",
]
