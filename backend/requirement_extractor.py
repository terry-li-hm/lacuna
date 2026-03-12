"""LLM-based requirement extraction from regulatory documents."""

import json
import logging
from typing import List, Dict, Any
import os
import uuid
from openai import OpenAI

logger = logging.getLogger(__name__)


def _extract_json_from_llm_response(text: str) -> str:
    """
    Strip markdown fences and leading/trailing prose from an LLM response to isolate raw JSON.

    Handles:
    - ```json ... ``` fences
    - ``` ... ``` fences
    - Preamble text before the first '{' or '['
    - Trailing text after the JSON object (uses raw_decode to stop at first complete value)
    """
    text = text.strip()
    # Strip markdown fences first (handles preamble + fence in one pass)
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    # If there is still leading prose before the JSON object/array, trim it
    for start_char in ('{', '['):
        idx = text.find(start_char)
        if idx > 0:
            text = text[idx:]
            break
    # Use raw_decode to stop at first complete JSON value — tolerates trailing content
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return json.dumps(obj)
    except json.JSONDecodeError:
        return text


def _format_not_flagged(not_flagged: list) -> str:
    """Render the structured not_flagged list into a human-readable rationale string."""
    if not not_flagged:
        return "No candidates were considered and rejected."
    parts = []
    for item in not_flagged:
        if isinstance(item, dict):
            candidate = item.get("candidate", "Unknown")
            reason = item.get("reason_excluded", "No reason given")
            parts.append(f"Considered '{candidate}' but excluded: {reason}")
    return " | ".join(parts) if parts else "No candidates were considered and rejected."


