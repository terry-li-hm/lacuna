"""Remediation planning routes for Meridian API."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.state import get_gap_analysis_service, get_requirement_service
from backend.routes import gap_analysis as _gap_analysis_module

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/remediation/plan")
async def remediation_plan(
    circular_doc_id: str,
    baseline_id: str,
    gap_service=Depends(get_gap_analysis_service),
    requirement_service=Depends(get_requirement_service),
):
    """Return enriched and bucketed findings for remediation planning."""
    cache_key = (circular_doc_id, baseline_id, False, False, False, False)
    gap_result = _gap_analysis_module._gap_cache.get(cache_key)

    if gap_result is None:
        try:
            gap_result = await gap_service.perform_gap_analysis(
                circular_doc_id=circular_doc_id,
                baseline_id=baseline_id,
                is_policy_baseline=False,
                no_llm=False,
            )
            _gap_analysis_module._gap_cache[cache_key] = gap_result
        except ValueError as e:
            raise HTTPException(
                status_code=404 if "not found" in str(e).lower() else 400,
                detail=str(e),
            )
        except Exception as e:
            logger.error(f"Error performing remediation plan analysis: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    findings_payload = []
    counts = {
        "unaddressed": 0,
        "in_progress": 0,
        "addressed": 0,
        "not_applicable": 0,
    }

    for finding in gap_result.findings:
        circular_req_id = getattr(finding, "circular_req_id", None)
        requirement = (
            requirement_service.get_requirement(circular_req_id) if circular_req_id else None
        )

        review_status = None
        reviewer = None
        review_notes = None
        tags = []

        if requirement:
            review_status = requirement.get("review_status") or requirement.get("status")
            reviewer = requirement.get("reviewer")
            review_notes = requirement.get("review_notes")
            tags = requirement.get("tags") or []

        if review_status == "Addressed":
            bucket = "addressed"
        elif review_status == "Not Applicable":
            bucket = "not_applicable"
        elif review_status == "In Progress":
            bucket = "in_progress"
        else:
            bucket = "unaddressed"

        counts[bucket] += 1

        findings_payload.append(
            {
                "circular_req_id": circular_req_id,
                "description": getattr(finding, "description", None),
                "gap_status": getattr(finding, "status", None),
                "reasoning": getattr(finding, "reasoning", None),
                "review_status": review_status,
                "reviewer": reviewer,
                "review_notes": review_notes,
                "tags": tags,
                "bucket": bucket,
            }
        )

    total = len(findings_payload)
    remediation_pct = (
        ((counts["addressed"] + counts["not_applicable"]) / total) * 100 if total > 0 else 0.0
    )

    return {
        "circular_id": getattr(gap_result, "circular_id", circular_doc_id),
        "baseline_id": getattr(gap_result, "baseline_id", baseline_id),
        "summary": {
            "total": total,
            "unaddressed": counts["unaddressed"],
            "in_progress": counts["in_progress"],
            "addressed": counts["addressed"],
            "not_applicable": counts["not_applicable"],
            "remediation_pct": remediation_pct,
        },
        "findings": findings_payload,
    }
