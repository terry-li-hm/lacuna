# RegAtlas

A production-ready prototype for analyzing and comparing regulatory requirements across different jurisdictions. Cross-jurisdiction regulatory analytics platform for financial institutions.

## Overview

This tool helps banks and financial institutions:
- **Ingest** regulatory documents (PDFs, text files) from multiple jurisdictions
- **Extract** key requirements using LLM-based analysis
- **Query** requirements using RAG (Retrieval Augmented Generation)
- **Compare** requirements across jurisdictions to identify similarities and differences

## Features

- **Document Processing**: Supports PDF and text file uploads with automatic text extraction
- **AI-Powered Extraction**: Uses LLMs to identify and categorize regulatory requirements
- **Vector Search**: ChromaDB-backed semantic search for finding relevant requirements
- **Cross-Jurisdiction Comparison**: Compare requirements between any two jurisdictions
- **Clean Web UI**: Simple, responsive interface for all operations
- **API-First Design**: FastAPI backend with documented endpoints
- **Flexible LLM Support**: Works with OpenAI API or fallback to local models

## Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **Vector Database**: ChromaDB with sentence-transformers embeddings
- **LLM**: OpenAI GPT-3.5/4 (with graceful fallback)
- **Document Processing**: pypdf for PDF extraction
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Package Management**: uv (modern Python package manager)

## Quick Start

### Prerequisites

- Python 3.10 or higher
- (Optional) OpenAI API key for enhanced LLM features

### Installation

1. **Clone or navigate to the project directory**:
```bash
cd ~/reg-atlas
```

2. **Install dependencies using uv**:
```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv pip install -e .
```

3. **Configure environment** (optional for OpenAI):
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### Running the Application

1. **Start the backend server**:
```bash
# Using uv
cd ~/reg-atlas
uv run uvicorn backend.main:app --reload

# Or with regular Python
python -m uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000`

2. **Open the web interface**:
```bash
# Open frontend/index.html in your browser
open frontend/index.html

# Or use a simple HTTP server
cd frontend
python -m http.server 8080
# Then visit http://localhost:8080
```

## Usage

### 1. Upload Regulatory Documents

1. Select a PDF or text file containing regulatory requirements
2. Choose the jurisdiction (Hong Kong, Singapore, UK, US, EU)
3. Click "Upload & Analyze"
4. View extracted requirements categorized by type

### 2. Query Requirements

1. Enter a natural language query (e.g., "What are capital adequacy requirements?")
2. Optionally filter by jurisdiction
3. Get relevant document sections and AI-generated summary

### 3. Compare Jurisdictions

1. Select two jurisdictions to compare
2. View side-by-side comparison of requirements
3. See common requirements, differences, and relative strictness

## API Endpoints

### Health Check
```
GET /
```
Returns system status and statistics

### Upload Document
```
POST /upload?jurisdiction={jurisdiction}
Content-Type: multipart/form-data

Body: {file: <PDF or TXT file>}
```
Processes document and extracts requirements

### Query Documents
```
POST /query
Content-Type: application/json

Body: {
  "query": "What are capital requirements?",
  "jurisdiction": "Hong Kong",  // optional
  "n_results": 5
}
```
Returns relevant document chunks and optional summary

### Compare Jurisdictions
```
POST /compare
Content-Type: application/json

Body: {
  "jurisdiction1": "Hong Kong",
  "jurisdiction2": "Singapore"
}
```
Returns comparison analysis

### Get Statistics
```
GET /stats
```
Returns document count, chunk count, and jurisdictions

### List Documents
```
GET /documents
```
Returns all processed documents with metadata

## Sample Documents

Two sample regulatory documents are included in `data/documents/`:

1. **sample_hkma_capital.txt**: Hong Kong Monetary Authority capital adequacy requirements
2. **sample_mas_liquidity.txt**: Monetary Authority of Singapore liquidity coverage ratio requirements

These can be used to test the system immediately without needing to source your own regulatory documents.

## Architecture

### Document Processing Pipeline

```
PDF/TXT → Text Extraction → Chunking → Embedding → Vector Store
                ↓
         LLM Requirement Extraction
                ↓
         Structured Requirements
```

