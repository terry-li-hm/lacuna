"""FastAPI application for regulatory analytics tool."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes import (
    documents_router,
    requirements_router,
    gap_analysis_router,
    policies_router,
    system_router,
    query_router,
    integrations_router,
    evidence_router,
    changes_router,
)
from backend import state

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="RegAtlas",
    description="Cross-jurisdiction regulatory analytics platform for financial institutions",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize state and components
state.init_state()
state.init_components()

# Include routers
app.include_router(system_router, tags=["system"])
app.include_router(documents_router, tags=["documents"])
app.include_router(requirements_router, tags=["requirements"])
app.include_router(gap_analysis_router, tags=["gap-analysis"])
app.include_router(policies_router, tags=["policies"])
app.include_router(query_router, tags=["query"])
app.include_router(integrations_router, tags=["integrations"])
app.include_router(evidence_router, tags=["evidence"])
app.include_router(changes_router, tags=["changes"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
