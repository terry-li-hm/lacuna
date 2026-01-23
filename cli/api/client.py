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
    
    def upload_document(self, file_path: Path, jurisdiction: str) -> Dict[str, Any]:
        """Upload a document for processing."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            params = {"jurisdiction": jurisdiction}
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
        n_results: int = 5
    ) -> Dict[str, Any]:
        """Query documents with semantic search."""
        payload = {
            "query": query,
            "jurisdiction": jurisdiction,
            "n_results": n_results
        }
        response = self.client.post(f"{self.base_url}/query", json=payload)
        response.raise_for_status()
        return response.json()
    
    def compare_jurisdictions(self, jurisdiction1: str, jurisdiction2: str) -> Dict[str, Any]:
        """Compare requirements between two jurisdictions."""
        payload = {
            "jurisdiction1": jurisdiction1,
            "jurisdiction2": jurisdiction2
        }
        response = self.client.post(f"{self.base_url}/compare", json=payload)
        response.raise_for_status()
        return response.json()
    
    def list_documents(self) -> Dict[str, Any]:
        """List all processed documents."""
        response = self.client.get(f"{self.base_url}/documents")
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