### Query Flow

```
User Query → Embedding → Vector Search → Top K Chunks
                                           ↓
                                    LLM Summarization
                                           ↓
                                    Formatted Response
```

### Key Components

- **DocumentProcessor**: Handles PDF/text extraction and chunking
- **RequirementExtractor**: LLM-based requirement identification and categorization
- **VectorStore**: ChromaDB wrapper for semantic search
- **FastAPI App**: REST API with CORS support

## Configuration

Key settings in `backend/config.py`:

- `openai_api_key`: OpenAI API key (optional)
- `log_level`: Logging level (INFO, DEBUG, etc.)
- `embedding_model`: Sentence transformer model for embeddings
- `llm_model`: OpenAI model to use (gpt-3.5-turbo, gpt-4, etc.)
- `chroma_persist_dir`: Where vector database is stored

## Project Structure

```
reg-atlas/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── document_processor.py   # Document ingestion
│   ├── requirement_extractor.py # LLM-based extraction
│   └── vector_store.py         # ChromaDB interface
├── frontend/
│   └── index.html              # Web UI
├── data/
│   ├── documents/              # Sample documents
│   │   ├── sample_hkma_capital.txt
│   │   └── sample_mas_liquidity.txt
│   └── db/                     # Vector database (auto-created)
├── pyproject.toml              # Dependencies
├── .env.example                # Environment template
└── README.md                   # This file
```

## Development

### Running Tests
```bash
uv pip install -e ".[dev]"
pytest
```

### Code Formatting
```bash
black backend/
ruff check backend/ --fix
```

### Adding New Features

1. **New Document Types**: Extend `DocumentProcessor._process_*` methods
2. **New LLM Providers**: Modify `RequirementExtractor` to support additional APIs
3. **Enhanced Extraction**: Update prompts in `extract_requirements()`
4. **New Endpoints**: Add routes to `backend/main.py`

## Limitations & Future Enhancements

### Current Limitations
- In-memory document storage (use proper database for production)
- No user authentication
- Limited to English language documents
- Basic keyword fallback when LLM unavailable

### Potential Enhancements
- User authentication and multi-tenancy
- Document versioning and change tracking
- Automated regulatory update monitoring
- Support for multiple languages
- Export to Excel/PDF reports
- Integration with compliance management systems
- Graph-based requirement relationship mapping
- Automated alert generation for regulatory changes

## Production Deployment

For production deployment:

1. **Use proper database**: Replace in-memory `documents_db` with PostgreSQL/MongoDB
2. **Add authentication**: Implement JWT or OAuth2
3. **Scale vector store**: Consider Pinecone, Weaviate, or hosted ChromaDB
4. **Add monitoring**: Integrate Sentry, DataDog, or similar
5. **Use production ASGI server**: Gunicorn + Uvicorn workers
6. **Add rate limiting**: Protect API endpoints
7. **Enable HTTPS**: Use Nginx/Traefik as reverse proxy
8. **Containerize**: Build Docker images and use Kubernetes/ECS

## Docker Support (Coming Soon)

Docker configuration will be added to enable:
```bash
docker-compose up
# Visit http://localhost:8000 for API
# Visit http://localhost:8080 for UI
```

## License

MIT License - free to use and modify for Capco client engagements and demonstrations.

## Contact

Built for Capco's regulatory analytics engagement.

For questions or enhancements, contact the development team.

---

## Quick Demo Script

Want to quickly demo the tool? Follow these steps:

1. **Start the backend**:
   ```bash
   cd ~/reg-atlas
   uv run uvicorn backend.main:app --reload
   ```

2. **Open UI in browser**:
   ```bash
   open frontend/index.html
   ```

3. **Upload sample documents**:
   - Upload `data/documents/sample_hkma_capital.txt` as "Hong Kong"
   - Upload `data/documents/sample_mas_liquidity.txt` as "Singapore"

4. **Try queries**:
   - "What are the minimum capital requirements?"
   - "What is the liquidity coverage ratio?"
   - "Compare capital requirements"

5. **Compare jurisdictions**:
   - Select Hong Kong vs Singapore
   - View automated comparison

Total demo time: **5 minutes**
