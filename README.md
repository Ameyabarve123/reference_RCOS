# RCOS RAG Application

A document library with retrieval-augmented answers. The pipeline matches `Architecture/`:

**Ingestion.** A router classifies an upload as PDF, image, or text. A chunking agent picks semantic, fixed, or sentence splits. Images go through a LaTeX agent that returns bounding boxes and equations. Chunks are embedded with Gemini `text-embedding-004` and stored in Supabase pgvector.

**Query.** A router chooses library-only, library plus web, or library plus pretrained knowledge. The question is embedded with the same model, the top chunks are reranked, and Gemini writes an answer with citations.

## Structure

```
reference_RCOS/
├── Architecture/       # Pipeline and ER diagrams
├── supabase/schema.sql # Postgres schema (run once in the SQL editor)
├── frontend/           # Next.js
└── backend/            # FastAPI + LangChain
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- A Supabase project with the `vector` extension

## 1. Database

In the Supabase SQL editor, run [`supabase/schema.sql`](supabase/schema.sql). That creates the Person, Folder, Text, Files, Chats, Messages, Chunks, References, AI Provider, Embeddings, and Uses tables, the `documents` storage bucket, and the `match_chunks` search function.

`PersonStoresFilesText` from the ER notes is omitted on purpose: the diagram marks it as redundant with `FolderContainingFilesText`.

## 2. Backend

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

`SUPABASE_KEY` must be the **secret / service-role** key. `GOOGLE_API_KEY` is a Gemini key.

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
Health check: [http://localhost:8000/health](http://localhost:8000/health)

## 3. Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

App: [http://localhost:3000](http://localhost:3000)

Sign-in is handled by the API, so the browser only needs `NEXT_PUBLIC_API_URL`.

## Using it

1. Create an account. If Supabase requires email confirmation, confirm it before signing in.
2. Upload a PDF, image, or text file, or paste a note. It is chunked and embedded into the selected folder.
3. Ask a question. The answer shows the query route and the cited chunks.
