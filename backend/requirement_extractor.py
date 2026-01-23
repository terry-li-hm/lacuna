"""LLM-based requirement extraction from regulatory documents."""

import logging
from typing import List, Dict, Any
import os
from openai import OpenAI

logger = logging.getLogger(__name__)


class RequirementExtractor:
    """Extract and categorize regulatory requirements using LLM."""
    
    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.client = None
        
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info(f"Initialized OpenRouter client with model: {model}")
        else:
            logger.warning("No OpenRouter API key provided - extraction features limited")
    
    def extract_requirements(self, text: str, jurisdiction: str = "Unknown") -> Dict[str, Any]:
        """
        Extract regulatory requirements from text.
        
        Args:
            text: Text to analyze
            jurisdiction: Regulatory jurisdiction (e.g., "Hong Kong", "Singapore")
            
        Returns:
            Dictionary containing extracted requirements and categories
        """
        if not self.client:
            logger.warning("No LLM client available - returning basic extraction")
            return self._basic_extraction(text, jurisdiction)
        
        try:
            prompt = f"""Analyze the following regulatory text from {jurisdiction} and extract key requirements.

For each requirement, identify:
1. Requirement type (e.g., Capital Adequacy, Liquidity, AML/KYC, Reporting, Governance)
2. Brief description of the requirement
3. Any specific thresholds, ratios, or deadlines mentioned
4. Whether it's mandatory or recommended

Text:
{text[:4000]}  # Limit context length

Provide output in the following structured format:
REQUIREMENT_TYPE: [type]
DESCRIPTION: [brief description]
DETAILS: [specific numbers, dates, thresholds]
MANDATORY: [Yes/No]
---
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance expert specializing in financial services regulations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            extracted_text = response.choices[0].message.content or ""
            requirements = self._parse_extraction(extracted_text, jurisdiction)
            
            return {
                "jurisdiction": jurisdiction,
                "requirements": requirements,
                "raw_extraction": extracted_text
            }
            
        except Exception as e:
            logger.error(f"Error extracting requirements: {e}")
            return self._basic_extraction(text, jurisdiction)
    
    def _parse_extraction(self, text: str, jurisdiction: str) -> List[Dict[str, str]]:
        """Parse LLM output into structured requirements."""
        requirements = []
        
        # Split by requirement separator
        req_blocks = text.split('---')
        
        for block in req_blocks:
            if not block.strip():
                continue
            
            req = {"jurisdiction": jurisdiction}
            
            # Extract fields
            lines = block.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    req[key] = value.strip()
            
            if 'requirement_type' in req:
                requirements.append(req)
        
        return requirements
    
    def _basic_extraction(self, text: str, jurisdiction: str) -> Dict[str, Any]:
        """Fallback extraction when no LLM is available."""
        # Simple keyword-based extraction
        keywords = {
            "Capital Adequacy": ["capital ratio", "CET1", "tier 1", "total capital"],
            "Liquidity": ["liquidity coverage", "LCR", "NSFR", "liquid assets"],
            "AML/KYC": ["anti-money laundering", "AML", "know your customer", "KYC", "CDD"],
            "Reporting": ["report", "disclosure", "submission", "filing"],
            "Governance": ["board", "risk management", "internal control", "governance"]
        }
        
        text_lower = text.lower()
        found_categories = []
        
        for category, terms in keywords.items():
            if any(term.lower() in text_lower for term in terms):
                found_categories.append(category)
        
        return {
            "jurisdiction": jurisdiction,
            "requirements": [
                {
                    "requirement_type": cat,
                    "description": f"Document contains {cat} requirements",
                    "details": "Extracted using basic keyword matching",
                    "mandatory": "Unknown"
                }
                for cat in found_categories
            ],
            "raw_extraction": "Basic extraction performed (no LLM available)"
        }
    
    def compare_requirements(
        self,
        req1: Dict[str, Any],
        req2: Dict[str, Any]
    ) -> str:
        """
        Compare requirements from two jurisdictions.
        
        Args:
            req1: Requirements from first jurisdiction
            req2: Requirements from second jurisdiction
            
        Returns:
            Comparison summary
        """
        if not self.client:
            return self._basic_comparison(req1, req2)
        
        try:
            j1 = req1.get("jurisdiction", "Jurisdiction 1")
            j2 = req2.get("jurisdiction", "Jurisdiction 2")
            
            prompt = f"""Compare the regulatory requirements between {j1} and {j2}.

{j1} Requirements:
{self._format_requirements(req1.get("requirements", []))}

{j2} Requirements:
{self._format_requirements(req2.get("requirements", []))}

Provide a concise comparison highlighting:
1. Common requirements across both jurisdictions
2. Key differences
3. Stricter requirements in each jurisdiction
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance expert specializing in cross-border financial regulations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            return response.choices[0].message.content or "No comparison available"
            
        except Exception as e:
            logger.error(f"Error comparing requirements: {e}")
            return self._basic_comparison(req1, req2)
    
    def _format_requirements(self, requirements: List[Dict[str, str]]) -> str:
        """Format requirements for LLM prompt."""
        if not requirements:
            return "No requirements extracted"
        
        formatted = []
        for req in requirements[:10]:  # Limit to prevent token overflow
            req_type = req.get("requirement_type", "Unknown")
            desc = req.get("description", "No description")
            formatted.append(f"- {req_type}: {desc}")
        
        return "\n".join(formatted)
    
    def _basic_comparison(self, req1: Dict[str, Any], req2: Dict[str, Any]) -> str:
        """Basic comparison without LLM."""
        j1 = req1.get("jurisdiction", "Jurisdiction 1")
        j2 = req2.get("jurisdiction", "Jurisdiction 2")
        
        types1 = set(r.get("requirement_type", "") for r in req1.get("requirements", []))
        types2 = set(r.get("requirement_type", "") for r in req2.get("requirements", []))
        
        common = types1 & types2
        only1 = types1 - types2
        only2 = types2 - types1
        
        result = f"Comparison between {j1} and {j2}:\n\n"
        result += f"Common requirement types: {', '.join(common) if common else 'None'}\n"
        result += f"Only in {j1}: {', '.join(only1) if only1 else 'None'}\n"
        result += f"Only in {j2}: {', '.join(only2) if only2 else 'None'}\n"
        
        return result
