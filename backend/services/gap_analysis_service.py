import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.storage.repositories import DocumentRepository, PolicyRepository
from backend.vector_store import VectorStore
from backend.services.llm_service import LLMService
from langgraph.checkpoint.memory import MemorySaver
from backend.services.gap_graph import build_gap_graph
from backend.models.schemas import (
    CompletenessAudit,
    CompletenessFlag,
    GapAnalysisResponse,
    GapRequirementMapping,
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
        self.gap_graph = build_gap_graph(checkpointer=MemorySaver())

    def _detect_checkpoint_db_path(self) -> str | None:
        # Kept for future SQLite persistence — currently unused (MemorySaver is always active)
        local_path = None  # placeholder
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return str(local_path)

    def _make_response(
        self,
        report_id: str,
        circular_doc_id: str,
        baseline_id: str,
        findings: list[GapRequirementMapping],
        *,
        completeness_audit: CompletenessAudit | None = None,
        status: str = "completed",
    ) -> GapAnalysisResponse:
        summary = {"Full": 0, "Partial": 0, "Gap": 0}
        for finding in findings:
            summary[finding.status] = summary.get(finding.status, 0) + 1

        return GapAnalysisResponse(
            report_id=report_id,
            circular_id=circular_doc_id,
            baseline_id=baseline_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            summary=summary,
            findings=findings,
            completeness_audit=completeness_audit,
        )

    @staticmethod
    def _normalize_findings(raw_findings: list[Any]) -> list[GapRequirementMapping]:
        return [
            finding
            if isinstance(finding, GapRequirementMapping)
            else GapRequirementMapping.model_validate(finding)
            for finding in raw_findings
        ]

    async def perform_gap_analysis(
        self,
        circular_doc_id: str,
        baseline_id: str,
        is_policy_baseline: bool = False,
        include_amendments: bool = False,
        use_confirmed: bool = False,
        confirm_repo: Any = None,
        include_completeness_audit: bool = False,
        interactive: bool = False,
        no_llm: bool = False,
    ) -> GapAnalysisResponse:
        """Perform a gap analysis between a circular document and a baseline."""

        # 1. Verify Circular Document exists
        circular_doc = self.doc_repo.get(circular_doc_id)
        if not circular_doc:
            raise ValueError(f"Circular document {circular_doc_id} not found")

        if use_confirmed:
            repo = confirm_repo
            if repo is None:
                raise ValueError("Confirmed requirement repository is required when use_confirmed=true")
            confirmed = repo.get(circular_doc_id)
            if not confirmed:
                raise ValueError(
                    f"No confirmed requirement list for {circular_doc_id}. Run 'lacuna confirm' first."
                )
            circular_requirements = confirmed.get("requirements", [])
        else:
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

        report_id = f"gap_{uuid.uuid4().hex[:8]}"
        graph_input = {
            "circular_doc_id": circular_doc_id,
            "baseline_id": baseline_id,
            "requirements": circular_requirements,
            "current_req": None,
            "findings": [],
            "interactive": interactive,
            "include_amendments": include_amendments,
            "no_llm": bool(no_llm),
        }
        graph_config = {
            "configurable": {
                "thread_id": report_id,
                "vector_store": self.vector_store,
                "llm_service": self.llm_service,
            }
        }

        completeness_audit = None
        result = await self.gap_graph.ainvoke(graph_input, config=graph_config)
        # In LangGraph 1.1, interrupt() returns __interrupt__ in the result dict
        # rather than raising GraphInterrupt. Check for that key.
        interrupted = bool(result.get("__interrupt__"))
        findings = self._normalize_findings(result.get("findings", []))

        if include_completeness_audit and not interrupted:
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

        return self._make_response(
            report_id=report_id,
            circular_doc_id=circular_doc_id,
            baseline_id=baseline_id,
            findings=findings,
            completeness_audit=completeness_audit,
            status="interrupted" if interrupted else "completed",
        )

    async def resume_gap_analysis(
        self,
        thread_id: str,
        override_findings: list[dict] | None = None,
    ) -> GapAnalysisResponse:
        if False:  # MemorySaver always active
            raise ValueError("Checkpointing is not enabled")

        config = {
            "configurable": {
                "thread_id": thread_id,
                "vector_store": self.vector_store,
                "llm_service": self.llm_service,
            }
        }
        snapshot = await self.gap_graph.aget_state(config)
        values = getattr(snapshot, "values", None) or {}
        if not values:
            raise ValueError(f"No paused analysis found for thread {thread_id}")

        if override_findings is not None:
            findings = self._normalize_findings(override_findings)
            await self.gap_graph.aupdate_state(config, {"findings": findings})

        result = await self.gap_graph.ainvoke(None, config=config)
        findings = self._normalize_findings(result["findings"])

        return self._make_response(
            report_id=thread_id,
            circular_doc_id=result["circular_doc_id"],
            baseline_id=result["baseline_id"],
            findings=findings,
            status="completed",
        )
