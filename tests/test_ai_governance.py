"""Tests for AI governance requirement extraction categories."""

import pytest
from backend.requirement_extractor import RequirementExtractor


AI_GOVERNANCE_CATEGORIES = [
    "Model Governance",
    "AI Safety & Robustness",
    "Fairness & Bias",
    "Transparency & Explainability",
    "Data Quality & Privacy",
    "Human Oversight",
    "Risk Management",
    "Accountability & Audit",
    "Consumer Protection",
    "Reporting & Disclosure",
]


def test_extraction_prompt_includes_ai_governance_categories():
    """Extraction prompt should list AI governance categories alongside banking ones."""
    extractor = RequirementExtractor(api_key=None)
    prompt = extractor._build_extraction_prompt("dummy text", "Hong Kong")
    for category in AI_GOVERNANCE_CATEGORIES:
        assert category.lower() in prompt.lower(), (
            f"Missing AI governance category: {category}"
        )


def test_extraction_prompt_still_includes_banking_categories():
    """Ensure we don't remove existing banking categories."""
    extractor = RequirementExtractor(api_key=None)
    prompt = extractor._build_extraction_prompt("dummy text", "Hong Kong")
    for category in ["Capital Adequacy", "Liquidity", "AML/KYC"]:
        assert category.lower() in prompt.lower(), (
            f"Missing banking category: {category}"
        )
