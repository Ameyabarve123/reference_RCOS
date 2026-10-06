# RCOS RAG Application

Scaffold for a RAG application using Next.js, Supabase, FastAPI, and LangChain.

## Structure

```
reference_RCOS/
├── Architecture/     # Architecture PDFs
├── frontend/         # Next.js (TypeScript + Tailwind)
└── backend/          # FastAPI + LangChain (Python)
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+ (3.12/3.13 recommended)

## Frontend setup

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

App runs at [http://localhost:3000](http://localhost:3000).

## Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> On Windows, prefer `python -m uvicorn ...` over calling `uvicorn` directly — Application Control policies often block `uvicorn.exe` in virtualenvs.

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)  
Health check: [http://localhost:8000/health](http://localhost:8000/health)

## Environment variables

Copy the `.env.example` files in each package and fill in Supabase / API keys when ready.

## What's included (setup only)

- Next.js app with TypeScript, Tailwind, ESLint
- Supabase JS clients (`@supabase/supabase-js`, `@supabase/ssr`) under `frontend/src/lib/supabase/`
- FastAPI app entrypoint with CORS and a health route
- LangChain and related packages in `backend/requirements.txt` (not wired to routes yet)

RAG ingestion, retrieval, and chat features are intentionally not implemented yet.
