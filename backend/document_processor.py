"""Document processing pipeline for regulatory documents."""

import logging
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
import re

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process and extract text from regulatory documents."""
    
    def __init__(self):
        self.supported_formats = [".pdf", ".txt"]
    
    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a regulatory document file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return self._process_pdf(file_path)
        elif suffix == ".txt":
            return self._process_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    
    def _process_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Extract text from PDF file."""
        logger.info(f"Processing PDF: {file_path.name}")
        
        try:
            reader = PdfReader(file_path)
            
            # Extract text from all pages
            text_chunks = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_chunks.append({
                        "page": page_num,
                        "text": text.strip()
                    })
            
            # Extract metadata
            metadata = {
                "filename": file_path.name,
                "num_pages": len(reader.pages),
                "source_type": "pdf"
            }
            
            # Try to extract document info
            if reader.metadata:
                metadata.update({
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                })
            
            return {
                "text_chunks": text_chunks,
                "metadata": metadata,
                "full_text": "\n\n".join([chunk["text"] for chunk in text_chunks])
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path.name}: {e}")
            raise
    
    def _process_text(self, file_path: Path) -> Dict[str, Any]:
        """Process plain text file."""
        logger.info(f"Processing text file: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Split into chunks by paragraphs
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            text_chunks = [
                {"page": i + 1, "text": para}
                for i, para in enumerate(paragraphs)
            ]
            
            metadata = {
                "filename": file_path.name,
                "num_pages": len(paragraphs),
                "source_type": "text"
            }
            
            return {
                "text_chunks": text_chunks,
                "metadata": metadata,
                "full_text": text
            }
            
        except Exception as e:
            logger.error(f"Error processing text file {file_path.name}: {e}")
            raise
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for better RAG performance.
        
        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end within last 100 chars
                search_text = text[end-100:end+100]
                sentence_end = max(
                    search_text.rfind('. '),
                    search_text.rfind('.\n'),
                    search_text.rfind('? '),
                    search_text.rfind('! ')
                )
                
                if sentence_end != -1:
                    end = end - 100 + sentence_end + 1
            
            chunks.append(text[start:end].strip())
            start = end - overlap
        
        return chunks
