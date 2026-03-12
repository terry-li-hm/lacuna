"""FastAPI application for Meridian regulatory analytics platform."""

import hmac
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

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
    remediation_router,
    decompose_router,
    confirm_router,
)
from backend.routes import synthesis
from backend import state

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Initialize app
app = FastAPI(
    title="Meridian",
    description="Cross-jurisdiction regulatory analytics platform for financial institutions",
    version="0.1.0",
)

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    if not settings.lacuna_api_keys:
        return await call_next(request)

    submitted = request.headers.get("X-API-Key", "")
    if not submitted:
        return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

    valid = any(
        hmac.compare_digest(submitted.encode(), key.encode())
        for key in settings.lacuna_api_keys
    )
    if not valid:
        return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

    return await call_next(request)

@app.on_event("startup")
async def startup_auth_warning():
    if not settings.lacuna_api_keys:
        logger.warning("LACUNA_API_KEYS not set - API key auth is DISABLED. Set before production use.")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lacuna.sh",
        "https://lacuna-production-8dbb.up.railway.app",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
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
app.include_router(remediation_router, tags=["remediation"])
app.include_router(decompose_router, tags=["decompose"])
app.include_router(confirm_router, tags=["confirm"])
app.include_router(synthesis.router, tags=["synthesis"])

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend dashboard."""
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
