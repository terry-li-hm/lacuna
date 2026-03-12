import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.models.schemas import JurisdictionResult, SynthesisResponse
from backend.services.gap_analysis_service import GapAnalysisService


class SynthesisService:
    def __init__(self, gap_analysis_service: GapAnalysisService):
        self.gap_service = gap_analysis_service

    async def synthesize(
        self,
        circular_ids: list[str],
        baseline_id: str,
        is_policy_baseline: bool = False,
        include_amendments: bool = False,
    ) -> SynthesisResponse:
        results = await asyncio.gather(
            *[
                self.gap_service.perform_gap_analysis(
                    circular_doc_id=circular_id,
                    baseline_id=baseline_id,
                    is_policy_baseline=is_policy_baseline,
                    include_amendments=include_amendments,
                )
                for circular_id in circular_ids
            ]
        )

        jurisdictions = [
            JurisdictionResult(
                circular_id=result.circular_id,
                jurisdiction=self._jurisdiction_for(result.circular_id),
                summary=result.summary,
                findings=result.findings,
            )
            for result in results
        ]

        generated_at = datetime.now(timezone.utc).isoformat()
        return SynthesisResponse(
            synthesis_id=f"synth_{uuid.uuid4().hex[:8]}",
            baseline_id=baseline_id,
            generated_at=generated_at,
            jurisdictions=jurisdictions,
            cross_jurisdiction_summary=self._build_summary(jurisdictions),
        )

    def _jurisdiction_for(self, circular_id: str) -> str:
        doc = self.gap_service.doc_repo.get(circular_id) or {}
        raw = (
            doc.get("jurisdiction")
            or (doc.get("metadata") or {}).get("jurisdiction")
            or circular_id[:2]
        )
        normalized = str(raw).strip()
        return normalized.upper() if len(normalized) <= 3 else normalized

    def _build_summary(self, jurisdictions: list[JurisdictionResult]) -> str:
        llm_summary = self._llm_summary(jurisdictions)
        if llm_summary:
            return llm_summary

        common_full, common_gap = self._common_status_counts(jurisdictions)
        return (
            f"{len(jurisdictions)} jurisdictions analysed. "
            f"Full compliance across all: {common_full}. "
            f"Gaps in all: {common_gap}."
        )

    def _common_status_counts(self, jurisdictions: list[JurisdictionResult]) -> tuple[int, int]:
        if not jurisdictions:
            return 0, 0

        full_sets = []
        gap_sets = []
        for jurisdiction in jurisdictions:
            full_sets.append(
                {
                    self._normalize_description(finding.description)
                    for finding in jurisdiction.findings
                    if finding.status == "Full"
                }
            )
            gap_sets.append(
                {
                    self._normalize_description(finding.description)
                    for finding in jurisdiction.findings
                    if finding.status == "Gap"
                }
            )

        common_full = set.intersection(*full_sets) if full_sets else set()
        common_gap = set.intersection(*gap_sets) if gap_sets else set()
        return len(common_full), len(common_gap)

    def _llm_summary(self, jurisdictions: list[JurisdictionResult]) -> str | None:
        extractor = getattr(self.gap_service.llm_service, "extractor", None)
        client = getattr(extractor, "client", None)
        model = getattr(extractor, "gap_analysis_model", None) or getattr(extractor, "model", None)
        if client is None or not model:
            return None

        payload = [
            {
                "circular_id": jurisdiction.circular_id,
                "jurisdiction": jurisdiction.jurisdiction,
                "summary": jurisdiction.summary,
                "findings": [
                    {
                        "description": finding.description,
                        "status": finding.status,
                    }
                    for finding in jurisdiction.findings
                ],
            }
            for jurisdiction in jurisdictions
        ]
        prompt = (
            "Given these gap analysis results across jurisdictions, summarise the key "
            "commonalities and differences in 2-3 sentences.\n\n"
            f"{json.dumps(payload, ensure_ascii=True)}"
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a regulatory compliance analyst. Summarise cross-jurisdiction "
                            "patterns crisply and avoid bullet points."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=220,
            )
        except Exception:
            return None

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return None
        return str(content).strip()

    def _normalize_description(self, description: Any) -> str:
        return " ".join(str(description or "").lower().split())
