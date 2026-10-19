# Blend — Hybrid Search RAG Pipeline

> A full-stack Retrieval-Augmented Generation system that combines **dense vector search** (semantic similarity) with **sparse keyword/FTS search** (BM25) to achieve superior retrieval quality over either technique alone.

Built for learning and mastery of modern RAG architectures, hybrid retrieval strategies, and cloud-native deployment patterns.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React + Vite UI                          │
│              Chat Interface  │  Document Dashboard              │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────────────────┐
│                   FastAPI Backend (Python 3.11)                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  /api/query │  │/api/documents│  │   MCP Server (stdio)   │  │
│  └──────┬──────┘  └──────┬───────┘  └────────────────────────┘  │
│         │                │                                        │
│  ┌──────▼──────────────────────────────────────────┐             │
│  │           Hybrid Search Engine (RRF)             │             │
│  │   Dense (Gemini Embeddings + Cosine Sim)         │             │
│  │   +  Sparse (SQLite FTS5 / Postgres tsvector)    │             │
│  └──────────────────────┬───────────────────────────┘             │
│                          │                                        │
│  ┌───────────────────────▼──────────────────────────┐            │
│  │        Gemini API (Grounded Generation)           │            │
│  └───────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   SQLite (local dev)    │
        │   Neon Postgres (prod)  │
        │   + pgvector extension  │
        └─────────────────────────┘
```

### Hybrid Search: How It Works

Blend uses **Reciprocal Rank Fusion (RRF)** to merge ranked lists from two retrieval methods:

```
score(d) = dense_weight / (k + dense_rank)
         + sparse_weight / (k + sparse_rank)
