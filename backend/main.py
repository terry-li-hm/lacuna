"""FastAPI application for regulatory analytics tool."""

import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid

from .config import settings
from .document_processor import DocumentProcessor
from .requirement_extractor import RequirementExtractor
from .vector_store import VectorStore

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="RegAtlas",
    description="Cross-jurisdiction regulatory analytics platform for financial institutions",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
doc_processor = DocumentProcessor()
req_extractor = RequirementExtractor(
    api_key=settings.openrouter_api_key,
    model=settings.llm_model
)
vector_store = VectorStore(settings.chroma_persist_dir)

# Store for processed documents (in production, use a proper database)
documents_db: Dict[str, Dict[str, Any]] = {}


# Pydantic models
class QueryRequest(BaseModel):
    query: str
    jurisdiction: str | None = None
    n_results: int = 5


class CompareRequest(BaseModel):
    jurisdiction1: str
    jurisdiction2: str


class QueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    summary: str | None = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "RegAtlas",
        "version": "0.1.0",
        "documents_count": vector_store.get_document_count(),
        "jurisdictions": vector_store.list_jurisdictions()
    }


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    jurisdiction: str = Query(..., description="Regulatory jurisdiction (e.g., 'Hong Kong', 'Singapore')")
):
    """
    Upload and process a regulatory document.
    
    Args:
        file: PDF or text file containing regulatory text
        jurisdiction: Jurisdiction this document belongs to
        
    Returns:
        Processing results including extracted requirements
    """
    logger.info(f"Received upload: {file.filename} for jurisdiction: {jurisdiction}")
    
    try:
        # Generate document ID
        doc_id = str(uuid.uuid4())
        
        # Save uploaded file temporarily
        temp_dir = settings.data_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        file_path = temp_dir / f"{doc_id}_{file.filename}"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Process document
        processed = doc_processor.process_file(file_path)
        
        # Extract requirements
        full_text = processed["full_text"]
        requirements = req_extractor.extract_requirements(full_text, jurisdiction)
        
        # Chunk and add to vector store
        chunks = doc_processor.chunk_text(full_text, chunk_size=1000, overlap=200)
        
        metadata = {
            **processed["metadata"],
            "jurisdiction": jurisdiction,
            "doc_id": doc_id
        }
        
        chunks_added = vector_store.add_document(doc_id, chunks, metadata)
        
        # Store document info
        documents_db[doc_id] = {
            "doc_id": doc_id,
            "filename": file.filename,
            "jurisdiction": jurisdiction,
            "requirements": requirements,
            "chunks_count": chunks_added,
            "metadata": metadata
        }
        
        # Clean up temp file
        file_path.unlink()
        
        logger.info(f"Successfully processed document {doc_id}")
        
        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "jurisdiction": jurisdiction,
            "chunks_added": chunks_added,
            "requirements": requirements
        }
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Query regulatory documents using RAG.
    
    Args:
        request: Query request with search terms and optional filters
        
    Returns:
        Relevant document chunks and optional LLM-generated summary
    """
    logger.info(f"Query: '{request.query}' (jurisdiction: {request.jurisdiction})")
    
    try:
        # Search vector store
        results = vector_store.query(
            query_text=request.query,
            n_results=request.n_results,
            jurisdiction=request.jurisdiction
        )
        
        # Optionally generate summary with LLM
        summary = None
        if req_extractor.client and results:
            context = "\n\n".join([r["document"] for r in results[:3]])
            
            try:
                from openai import OpenAI
                client = OpenAI(
                    api_key=settings.openrouter_api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                
                response = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": "You are a regulatory compliance expert. Provide concise, accurate answers based on the provided regulatory text."},
                        {"role": "user", "content": f"Based on the following regulatory text, answer this question: {request.query}\n\nContext:\n{context}"}
                    ],
                    temperature=0.1,
                    max_tokens=500
                )
                
                summary = response.choices[0].message.content or "No summary generated"
                
            except Exception as e:
                logger.warning(f"Could not generate summary: {e}")
        
        return QueryResponse(
            query=request.query,
            results=results,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare")
async def compare_jurisdictions(request: CompareRequest):
    """
    Compare regulatory requirements between two jurisdictions.
    
    Args:
        request: Comparison request specifying two jurisdictions
        
    Returns:
        Comparison summary highlighting similarities and differences
    """
    logger.info(f"Comparing: {request.jurisdiction1} vs {request.jurisdiction2}")
    
    try:
        # Find documents for each jurisdiction
        docs1 = [doc for doc in documents_db.values() 
                if doc["jurisdiction"] == request.jurisdiction1]
        docs2 = [doc for doc in documents_db.values() 
                if doc["jurisdiction"] == request.jurisdiction2]
        
        if not docs1:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction1}"
            )
        
        if not docs2:
            raise HTTPException(
                status_code=404,
                detail=f"No documents found for jurisdiction: {request.jurisdiction2}"
            )
        
        # Aggregate requirements
        req1 = {
            "jurisdiction": request.jurisdiction1,
            "requirements": []
        }
        req2 = {
            "jurisdiction": request.jurisdiction2,
            "requirements": []
        }
        
        for doc in docs1:
            req1["requirements"].extend(doc.get("requirements", {}).get("requirements", []))
        
        for doc in docs2:
            req2["requirements"].extend(doc.get("requirements", {}).get("requirements", []))
        
        # Generate comparison
        comparison = req_extractor.compare_requirements(req1, req2)
        
        return {
            "jurisdiction1": request.jurisdiction1,
            "jurisdiction2": request.jurisdiction2,
            "comparison": comparison,
            "documents_compared": {
                request.jurisdiction1: len(docs1),
                request.jurisdiction2: len(docs2)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing jurisdictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List all processed documents."""
    return {
        "documents": list(documents_db.values()),
        "total": len(documents_db),
        "jurisdictions": vector_store.list_jurisdictions()
    }


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "total_chunks": vector_store.get_document_count(),
        "total_documents": len(documents_db),
        "jurisdictions": vector_store.list_jurisdictions(),
        "llm_available": req_extractor.client is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
