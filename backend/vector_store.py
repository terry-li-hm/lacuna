"""Vector database for RAG-based querying of regulatory documents."""

import logging
from typing import List, Dict, Any
from pathlib import Path
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class SimpleEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Deterministic, local embeddings for offline/testing use."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        import hashlib

        embeddings: List[List[float]] = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # 32 bytes -> 32 float values normalized to [0, 1]
            embeddings.append([b / 255.0 for b in digest])
        return embeddings


class VectorStore:
    """Manage vector embeddings and similarity search for regulatory documents."""
    
    def __init__(self, persist_dir: Path, collection_name: str = "regulatory_docs"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        use_in_memory = os.getenv("REG_ATLAS_IN_MEMORY") == "1"
        if use_in_memory:
            self.client = chromadb.Client(Settings(anonymized_telemetry=False))
        else:
            try:
                self.client = chromadb.PersistentClient(
                    path=str(persist_dir),
                    settings=Settings(anonymized_telemetry=False)
                )
            except Exception as exc:
                logger.warning(f"Persistent Chroma failed, falling back to in-memory: {exc}")
                self.client = chromadb.Client(Settings(anonymized_telemetry=False))
        
        use_local_embeddings = os.getenv("REG_ATLAS_NO_LLM") == "1"
        if use_local_embeddings:
            self.collection_name = f"{collection_name}_local"

        # Get or create collection
        embedding_fn = SimpleEmbeddingFunction() if use_local_embeddings else None
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Regulatory document chunks"},
            embedding_function=embedding_fn
        )
        
        # Initialize OpenAI client for embeddings via OpenRouter
        api_key = None if use_local_embeddings else os.getenv("OPENROUTER_API_KEY")
        if api_key:
            self.embedding_client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            self.embedding_model = "openai/text-embedding-3-small"
            logger.info(f"Using OpenRouter for embeddings ({self.embedding_model})")
        elif use_local_embeddings:
            self.embedding_client = None
            logger.info("Using deterministic local embeddings (REG_ATLAS_NO_LLM=1)")
        else:
            self.embedding_client = None
            logger.warning("No OpenRouter API key - using ChromaDB default embeddings")
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenRouter."""
        if not self.embedding_client:
            return None
        
        try:
            response = self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return None
    
    def add_document(
        self,
        doc_id: str,
        chunks: List[str],
        metadata: Dict[str, Any]
    ) -> int:
        """
        Add a document's chunks to the vector store.
        
        Args:
            doc_id: Unique identifier for the document
            chunks: List of text chunks from the document
            metadata: Document metadata (jurisdiction, filename, etc.)
            
        Returns:
            Number of chunks added
        """
        cleaned_chunks = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
        logger.info(f"Adding document {doc_id} with {len(cleaned_chunks)} chunks")
        
        # Generate embeddings
        if self.embedding_client:
            embeddings = self._generate_embeddings(cleaned_chunks)
        else:
            embeddings = None  # ChromaDB will use default
        
        # Prepare data for ChromaDB
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(cleaned_chunks))]
        metadatas = [
            {
                **{k: str(v) for k, v in metadata.items()},  # Convert all values to strings
                "doc_id": doc_id,
                "chunk_index": str(i),
                "chunk_text": chunk[:100]
            }
            for i, chunk in enumerate(cleaned_chunks)
        ]
        
        # Add to collection
        if embeddings:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=cleaned_chunks,
                metadatas=metadatas
            )
        else:
            # ChromaDB will generate embeddings automatically
            self.collection.add(
                ids=ids,
                documents=cleaned_chunks,
                metadatas=metadatas
            )
        
        logger.info(f"Successfully added {len(cleaned_chunks)} chunks for document {doc_id}")
        return len(cleaned_chunks)
    
    def query(
        self,
        query_text: str,
        n_results: int = 5,
        jurisdiction: str | None = None,
        filters: Dict[str, str] | None = None,
        max_distance: float | None = None
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for relevant chunks.
        
        Args:
            query_text: Query string
            n_results: Number of results to return
            jurisdiction: Optional filter by jurisdiction
            filters: Optional additional filters
            max_distance: Optional distance threshold (lower is better)
            
        Returns:
            List of relevant chunks with metadata and scores
        """
        logger.info(f"Querying: '{query_text}' (jurisdiction: {jurisdiction})")
        
        # Generate query embedding
        query_embeddings = None
        if self.embedding_client:
            query_embeddings = self._generate_embeddings([query_text])
            if not query_embeddings:
                logger.warning("Embedding generation failed, falling back to text query")
        
        # Build where clause for filtering
        where = None
        if jurisdiction:
            where = {"jurisdiction": jurisdiction}
        if filters:
            if where:
                # ChromaDB requires $and for multiple conditions if not using simple dict
                if len(filters) == 1 and "jurisdiction" not in filters:
                    where = {"$and": [where, filters]}
                else:
                    where = {"$and": [where] + [{k: v} for k, v in filters.items()]}
            else:
                where = filters
        
        # Query collection
        if query_embeddings:
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where
            )
        else:
            # Use text-based query (ChromaDB default)
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
        
        # Format results
        formatted_results = []
        if results and results.get('ids') and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                distance = results.get('distances', [[]])[0][i] if results.get('distances') else None
                
                # Apply distance threshold if provided
                if max_distance is not None and distance is not None and distance > max_distance:
                    continue
                    
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": distance
                })
        
        logger.info(f"Found {len(formatted_results)} relevant chunks")
        return formatted_results

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve specific chunks by their IDs."""
        if not ids:
            return []
        try:
            results = self.collection.get(ids=ids)
            formatted = []
            if results and results.get('ids'):
                for i in range(len(results['ids'])):
                    formatted.append({
                        "id": results['ids'][i],
                        "document": results['documents'][i],
                        "metadata": results['metadatas'][i]
                    })
            return formatted
        except Exception as e:
            logger.error(f"Error fetching chunks by IDs: {e}")
            return []
    
    def get_document_count(self) -> int:
        """Get total number of document chunks in the store."""
        return self.collection.count()
    
    def list_jurisdictions(self) -> List[str]:
        """Get list of unique jurisdictions in the store."""
        # Get all metadata
        all_items = self.collection.get()
        
        if not all_items['metadatas']:
            return []
        
        jurisdictions = set()
        for metadata in all_items['metadatas']:
            if 'jurisdiction' in metadata:
                jurisdictions.add(metadata['jurisdiction'])
        
        return sorted(list(jurisdictions))
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks for a specific document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if successful
        """
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(where={"doc_id": doc_id})
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} chunks for document {doc_id}")
                return True
            else:
                logger.warning(f"No chunks found for document {doc_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    def clear_collection(self) -> bool:
        """Clear all documents from the collection."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Regulatory document chunks"}
            )
            logger.info(f"Cleared collection {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            return False