class RequirementExtractor:
    """Extract and categorize regulatory requirements using LLM."""
    
    CHUNK_SIZE = 12000  # chars per extraction window
    CHUNK_OVERLAP = 500  # overlap between windows

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-4o-mini",
        gap_analysis_model: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        if os.getenv("REG_ATLAS_NO_LLM") == "1":
            api_key = None
        self.api_key = api_key
        self.model = model
        self.gap_analysis_model = gap_analysis_model or model
        self.client = None

        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info(f"Initialized OpenRouter client with model: {model}, gap analysis: {self.gap_analysis_model}")
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
            # Process document in chunks to handle long texts
            chunks = self._chunk_text(text)
            all_requirements = []
            raw_parts = []

            for i, chunk in enumerate(chunks):
                chunk_label = f" (section {i+1}/{len(chunks)})" if len(chunks) > 1 else ""
                prompt = f"""Analyze the following regulatory text from {jurisdiction}{chunk_label} and extract key requirements.

For each requirement, identify:
1. Requirement type (e.g., Capital Adequacy, Liquidity, AML/KYC, Reporting, Governance, AI/Technology, Consumer Protection, Data Privacy, Risk Management)
2. Brief description of the requirement
3. Any specific thresholds, ratios, or deadlines mentioned
4. Whether it's mandatory or recommended
5. Confidence level (High/Medium/Low)
6. A short source snippet (<= 200 chars) quoted from the text

Text:
{chunk}

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
                    max_tokens=2000
                )

                extracted_text = response.choices[0].message.content or ""
                raw_parts.append(extracted_text)
                all_requirements.extend(self._parse_extraction(extracted_text, jurisdiction))

            # Deduplicate by description similarity
            requirements = self._deduplicate_requirements(all_requirements)

            return {
                "jurisdiction": jurisdiction,
                "requirements": requirements,
                "raw_extraction": "\n---\n".join(raw_parts)
            }
            
        except Exception as e:
            logger.error(f"Error extracting requirements: {e}")
            return self._basic_extraction(text, jurisdiction)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks for processing."""
        if len(text) <= self.CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.CHUNK_SIZE
            # Try to break at a paragraph or sentence boundary
            if end < len(text):
                for boundary in ["\n\n", ".\n", ". ", "\n"]:
                    last = text.rfind(boundary, start + self.CHUNK_SIZE // 2, end)
                    if last != -1:
                        end = last + len(boundary)
                        break
            chunks.append(text[start:end])
            start = end - self.CHUNK_OVERLAP
        return chunks

    def _deduplicate_requirements(self, requirements: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove near-duplicate requirements based on description overlap."""
        if len(requirements) <= 1:
            return requirements
        seen_descriptions = []
        unique = []
        for req in requirements:
            desc = (req.get("description") or "").lower().strip()
            if not desc:
                unique.append(req)
                continue
            is_dup = False
            for seen in seen_descriptions:
                # Simple word overlap check
                words_new = set(desc.split())
                words_seen = set(seen.split())
                if len(words_new) == 0:
                    break
                overlap = len(words_new & words_seen) / max(len(words_new), len(words_seen))
                if overlap > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                seen_descriptions.append(desc)
                unique.append(req)
        return unique

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
                model=self.gap_analysis_model,
                messages=[
                    {"role": "system", "content": "You are a regulatory compliance auditor. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )

            result_text = response.choices[0].message.content or "{}"
            result_text = _extract_json_from_llm_response(result_text)
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

    def adversarial_completeness_check(
        self,
        circular_text: str,
        findings: List[Dict[str, Any]],
        force_basic: bool = False,
    ) -> Dict[str, Any]:
        """
        Adversarial pass: find requirements in the circular that are not covered by findings.
        Returns at most 5 flagged items and rationale for what was not flagged.
        """
        if force_basic or not self.client:
            return {
                "flagged": [],
                "not_flagged_rationale": "Adversarial completeness audit unavailable (LLM disabled).",
            }

        try:
            findings_lines: List[str] = []
            for idx, finding in enumerate(findings, 1):
                desc = (finding.get("description") or "No description").strip()
                status = (finding.get("status") or "Unknown").strip()
                reasoning = (finding.get("reasoning") or "").strip()
                findings_lines.append(
                    f"{idx}. [{status}] {desc}"
                    + (f" | reasoning: {reasoning}" if reasoning else "")
                )
            formatted_findings = (
                "\n".join(findings_lines) if findings_lines else "No findings available."
            )

            prompt = f"""You are an adversarial regulatory auditor. Your sole job is to find requirements in the circular that were MISSED by the existing gap analysis.

CRITICAL RULES — read before responding:
1. HARD CAP: Output AT MOST 5 flagged items. If you identify more than 5 candidates, rank by severity and keep only the top 5.
2. ANTI-HALLUCINATION: Every flagged item MUST include a `source_quote` field containing a verbatim excerpt (≤100 characters) copied character-for-character from the circular text below. Do not paraphrase or reconstruct — copy exactly.
3. FALSE-POSITIVE SUPPRESSION: If every material requirement is already covered by the findings, you MUST return an empty `flagged` list and say so explicitly. Do NOT invent omissions. It is correct and acceptable to flag zero items.
4. NOT-FLAGGED RATIONALE: You MUST provide a `not_flagged` array listing 2–3 requirements you considered but rejected, each with a one-sentence reason. This field is required even when `flagged` is empty.
5. OUTPUT FORMAT: Return strict JSON only — no preamble, no markdown, no trailing commentary.

Circular text (truncated to 8000 chars):
{(circular_text or "")[:8000]}

Requirements already analyzed ({len(findings)} items):
{formatted_findings}

Required JSON schema (all fields mandatory):
{{
  "flagged": [
    {{
      "description": "concise statement of the missed requirement",
      "reasoning": "why this was not covered by any finding above",
      "source_quote": "verbatim excerpt ≤100 chars from circular text"
    }}
  ],
  "not_flagged": [
    {{
      "candidate": "brief label of what was considered",
      "reason_excluded": "one sentence explaining why it was not flagged"
    }}
  ]
}}
"""

            response = self.client.chat.completions.create(
                model=self.gap_analysis_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a regulatory compliance auditor. Return strict JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1400,
            )

            result_text = response.choices[0].message.content or "{}"
            result_text = _extract_json_from_llm_response(result_text)

            try:
                parsed = json.loads(result_text)
            except json.JSONDecodeError as parse_err:
                logger.warning(f"Adversarial check: JSON parse failed ({parse_err}), returning safe default")
                return {
                    "flagged": [],
                    "not_flagged": [],
                    "not_flagged_rationale": f"Response could not be parsed as JSON: {parse_err}",
                }

            flagged = parsed.get("flagged", [])
            if not isinstance(flagged, list):
                flagged = []
            # Enforce source_quote field presence; drop items that lack it to prevent hallucination
            validated_flagged = [
                item for item in flagged
                if isinstance(item, dict) and item.get("source_quote", "").strip()
            ]
            not_flagged = parsed.get("not_flagged", [])
            if not isinstance(not_flagged, list):
                not_flagged = []
            return {
                "flagged": validated_flagged[:5],
                "not_flagged": not_flagged,
                # Keep legacy key for backwards compatibility with callers that read this field
                "not_flagged_rationale": parsed.get("not_flagged_rationale") or _format_not_flagged(not_flagged),
            }
        except Exception as e:
            logger.error(f"Error in adversarial completeness check: {e}")
            return {
                "flagged": [],
                "not_flagged": [],
                "not_flagged_rationale": f"Adversarial completeness check failed: {e}",
            }

    def generate_draft_amendment(
        self,
        circular_req: Dict[str, Any],
        baseline_chunks: List[Dict[str, Any]],
        status: str,
        reasoning: str
    ) -> str:
        """Generate concise policy amendment language for partial/gap findings."""
        if not self.client:
            return ""

        try:
            context_text = ""
            for chunk in baseline_chunks:
                text = chunk.get("document", "")
                if text:
                    context_text += f"- {text[:1200]}\n"

            prompt = f"""You are a policy drafting assistant. Given a regulatory requirement that is {status} covered by an existing policy, write a concise policy amendment (2-4 sentences) in formal governance language that would close the coverage gap. The amendment should be specific to the requirement, directly actionable, and ready for insertion into a policy document.

Regulatory Requirement:
{circular_req.get('description', 'No description')}

Requirement Details:
{circular_req.get('details', 'No specific details')}

Current Gap Reasoning:
{reasoning}

Relevant Baseline Context:
{context_text if context_text else "No baseline context available"}
"""

            response = self.client.chat.completions.create(
                model=self.gap_analysis_model,
                messages=[
                    {"role": "system", "content": "You are a governance policy drafting expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )

            return (response.choices[0].message.content or "").strip()

        except Exception as e:
            logger.error(f"Error generating draft amendment: {e}")
            return ""

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
