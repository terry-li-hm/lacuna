"""Gap analysis routes for RegAtlas API."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.state import (
    _extract_requirements_from_doc,
    documents_db,
    policies_db,
    req_extractor,
    vector_store,
)
from backend.models.schemas import (
    GapAnalysisRequest,
    GapAnalysisResponse,
    GapRequirementMapping,
    Provenance,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(request: GapAnalysisRequest):
    """
    Perform a gap analysis between a new circular and a baseline.
    """
    logger.info(f"Gap Analysis: {request.circular_doc_id} vs {request.baseline_id}")

    try:
        # 1. Verify Circular Document exists
        if request.circular_doc_id not in documents_db:
            raise HTTPException(
                status_code=404,
                detail=f"Circular document {request.circular_doc_id} not found",
            )

        circular_doc = documents_db[request.circular_doc_id]
        circular_requirements = _extract_requirements_from_doc(circular_doc)

        if not circular_requirements:
            raise HTTPException(
                status_code=400,
                detail="Circular document has no extracted requirements",
            )

        # 2. Verify Baseline exists
        baseline_id = request.baseline_id
        if request.is_policy_baseline:
            if baseline_id not in policies_db:
                raise HTTPException(
                    status_code=404, detail=f"Policy baseline {baseline_id} not found"
                )
        else:
            if baseline_id not in documents_db:
                raise HTTPException(
                    status_code=404, detail=f"Document baseline {baseline_id} not found"
                )

        findings = []
        summary = {"Full": 0, "Partial": 0, "Gap": 0}

        # 3. Perform Gap Analysis for each Circular Requirement
        for req in circular_requirements:
            # Search baseline for relevant context
            # Use 'filters' to target either 'doc_id' or 'policy_id' (if implemented)
            # For now, we assume policy chunks are also in VectorStore with doc_id = policy_id
            filters = {"doc_id": baseline_id}

            baseline_chunks = vector_store.query(
                query_text=req.get("description", ""), n_results=3, filters=filters
            )

            # Analyze gap
            analysis = req_extractor.perform_gap_analysis(
                circular_req=req,
                baseline_chunks=baseline_chunks,
                force_basic=bool(request.no_llm),
            )

            status = analysis.get("status", "Gap")
            summary[status] = summary.get(status, 0) + 1

            findings.append(
                GapRequirementMapping(
                    circular_req_id=str(uuid.uuid4()),
                    description=req.get("description", "No description"),
                    status=status,
                    reasoning=analysis.get("reasoning", "No reasoning provided"),
                    provenance=[
                        Provenance(**p) for p in analysis.get("provenance", [])
                    ],
                )
            )

        report_id = f"gap_{uuid.uuid4().hex[:8]}"

        return GapAnalysisResponse(
            report_id=report_id,
            circular_id=request.circular_doc_id,
            baseline_id=request.baseline_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            findings=findings,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing gap analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