```

| Parameter       | Default | Description                           |
|-----------------|---------|---------------------------------------|
| `dense_weight`  | 0.6     | Weight given to semantic similarity   |
| `sparse_weight` | 0.4     | Weight given to BM25/FTS keyword rank |
| `k` (RRF)       | 60      | Standard RRF constant                 |
| `top_k`         | 10      | Chunks retrieved before LLM context   |
| `top_k_context` | 5       | Chunks sent to the LLM                |

---

## Tech Stack

| Layer          | Local Dev                    | Production                      |
|----------------|------------------------------|---------------------------------|
| **Backend**    | FastAPI + Uvicorn            | Azure Container Apps (scale-to-zero) |
| **Database**   | SQLite + FTS5                | Neon Serverless Postgres + pgvector |
| **Embeddings** | Gemini `text-embedding-004`  | Gemini `text-embedding-004`     |
| **Generation** | Gemini `gemini-2.0-flash`    | Gemini `gemini-2.0-flash`       |
| **Frontend**   | React 18 + Vite + Tailwind   | Vercel                          |
| **Registry**   | —                            | GitHub Container Registry (GHCR) |
| **IaC**        | —                            | Azure Bicep                     |
| **CI/CD**      | —                            | GitHub Actions + OIDC (no stored cloud secrets) |

---

## Project Structure

```
blend/
├── .github/
│   └── workflows/
│       ├── pr-checks.yml        # Lint, type-check, test on every PR
│       └── deploy-azure.yml     # Build → GHCR → Azure Container Apps
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry-point & lifespan
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic v2 BaseSettings
│   │   │   ├── database.py      # Async SQLAlchemy engine & sessions
│   │   │   └── security.py      # API-key dependency
│   │   ├── models/
│   │   │   ├── orm.py           # Document & Chunk SQLAlchemy models
│   │   │   └── schemas.py       # Pydantic v2 request/response schemas
│   │   ├── services/
│   │   │   ├── embedding.py     # Gemini embedding wrapper (async)
│   │   │   ├── chunker.py       # Sliding-window text chunker
│   │   │   ├── hybrid_search.py # RRF merger + dense/sparse retrieval
│   │   │   ├── ingestion.py     # Full ingestion pipeline
│   │   │   └── gemini.py        # Grounded generation service
│   │   ├── mcp/
│   │   │   └── server.py        # MCP stdio server exposing blend_search tool
│   │   └── api/
│   │       ├── health.py        # GET /health/
│   │       ├── documents.py     # CRUD /api/documents/
│   │       └── query.py         # POST /api/query/
│   ├── Dockerfile               # Multi-stage build (builder + runtime)
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│       ├── test_health.py
│       └── test_hybrid_search.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router + sidebar layout
│   │   ├── main.jsx
│   │   ├── index.css            # Tailwind + scroll-state CSS
│   │   └── components/
│   │       ├── ChatPage.jsx     # Chat UI with hybrid search results
│   │       └── DocumentsPage.jsx # Document upload & management
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── vite.config.js
├── infra/
│   ├── main.bicep               # Root Bicep template
│   └── modules/
│       ├── container-app.bicep  # Azure Container App + scaling rules
│       └── container-registry.bicep  # Optional ACR module
└── README.md
```

---

## Quick Start — Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### 1. Clone & configure

```bash
git clone https://github.com/jun-gh/blend.git
cd blend
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-here

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API is now live at **https://blend-api.ambitiousflower-4ef79cd6.southeastasia.azurecontainerapps.io**  
Interactive docs: **https://blend-api.ambitiousflower-4ef79cd6.southeastasia.azurecontainerapps.io/docs**

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (proxies /api/* to :8000 automatically)
npm run dev
```

Frontend is now and password protected at **https://blend-theta.vercel.app**

---

## Usage

### Ingest a document

```bash
curl -X POST http://localhost:8000/api/documents/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Attention Is All You Need",
    "content": "We propose a new simple network architecture...",
    "source": "https://arxiv.org/abs/1706.03762"
  }'
```

### Query the knowledge base

```bash
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the purpose of multi-head attention?",
    "top_k": 5,
    "dense_weight": 0.7,
    "sparse_weight": 0.3
  }'
```

### MCP Server (for Claude Desktop / Cursor)

```bash
# Run the MCP server directly (stdio transport)
python -m app.mcp.server
```

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blend": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/blend/backend"
    }
  }
}
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Production Deployment

### Azure Container Apps (via GitHub Actions)

1. **Fork** this repository.
2. **Configure GitHub repository secrets**:
   - `AZURE_CLIENT_ID` — Service principal client ID (OIDC federated credential)
   - `AZURE_TENANT_ID` — Azure AD tenant ID  
   - `AZURE_SUBSCRIPTION_ID` — Azure subscription ID
   - `GEMINI_API_KEY` — Your Gemini API key
   - `DATABASE_URL` — Neon Postgres connection string
3. **Configure OIDC** in Azure: create a federated identity credential on your service principal for `repo:YOUR_ORG/blend:ref:refs/heads/main`.
4. **Push to `main`** — the `deploy-azure.yml` workflow will:
   - Build and push the Docker image to GHCR
   - Log into Azure via OIDC (no stored cloud secrets!)
   - Deploy the Bicep template to create/update the Container App

### Frontend — Vercel

1. Connect the repo in the [Vercel dashboard](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Add environment variable: `VITE_API_URL=https://your-container-app.azurecontainerapps.io`
4. Deploy.

---

## Production Database — Neon Postgres + pgvector

1. Create a [Neon](https://neon.tech) project and enable the `pgvector` extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. Add a `VECTOR(768)` column to the `chunks` table (replacing the SQLite JSON fallback):
   ```sql
   ALTER TABLE chunks ADD COLUMN embedding vector(768);
   CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
   ```
3. Update `DATABASE_URL` in your secrets / `.env` to the Neon connection string.
4. The dense search in `hybrid_search.py` should be upgraded to use the pgvector `<=>` operator for production performance.

---

## Key Concepts for Learning

### Hybrid Search (Dense + Sparse)
- **Dense retrieval**: Embeds query and documents into high-dimensional vectors. Captures semantic meaning even without keyword overlap.
- **Sparse retrieval**: BM25/FTS matches exact and stemmed keywords. Excellent for named entities, technical terms, and precise lookups.
- **RRF fusion**: Normalises rank positions (not raw scores) to combine both lists without score calibration.

### RAG Pipeline Stages
1. **Ingestion**: Chunk → Embed → Store (vector + FTS index)
2. **Retrieval**: Dense search + Sparse search → RRF merge → Top-K chunks
3. **Generation**: Grounded prompt with retrieved context → Gemini LLM → Answer

### Error Handling & Automatic Retries
- **3-Retry Resilience**: Automatic exponential backoff with jitter (up to 3 retries) on transient API errors (`500`, `503`, `504`) and rate limits (`429` / `ResourceExhausted`).
- **User-Centric Error UX**: Distinguishes rate limit/quota events from connection issues and displays an inline banner with 1-click **Retry** and **Dismiss** controls directly above the chat box.

### Dynamic Model Configuration
- Switch LLM models via `GEMINI_CHAT_MODEL` in `.env` without modifying code. The UI dynamically detects and displays the active model badge in the chat header and sidebar footer (`Powered by <model>`).

### Optional Password Protection
- Configure `SITE_PASSWORD` in `.env` to protect the app. If left empty, blank, or `"null"`, authentication is seamlessly disabled for open development and demo access.

### MCP Integration
The MCP server exposes `blend_search` as a tool that any MCP-compatible AI client can call directly, enabling AI assistants to query your private knowledge base without any custom plugin code.

---

## Environment Variables

| Variable               | Default                             | Description                          |
|------------------------|-------------------------------------|--------------------------------------|
| `DATABASE_URL`         | `sqlite+aiosqlite:///./blend.db`    | Database connection string           |
| `GEMINI_API_KEY`       | —                                   | **Required.** Google AI API key      |
| `GEMINI_EMBED_MODEL`   | `models/text-embedding-004`         | Embedding model                      |
| `GEMINI_CHAT_MODEL`    | `models/gemini-2.0-flash`           | Chat/generation model (dynamic)      |
| `SITE_PASSWORD`        | —                                   | Optional visitor password protection |
| `EMBEDDING_DIMENSIONS` | `768`                               | Vector dimensionality                |
| `DENSE_WEIGHT`         | `0.6`                               | RRF dense score weight               |
| `SPARSE_WEIGHT`        | `0.4`                               | RRF sparse score weight              |
| `TOP_K_RETRIEVAL`      | `10`                                | Chunks retrieved per query           |
| `TOP_K_CONTEXT`        | `5`                                 | Chunks sent to LLM                   |
| `DEBUG`                | `false`                             | Enable SQL echo & verbose logging    |
| `CORS_ORIGINS`         | `["http://localhost:5173"]`         | Allowed CORS origins (JSON array)    |

---

## License

MIT
