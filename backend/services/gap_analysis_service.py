import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.storage.repositories import DocumentRepository, PolicyRepository
from backend.vector_store import VectorStore
from backend.services.llm_service import LLMService
from backend.models.schemas import (
    CompletenessAudit,
    CompletenessFlag,
    GapRequirementMapping,
    Provenance,
    GapAnalysisResponse,
)

logger = logging.getLogger(__name__)


class GapAnalysisService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        policy_repo: PolicyRepository,
        vector_store: VectorStore,
        llm_service: LLMService,
    ):
        self.doc_repo = doc_repo
        self.policy_repo = policy_repo
        self.vector_store = vector_store
        self.llm_service = llm_service

    async def perform_gap_analysis(
        self,
        circular_doc_id: str,
        baseline_id: str,
        is_policy_baseline: bool = False,
        include_amendments: bool = False,
        include_completeness_audit: bool = False,
        no_llm: bool = False,
    ) -> GapAnalysisResponse:
        """Perform a gap analysis between a circular document and a baseline."""

        # 1. Verify Circular Document exists
        circular_doc = self.doc_repo.get(circular_doc_id)
        if not circular_doc:
            raise ValueError(f"Circular document {circular_doc_id} not found")

        from backend.state import _extract_requirements_from_doc

        circular_requirements = _extract_requirements_from_doc(circular_doc)

        if not circular_requirements:
            raise ValueError("Circular document has no extracted requirements")

        # 2. Verify Baseline exists
        if is_policy_baseline:
            baseline = self.policy_repo.get(baseline_id)
            if not baseline:
                raise ValueError(f"Policy baseline {baseline_id} not found")
        else:
            baseline = self.doc_repo.get(baseline_id)
            if not baseline:
                raise ValueError(f"Document baseline {baseline_id} not found")

        findings = []
        summary = {"Full": 0, "Partial": 0, "Gap": 0}

        # 3. Perform Gap Analysis for each Circular Requirement
        for req in circular_requirements:
            # Search baseline for relevant context
            filters = {"doc_id": baseline_id}

            baseline_chunks = self.vector_store.query(
                query_text=req.get("description", ""), n_results=3, filters=filters
            )

            # Analyze gap
            analysis = await asyncio.to_thread(
                self.llm_service.perform_gap_analysis,
                req,
                baseline_chunks,
                bool(no_llm),
            )

            status = analysis.get("status", "Gap")
            summary[status] = summary.get(status, 0) + 1

            draft_amendment: Optional[str] = None
            if include_amendments and not no_llm and status in ("Partial", "Gap"):
                draft_amendment = await asyncio.to_thread(
                    self.llm_service.generate_draft_amendment,
                    req,
                    baseline_chunks,
                    status,
                    analysis.get("reasoning", "No reasoning provided"),
                )

            findings.append(
                GapRequirementMapping(
                    circular_req_id=str(uuid.uuid4()),
                    description=req.get("description", "No description"),
                    status=status,
                    reasoning=analysis.get("reasoning", "No reasoning provided"),
                    draft_amendment=draft_amendment,
                    provenance=[
                        Provenance(**p) for p in analysis.get("provenance", [])
                    ],
                )
            )

        report_id = f"gap_{uuid.uuid4().hex[:8]}"
        completeness_audit = None
        if include_completeness_audit:
            try:
                circular_text = (
                    circular_doc.get("raw_text")
                    or circular_doc.get("content")
                    or circular_doc.get("raw_extraction")
                    or "\n".join(
                        req.get("source_snippet", "")
                        for req in circular_requirements
                        if isinstance(req, dict)
                    )
                )
                findings_dicts = [f.model_dump() for f in findings]
                raw_audit = await asyncio.to_thread(
                    self.llm_service.adversarial_completeness_check,
                    circular_text,
                    findings_dicts,
                    bool(no_llm),
                )
                completeness_audit = CompletenessAudit(
                    flagged=[
                        CompletenessFlag(**flag) for flag in raw_audit.get("flagged", [])
                    ],
                    not_flagged_rationale=raw_audit.get("not_flagged_rationale"),
                    model=self.llm_service.gap_analysis_model,
                )
            except Exception as e:
                logger.warning(
                    f"Completeness audit failed for {circular_doc_id}: {e}",
                    exc_info=True,
                )
                completeness_audit = None

        return GapAnalysisResponse(
            report_id=report_id,
            circular_id=circular_doc_id,
            baseline_id=baseline_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            findings=findings,
            completeness_audit=completeness_audit,
        )
