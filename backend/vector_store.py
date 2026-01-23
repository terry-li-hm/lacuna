"""Vector database for RAG-based querying of regulatory documents."""

import logging
from typing import List, Dict, Any
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class VectorStore:
    """Manage vector embeddings and similarity search for regulatory documents."""
    
    def __init__(self, persist_dir: Path, collection_name: str = "regulatory_docs"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Regulatory document chunks"}
        )
        
        # Initialize embedding model
        logger.info("Loading embedding model...")
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logger.info("Embedding model loaded")
    
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
        logger.info(f"Adding document {doc_id} with {len(chunks)} chunks")
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
        
        # Prepare data for ChromaDB
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                **metadata,
                "doc_id": doc_id,
                "chunk_index": i,
                "chunk_text": chunk[:100]  # Store first 100 chars for preview
            }
            for i, chunk in enumerate(chunks)
        ]
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=metadatas
        )
        
        logger.info(f"Successfully added {len(chunks)} chunks for document {doc_id}")
        return len(chunks)
    
    def query(
        self,
        query_text: str,
        n_results: int = 5,
        jurisdiction: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for relevant chunks.
        
        Args:
            query_text: Query string
            n_results: Number of results to return
            jurisdiction: Optional filter by jurisdiction
            
        Returns:
            List of relevant chunks with metadata and scores
        """
        logger.info(f"Querying: '{query_text}' (jurisdiction: {jurisdiction})")
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text], show_progress_bar=False)[0]
        
        # Build where clause for filtering
        where = None
        if jurisdiction:
            where = {"jurisdiction": jurisdiction}
        
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=where
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })
        
        logger.info(f"Found {len(formatted_results)} relevant chunks")
        return formatted_results
    
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
