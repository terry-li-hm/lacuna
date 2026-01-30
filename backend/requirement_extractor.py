"""LLM-based requirement extraction from regulatory documents."""

import logging
from typing import List, Dict, Any
import os
import uuid
from openai import OpenAI

logger = logging.getLogger(__name__)


class RequirementExtractor:
    """Extract and categorize regulatory requirements using LLM."""
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-3.5-turbo",
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        if os.getenv("REG_ATLAS_NO_LLM") == "1":
            api_key = None
        self.api_key = api_key
        self.model = model
        self.client = None
        
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"Initialized OpenRouter client with model: {model}")
        else:
            logger.warning("No OpenRouter API key provided - extraction features limited")
    
    def extract_requirements(
        self,
        text: str,
        jurisdiction: str = "Unknown",
        force_basic: bool = False
    ) -> Dict[str, Any]:
        """
        Extract regulatory requirements from text.
        
        Args:
            text: Text to analyze
            jurisdiction: Regulatory jurisdiction (e.g., "Hong Kong", "Singapore")
            
        Returns:
            Dictionary containing extracted requirements and categories
        """
        if force_basic or not self.client:
            logger.warning("No LLM client available - returning basic extraction")
            return self._basic_extraction(text, jurisdiction)
        
        try:
            prompt = f"""Analyze the following regulatory text from {jurisdiction} and extract key requirements.

For each requirement, identify:
1. Requirement type (e.g., Capital Adequacy, Liquidity, AML/KYC, Reporting, Governance)
2. Brief description of the requirement
3. Any specific thresholds, ratios, or deadlines mentioned
4. Whether it's mandatory or recommended
5. Confidence level (High/Medium/Low)
6. A short source snippet (<= 200 chars) quoted from the text

Text:
{text[:4000]}  # Limit context length

Provide output in the following structured format:
REQUIREMENT_TYPE: [type]
DESCRIPTION: [brief description]
DETAILS: [specific numbers, dates, thresholds]
MANDATORY: [Yes/No]
CONFIDENCE: [High/Medium/Low]
SOURCE_SNIPPET: [quoted excerpt]
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
            ] or [
                {
                    "requirement_type": "General Compliance",
                    "description": "Regulatory requirements detected (LLM disabled)",
                    "details": "No keyword match found in basic extraction",
                    "mandatory": "Unknown"
                }
            ],
            "raw_extraction": "Basic extraction performed (no LLM available)"
        }
    
    def compare_requirements(
        self,
        req1: Dict[str, Any],
        req2: Dict[str, Any],
        force_basic: bool = False
    ) -> str:
        """
        Compare requirements from two jurisdictions.
        
        Args:
            req1: Requirements from first jurisdiction
            req2: Requirements from second jurisdiction
            
        Returns:
            Comparison summary
        """
        if force_basic or not self.client:
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
    
    def perform_gap_analysis(
        self,
        circular_req: Dict[str, Any],
        baseline_chunks: List[Dict[str, Any]],
        force_basic: bool = False
    ) -> Dict[str, Any]:
        """
        Perform a gap analysis for a single requirement against baseline context.
        
        Args:
            circular_req: The requirement from the new circular
            baseline_chunks: Relevant chunks from the baseline document/policy
            force_basic: Whether to skip LLM
            
        Returns:
            Dictionary with status, reasoning, and verified citations
        """
        if force_basic or not self.client:
            return {
                "status": "Partial",
                "reasoning": "Gap analysis performed without LLM. Manual review required.",
                "citations": []
            }

        try:
            # Format baseline chunks with indices for "Inject-and-Verify"
            context_text = ""
            for i, chunk in enumerate(baseline_chunks):
                text = chunk.get('document', '')
                context_text += f"<chunk index=\"{i}\">\n{text}\n</chunk>\n"

            prompt = f"""You are a Senior Regulatory Auditor. Perform a gap analysis.

Circular Requirement: {circular_req.get('description', 'No description')}
Details: {circular_req.get('details', 'No specific details')}

Baseline Context:
{context_text}

Evaluation Criteria:
- Full Coverage: Baseline explicitly meets all conditions, thresholds, and deadlines.
- Partial Coverage: Baseline addresses intent but lacks granular details or specific thresholds.
- Gap: Baseline is silent or contradicts the requirement.

Rules:
1. Cite index in square brackets, e.g., [0], [1].
2. If no coverage exists, status is 'Gap'.
3. Output valid JSON only.

Response Format:
{{
  "status": "Full" | "Partial" | "Gap",
  "reasoning": "Provide exact delta or alignment details",
  "citations": [list of index integers]
}}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance auditor. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            result_text = response.choices[0].message.content or "{}"
            
            # Simple JSON extraction in case of markdown wrapping
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            import json
            result = json.loads(result_text)
            
            # Map indices back to chunk IDs and enrich citations
            verified_provenance = []
            for idx in result.get("citations", []):
                try:
                    idx_int = int(idx)
                    if 0 <= idx_int < len(baseline_chunks):
                        chunk = baseline_chunks[idx_int]
                        verified_provenance.append({
                            "id": f"cit_{uuid.uuid4().hex[:8]}",
                            "source_type": "baseline",
                            "doc_id": chunk.get("metadata", {}).get("doc_id", "unknown"),
                            "chunk_id": chunk.get("id", "unknown"),
                            "text_segment": chunk.get("document", "")[:500],
                            "verification_status": "verified"
                        })
                except (ValueError, TypeError):
                    continue
            
            result["provenance"] = verified_provenance
            return result

        except Exception as e:
            logger.error(f"Error in gap analysis: {e}")
            return {
                "status": "Gap",
                "reasoning": f"Error during analysis: {str(e)}",
                "provenance": []
            }

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
