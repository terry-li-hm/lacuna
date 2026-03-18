"""API client for RegAtlas."""

import httpx
from typing import Dict, Any, Optional
from pathlib import Path


class RegAtlasClient:
    """Client for interacting with RegAtlas API."""
    
    def __init__(self, base_url: str = "https://reg-atlas.onrender.com", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def health(self) -> Dict[str, Any]:
        """Check API health status."""
        response = self.client.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json()
    
    def stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        response = self.client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def upload_document(
        self,
        file_path: Path,
        jurisdiction: str,
        no_llm: bool = False
    ) -> Dict[str, Any]:
        """Upload a document for processing."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            params = {"jurisdiction": jurisdiction}
            if no_llm:
                params["no_llm"] = "true"
            response = self.client.post(
                f"{self.base_url}/upload",
                files=files,
                params=params
            )
        response.raise_for_status()
        return response.json()
    
    def query_documents(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        n_results: int = 5,
        no_llm: bool = False
    ) -> Dict[str, Any]:
        """Query documents with semantic search."""
        payload = {
            "query": query,
            "jurisdiction": jurisdiction,
            "n_results": n_results,
            "no_llm": no_llm
        }
        response = self.client.post(f"{self.base_url}/query", json=payload)
        response.raise_for_status()
        return response.json()
    
    def compare_jurisdictions(
        self,
        jurisdiction1: str,
        jurisdiction2: str,
        no_llm: bool = False
    ) -> Dict[str, Any]:
        """Compare requirements between two jurisdictions."""
        payload = {
            "jurisdiction1": jurisdiction1,
            "jurisdiction2": jurisdiction2,
            "no_llm": no_llm
        }
        response = self.client.post(f"{self.base_url}/compare", json=payload)
        response.raise_for_status()
        return response.json()
    
    def list_documents(self) -> Dict[str, Any]:
        """List all processed documents."""
        response = self.client.get(f"{self.base_url}/documents")
        response.raise_for_status()
        return response.json()

    def list_requirements(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List requirements with optional filters."""
        response = self.client.get(f"{self.base_url}/requirements", params=params or {})
        response.raise_for_status()
        return response.json()

    def requirements_stats(self) -> Dict[str, Any]:
        """Get requirement stats."""
        response = self.client.get(f"{self.base_url}/requirements/stats")
        response.raise_for_status()
        return response.json()

    def gap_analysis(
        self,
        circular_doc_id: str,
        baseline_id: str,
        is_policy_baseline: bool = False,
        include_completeness_audit: bool = False,
        use_confirmed: bool = False,
        no_llm: bool = False
    ) -> Dict[str, Any]:
        """Perform gap analysis between circular and baseline."""
        payload = {
            "circular_doc_id": circular_doc_id,
            "baseline_id": baseline_id,
            "is_policy_baseline": is_policy_baseline,
            "include_completeness_audit": include_completeness_audit,
            "use_confirmed": use_confirmed,
            "no_llm": no_llm
        }
        response = self.client.post(f"{self.base_url}/gap-analysis", json=payload)
        response.raise_for_status()
        return response.json()

    def decompose(self, doc_id: str, fresh: bool = False) -> Dict[str, Any]:
        """List atomic requirements for a given document."""
        response = self.client.post(
            f"{self.base_url}/decompose",
            json={"doc_id": doc_id, "fresh": fresh},
            timeout=300 if fresh else 30,
        )
        response.raise_for_status()
        return response.json()

    def save_confirmed(
        self,
        doc_id: str,
        requirements: list,
        confirmed_by: str | None = None,
    ) -> Dict[str, Any]:
        """Save a confirmed requirement list for a document."""
        response = self.client.post(
            f"{self.base_url}/confirm/{doc_id}",
            json={"requirements": requirements, "confirmed_by": confirmed_by},
        )
        response.raise_for_status()
        return response.json()

    def get_confirmed(self, doc_id: str) -> Dict[str, Any]:
        """Get confirmed requirement list by document ID."""
        response = self.client.get(f"{self.base_url}/confirm/{doc_id}")
        response.raise_for_status()
        return response.json()

    def list_policies(self) -> Dict[str, Any]:
        """List all internal policies."""
        response = self.client.get(f"{self.base_url}/policies")
        response.raise_for_status()
        return response.json()

    def upload_policy(
        self,
        file_path: Path,
        title: str | None = None,
        owner: str | None = None,
    ) -> Dict[str, Any]:
        """Upload an internal policy document."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            params = {}
            if title:
                params["title"] = title
            if owner:
                params["owner"] = owner
            response = self.client.post(
                f"{self.base_url}/policies/upload",
                files=files,
                params=params,
                timeout=120,
            )
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP client."""
        self.client.close()
