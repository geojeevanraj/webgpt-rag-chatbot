# WebGPT — RAG-Powered Website Chatbot

A chatbot that ingests any website URL, recursively scrapes linked pages, and uses Retrieval-Augmented Generation (RAG) to answer user questions grounded in the collected content.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 · TypeScript · Tailwind CSS v4 |
| **Backend** | FastAPI · Python 3.12 |
| **LLM** | Google Gemini 2.5 Flash |
| **Embeddings** | Sentence Transformers (all-MiniLM-L6-v2) |
| **Vector Store** | ChromaDB |
| **Database** | SQLite (async via aiosqlite) |
| **Scraping** | BeautifulSoup4 · aiohttp |

## Architecture

```
┌──────────────────┐     ┌──────────────────────────────────────┐
│                  │     │           FastAPI Backend             │
│   React Frontend │────▶│                                      │
│                  │     │  Scraper → Chunker → Embedder → ChromaDB
│                  │◀────│                                      │
│                  │     │  RAG Engine → Gemini API → Response   │
└──────────────────┘     └──────────────────────────────────────┘
```

### Core Flow

1. **Ingest**: User submits a URL → Recursive BFS scrape → Clean HTML → Chunk text → Embed → Store in ChromaDB
2. **Query**: User asks a question → Embed question → Retrieve similar chunks → Augmented prompt → Gemini generates answer with citations

## Project Structure

```
webgpt/
├── frontend/               # React + TypeScript + Tailwind v4
│   ├── src/
│   │   ├── components/     # UI components (chat, sidebar, layout)
│   │   ├── hooks/          # Custom React hooks
│   │   ├── services/       # API client layer
│   │   └── types/          # TypeScript interfaces
│   └── ...
│
├── backend/                # FastAPI + Python 3.12
│   ├── app/
│   │   ├── api/            # Route handlers (scrape, chat, sources)
│   │   ├── core/           # Config, database engine
│   │   ├── models/         # ORM models + Pydantic schemas
│   │   └── services/       # Business logic (scraper, chunker, embedder, RAG)
│   └── requirements.txt
│
└── .gitignore
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### Backend Setup

```bash
cd backend

# Create virtual environment
uv venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and the API at `http://localhost:8000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scrape` | Start a new scrape job |
| `GET` | `/api/scrape/{job_id}/status` | Get scrape progress |
| `DELETE` | `/api/scrape/{job_id}` | Delete a scrape job |
| `POST` | `/api/chat` | Ask a question |
| `GET` | `/api/chat/{job_id}/history` | Get chat history |
| `GET` | `/api/sources` | List all scraped sources |
| `GET` | `/health` | Health check |

## License

MIT
