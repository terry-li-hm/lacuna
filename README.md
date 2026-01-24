# RegAtlas

A production-ready prototype for analyzing and comparing regulatory requirements across different jurisdictions. Cross-jurisdiction regulatory analytics platform for financial institutions.

**🚀 Live Demo:** https://reg-atlas.onrender.com  
**📦 Repository:** https://github.com/terry-li-hm/reg-atlas

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
- **Metadata Persistence**: Keeps processed document metadata across restarts
- **Cross-Jurisdiction Comparison**: Compare requirements between any two jurisdictions
- **Requirements Registry**: Centralized requirement catalog with review status and tags
- **Evidence Linking**: Auto-attached citation snippets from source documents
- **Exports**: One-click CSV export for compliance teams
- **Document Library**: Track processed documents, jurisdictions, and ingestion stats
- **Regulatory Change Register**: Log regulatory updates, ownership, deadlines, and impact
- **Audit Trail**: Immutable log of review and change actions for audit readiness
- **Horizon Scanning**: RSS/Atom feed ingestion to auto-create change items
- **Approvals Workflow**: Capture approvals per change item
- **Evidence Management**: Upload evidence files linked to changes/requirements
- **Alerts**: Overdue change detection for SLA tracking
- **Entity Scoping**: Filter by entity and business unit for group reporting
- **Integration Export**: JSON export for downstream systems
- **GenAI Suggestions**: Draft impact summaries and map related requirements
- **Policy Library**: Internal policy/procedure registry for impact mapping
- **Risk Scoring**: Severity + SLA-based prioritization for changes
- **Escalation Flags**: Overdue/high severity alerts surface escalation need
- **Webhooks**: Push change events to downstream systems
- **Clean Web UI**: Simple, responsive interface for all operations
- **CLI Tool**: Beautiful terminal interface for rapid testing and automation
- **API-First Design**: FastAPI backend with documented endpoints
- **OpenRouter Integration**: Uses OpenRouter for LLM and embeddings (multi-model support)

## Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **Vector Database**: ChromaDB with OpenAI embeddings via OpenRouter
- **LLM**: OpenRouter (multi-model access: GPT, Claude, Llama, etc.)
- **Document Processing**: pypdf for PDF extraction
- **CLI**: Typer + Rich for beautiful terminal interface
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Package Management**: uv (modern Python package manager)
- **Deployment**: Render (free tier)

## Quick Start

**🎯 Fastest Way - Use the CLI:**

```bash
cd ~/reg-atlas
source .venv/bin/activate

# Test the deployed service
python -m cli.main health
python -m cli.main upload data/documents/sample_hkma_capital.txt -j "Hong Kong"
python -m cli.main query "What are capital requirements?"
```

See [CLI.md](CLI.md) for full CLI documentation.

### Prerequisites

- Python 3.10 or higher
- OpenRouter API key (required for LLM features)

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

### Docker (Local)

**Build and run:**
```bash
docker build -t reg-atlas .
docker run -p 8000:8000 -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY reg-atlas
```

**Docker Compose:**
```bash
docker compose up --build
```

**Scripts:**
```bash
scripts/docker-build.sh
scripts/docker-run.sh
```

### On-Prem Packaging

**Single-node (compose):**
```bash
docker compose -f docker-compose.onprem.yml up --build
```

**Kubernetes (basic manifests):**
```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml
kubectl apply -f deploy/k8s/pvc.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
```

**Note:** These manifests deploy the app with persistent storage only. Add SSO/RBAC, external DB, and object storage for true production.

**Helm (recommended for on-prem):**
```bash
helm install reg-atlas deploy/helm/reg-atlas
```

**Helm (upgrade/install):**
```bash
helm upgrade --install reg-atlas deploy/helm/reg-atlas
```

**Helm values template:**
```bash
cp deploy/helm/reg-atlas/values.yaml deploy/helm/reg-atlas/values-prod.yaml
```

**AWS (ECS/Fargate scaffold):**
See `deploy/aws/README.md` and `deploy/aws/ecs/task-definition.json`

## Sales Collateral

- `docs/buyer-one-pager.md`

## POC vs Production Readiness

**POC / Client Demo (ready):**
- End-to-end workflow: ingest → extract → compare → change log → approvals → evidence → export
- GenAI summaries + offline demo mode
- Horizon scanning (RSS/Atom) and alerts
- Policy library + impact mapping
- Risk scoring + escalation flags

**Production (gaps to close):**
- SSO/RBAC and audit-grade access logging
- Multi-tenant data isolation and encryption at rest
- Policy/version lifecycle management + training attestations
- Advanced workflow escalation + SLA monitoring
- Enterprise integrations (ServiceNow/Archer/Jira) with hardened connectors

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

### Get Document
```
GET /documents/{doc_id}
```
Returns a single document with requirements

### Delete Document
```
DELETE /documents/{doc_id}
```
Deletes a document and all its indexed chunks

