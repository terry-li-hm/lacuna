"""Gap analysis routes for Meridian API."""

import asyncio
import logging
import os
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
import weasyprint

from backend.state import (
    get_gap_analysis_service,
    get_document_service,
    get_policy_service,
)
from backend.models.schemas import (
    GapAnalysisRequest,
    GapAnalysisResponse,
    BatchGapAnalysisRequest,
    BatchGapAnalysisResponse,
    BatchGapAnalysisResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

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


@router.post("/gap-analysis/export")
async def export_gap_analysis(
    request: GapAnalysisRequest,
    service=Depends(get_gap_analysis_service),
    doc_service=Depends(get_document_service),
    policy_service=Depends(get_policy_service),
):
    """
    Perform a gap analysis and export the result as a Capco-branded PDF report.
    """
    logger.info(f"Exporting Gap Analysis: {request.circular_doc_id} vs {request.baseline_id}")

    cache_key = (request.circular_doc_id, request.baseline_id, request.is_policy_baseline)
    
    if cache_key in _gap_cache and not request.no_llm:
        logger.info("Gap analysis cache hit — using cached result for export")
        result = _gap_cache[cache_key]
    else:
        try:
            result = await service.perform_gap_analysis(
                circular_doc_id=request.circular_doc_id,
                baseline_id=request.baseline_id,
                is_policy_baseline=request.is_policy_baseline,
                no_llm=request.no_llm,
            )
            if not request.no_llm:
                _gap_cache[cache_key] = result
        except ValueError as e:
            raise HTTPException(
                status_code=404 if "not found" in str(e).lower() else 400, detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error performing gap analysis for export: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    # Get names for circular and baseline for the report
    circular_name = request.circular_doc_id
    baseline_name = request.baseline_id

    try:
        # Try to resolve circular name
        doc = doc_service.get_document(request.circular_doc_id)
        if doc:
            circular_name = doc.get("title") or doc.get("name") or request.circular_doc_id
            
        # Try to resolve baseline name
        if request.is_policy_baseline:
            policy = policy_service.get_policy(request.baseline_id)
            if policy:
                baseline_name = policy.get("name") or policy.get("title") or request.baseline_id
        else:
            doc = doc_service.get_document(request.baseline_id)
            if doc:
                baseline_name = doc.get("title") or doc.get("name") or request.baseline_id
    except Exception as e:
        logger.warning(f"Could not resolve circular or baseline names: {e}")

    # Prepare data for template
    template_data = {
        "circular_name": circular_name,
        "baseline_name": baseline_name,
        "generated_at": result.generated_at,
        "summary": result.summary,
        "findings": [f.model_dump() for f in result.findings],
    }

    try:
        # Render HTML
        template = jinja_env.get_template("gap_report.html")
        html_content = template.render(**template_data)

        # Generate PDF using WeasyPrint in a thread to avoid blocking event loop
        pdf_bytes = await asyncio.to_thread(
            lambda: weasyprint.HTML(string=html_content).write_pdf()
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="lacuna-gap-report.pdf"'
            },
        )
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")


@router.post("/gap-analysis/batch", response_model=BatchGapAnalysisResponse)
async def batch_gap_analysis(
    request: BatchGapAnalysisRequest, service=Depends(get_gap_analysis_service)
):
    """
    Perform gap analysis for one baseline against multiple circulars in parallel.
    Individual failures are returned per circular without failing the whole batch.
    """

    async def _analyze_single(circular_doc_id: str) -> BatchGapAnalysisResult:
        cache_key = (circular_doc_id, request.baseline_id, request.is_policy_baseline)
        if cache_key in _gap_cache and not request.no_llm:
            logger.info(
                f"Gap analysis cache hit — returning cached result for {circular_doc_id}"
            )
            return BatchGapAnalysisResult(
                circular_doc_id=circular_doc_id, result=_gap_cache[cache_key]
            )

        try:
            result = await service.perform_gap_analysis(
                circular_doc_id=circular_doc_id,
                baseline_id=request.baseline_id,
                is_policy_baseline=request.is_policy_baseline,
                no_llm=request.no_llm,
            )
            if not request.no_llm:
                _gap_cache[cache_key] = result
            return BatchGapAnalysisResult(circular_doc_id=circular_doc_id, result=result)
        except ValueError as e:
            return BatchGapAnalysisResult(circular_doc_id=circular_doc_id, error=str(e))
        except Exception as e:
            logger.error(
                f"Error performing gap analysis for {circular_doc_id}: {e}",
                exc_info=True,
            )
            return BatchGapAnalysisResult(
                circular_doc_id=circular_doc_id, error="Internal server error"
            )

    tasks = [_analyze_single(circular_doc_id) for circular_doc_id in request.circular_doc_ids]
    gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for circular_doc_id, item in zip(request.circular_doc_ids, gathered_results):
        if isinstance(item, Exception):
            logger.error(
                f"Error performing gap analysis for {circular_doc_id}: {item}",
                exc_info=True,
            )
            results.append(
                BatchGapAnalysisResult(
                    circular_doc_id=circular_doc_id, error="Internal server error"
                )
            )
        else:
            results.append(item)

    return BatchGapAnalysisResponse(baseline_id=request.baseline_id, results=results)
