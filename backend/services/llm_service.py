from typing import Any, Dict, List, Optional
from backend.requirement_extractor import RequirementExtractor


class LLMService:
    """Service to handle LLM-based operations, wrapping RequirementExtractor."""

    def __init__(self, extractor: Optional[RequirementExtractor] = None):
        self.extractor = extractor or RequirementExtractor()

    @property
    def gap_analysis_model(self) -> str:
        """Name of the model used for gap analysis and completeness checks."""
        return self.extractor.gap_analysis_model

    def extract_requirements(
        self, text: str, jurisdiction: str, force_basic: bool = False
    ) -> Dict[str, Any]:
        """Extract requirements from text using LLM or basic regex."""
        return self.extractor.extract_requirements(
            text, jurisdiction, force_basic=force_basic
        )

    def perform_gap_analysis(
        self,
        circular_req: Dict[str, Any],
        baseline_chunks: List[Dict[str, Any]],
        force_basic: bool = False,
    ) -> Dict[str, Any]:
        """Perform gap analysis between a requirement and baseline chunks."""
        return self.extractor.perform_gap_analysis(
            circular_req, baseline_chunks, force_basic=force_basic
        )

    def generate_draft_amendment(
        self,
        circular_req: Dict[str, Any],
        baseline_chunks: List[Dict[str, Any]],
        status: str,
        reasoning: str,
    ) -> str:
        """Generate suggested policy amendment language for partial/gap findings."""
        return self.extractor.generate_draft_amendment(
            circular_req,
            baseline_chunks,
            status,
            reasoning,
        )

    def adversarial_completeness_check(
        self,
        circular_text: str,
        findings: List[Dict[str, Any]],
        force_basic: bool = False,
    ) -> Dict[str, Any]:
        """Adversarial pass: find requirements in the circular not covered by findings."""
        return self.extractor.adversarial_completeness_check(
            circular_text,
            findings,
            force_basic=force_basic,
        )