### List Requirements
```
GET /requirements?jurisdiction=Hong%20Kong&requirement_type=Capital%20Adequacy
```
Returns filtered requirements with review metadata

### Get Requirement
```
GET /requirements/id/{requirement_id}
```
Returns a single requirement by ID

### Review Requirement
```
POST /requirements/id/{requirement_id}/review
Content-Type: application/json

Body: {
  "status": "reviewed",
  "reviewer": "Compliance",
  "notes": "Reviewed for Q1 update",
  "tags": ["capital", "lcr"],
  "controls": ["Risk Control R-12"],
  "policy_refs": ["Policy AML-001"]
}
```
Updates review status and notes

### Export Requirements
```
GET /requirements/export?format=csv
```
Downloads requirements in CSV format

### Approvals
```
POST /changes/{change_id}/approvals
Content-Type: application/json

Body: {
  "approver": "Head of Compliance",
  "status": "pending",
  "notes": "Queued"
}
```
Adds an approval step

### Evidence Upload
```
POST /evidence/upload?entity_type=change&entity_id={change_id}
Content-Type: multipart/form-data
```
Uploads evidence linked to a change or requirement

### Alerts
```
GET /alerts
```
Returns overdue change items

### Entities
```
GET /entities
```
Lists entities and business units found in the data

### Sources
```
POST /sources
GET /sources
DELETE /sources/{source_id}
```
Manage regulatory feed sources

### Scan Sources
```
POST /scan
POST /scan?source_id={source_id}
```
Scan feeds and create change items

### Integration Export
```
GET /integrations/export
```
Export core data as JSON

### Policies
```
GET /policies
GET /policies/{policy_id}
```
Lists internal policies and retrieves policy details

### Policy Update
```
POST /policies/{policy_id}/update
Content-Type: application/json

Body: {
  "status": "active",
  "version": "1.1",
  "owner": "Compliance"
}
```

### Webhooks
```
POST /webhooks
GET /webhooks
DELETE /webhooks/{webhook_id}
```

### GenAI Suggestions
```
POST /changes/{change_id}/ai-suggest
Content-Type: application/json

Body: {
  "no_llm": false,
  "n_results": 5
}
```
Returns impact summary and suggested related requirements

### Impact Brief (Audit-Grade)
```
POST /changes/{change_id}/impact-brief
Content-Type: application/json

Body: {
  "no_llm": false,
  "n_results": 5,
  "max_claims_per_section": 8
}
```
Returns an audit-grade impact brief with claim-level citations

### Create Change Item
```
POST /changes
Content-Type: application/json

Body: {
  "title": "HKMA circular on LCR reporting",
  "jurisdiction": "Hong Kong",
  "summary": "New disclosure requirements for LCR",
  "severity": "high",
  "owner": "Compliance",
  "due_date": "2026-06-30"
}
```
Creates a regulatory change item for triage

### List Change Items
```
GET /changes?status=new&jurisdiction=Hong%20Kong
```
Returns filtered change items

### Update Change Item
```
POST /changes/{change_id}
Content-Type: application/json

Body: {
  "status": "assessing",
  "owner": "Risk",
  "impact_assessment": "Impacts liquidity reporting controls"
}
```
Updates status, owner, and impact assessment

### Export Change Items
```
GET /changes/export?format=csv
```
Downloads change log in CSV format

### Audit Log
```
GET /audit-log?entity_type=change
```
Returns audit trail entries

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
- `openai_base_url`: OpenAI-compatible base URL (default OpenRouter)
- `log_level`: Logging level (INFO, DEBUG, etc.)
- `embedding_model`: Sentence transformer model for embeddings
- `llm_model`: OpenAI model to use (gpt-3.5-turbo, gpt-4, etc.)
- `chroma_persist_dir`: Where vector database is stored
- `no_llm`: Disable LLM calls and use deterministic local embeddings (set `REG_ATLAS_NO_LLM=1`)

**Optional LlamaIndex chunking:**
- Install extra: `uv pip install -e ".[llamaindex]"`
- Enable: `REG_ATLAS_USE_LLAMAINDEX=1`

**On-prem LLM (OpenAI-compatible server):**
- Set `OPENAI_BASE_URL` to your local endpoint (e.g., `http://localhost:8000/v1`)
- Set `OPENAI_API_KEY` to a dummy value if your server ignores auth
- Set `LLM_MODEL=gpt-oss-120b`

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

**E2E (offline, no LLM calls):**
```bash
REG_ATLAS_NO_LLM=1 DATA_DIR=/tmp/reg_atlas_data CHROMA_PERSIST_DIR=/tmp/reg_atlas_data/db/chroma PYTHONPATH=/Users/terry/reg-atlas pytest tests/e2e_reg_atlas.py -q
```

**Convenience:**
```bash
make e2e
scripts/test.sh
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
