# SANGYAN 2K26

SANGYAN is an investor-grievance assistant for Indian securities and brokerage issues. The React frontend uses the authenticated FastAPI application for account and report storage. That backend forwards grievance conversations to the SANGYAN AI reasoning service.

Both backend services use the same PostgreSQL 16 database. PostgreSQL is provided by the `pgvector/pgvector:pg16` image; AI cases, regulatory knowledge, and 768-dimensional Ollama embeddings are stored in the same database. There is no separate vector-database service.

## Architecture

```text
React + Vite (5173)
        │ cookie-authenticated /api requests
        ▼
FastAPI account and grievance backend (8000)
        │ authenticated server-to-server requests
        ▼
SANGYAN AI reasoning API (8001)
        │
        ▼
PostgreSQL 16 + pgvector (5432) ── Ollama nomic-embed-text
```

The browser never calls the AI service directly. The account backend associates each AI case with its owner's saved grievance and persists the conversation, assessment summary, evidence questions, suggested next steps, and AI case version.

## Local setup (Windows PowerShell)

### Prerequisites

- Node.js and npm
- Python 3.11 or newer
- PostgreSQL 16 or newer with the `vector` (pgvector) extension
- Ollama with the `nomic-embed-text` model for semantic retrieval

Redis is optional for local development. The local configuration uses in-memory
sessions, rate limiting, and caching, so Docker Desktop is not required.

### Install dependencies

From the repository root:

```powershell
cd .\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..
.\backend\.venv\Scripts\python.exe -m pip install -r .\ai\requirements.txt
npm install
npm run install:frontend
```

The repository has local backend configuration already. On a fresh checkout, create it from the template:

```powershell
if (-not (Test-Path .\backend\.env)) {
    Copy-Item .\backend\.env.example .\backend\.env
}
```

The host-run backend and AI both use the Compose database. Their local connection string is:

```text
DATABASE_URL=postgresql+psycopg://sangyan:local_dev_password@localhost:5432/sangyan_db
```

The backend reads `backend/.env`; AI reads `ai/.env`. `ai/.env` is local-only and Git-ignored; it must point to the same database. These Compose credentials are for local development only.

### Set up native PostgreSQL

Install PostgreSQL and pgvector using the installer or package manager for your
operating system. Ensure the `vector` extension is available to the database
that will hold the SANGYAN schema. On Windows, the PostgreSQL `bin` directory
must be on `PATH` so that `psql` can be run from PowerShell.

From the repository root, run:

```powershell
npm run setup:local
```

The setup command reads `backend/.env`, creates the configured database when
needed, verifies PostgreSQL and pgvector, and applies both Alembic migration
sets. It does not start Docker, Redis, or any other container.

If you already have a configured database and only need to rerun migrations:

```powershell
npm run migrate:local
```

### Apply database migrations

The account backend and AI use separate Alembic version tables while sharing the same database. `npm run setup:local` and `npm run migrate:local` perform these steps automatically:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location

Push-Location .\ai
..\backend\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

The AI migration enables the PostgreSQL `vector` extension, converts old embedding arrays to `vector(768)`, and creates an HNSW cosine index.

### Build the regulatory knowledge index

Start Ollama in one PowerShell window if it is not already running:

```powershell
ollama serve
```

Then, in another PowerShell window, download the model:

```powershell
ollama pull nomic-embed-text
```

Review the approved source list in [`ai/corpus/manifest.v1.yaml`](./ai/corpus/manifest.v1.yaml). Then, from the repository root, ingest the listed sources, extract provisions, and index their 768-dimensional embeddings:

```powershell
Push-Location .\ai
..\backend\.venv\Scripts\python.exe .\app\corpus\runner.py --manifest .\corpus\manifest.v1.yaml --use-db
..\backend\.venv\Scripts\python.exe .\scripts\extract_provisions.py
..\backend\.venv\Scripts\python.exe .\scripts\index_embeddings.py
Pop-Location
```

The corpus runner processes only sources declared in the manifest. See [`ai/corpus/README.md`](./ai/corpus/README.md) for its validation and rerun behavior.

### Run the application

From the repository root:

```powershell
npm run dev
```

This starts the account backend on `http://127.0.0.1:8000`, the AI API on `http://127.0.0.1:8001`, and the frontend on `http://localhost:5173`. The AI process starts with `ai/` as its working directory, so it reads the local `ai/.env`. Sign in, start a grievance, then continue the conversation with the AI-backed chat. Reports can be reopened and printed or saved as PDF.

## Configuration details

- PostgreSQL connection string: `DATABASE_URL=postgresql+psycopg://...`.
- Backend setting: `AI_BACKEND_URL` defaults to `http://127.0.0.1:8001`.
- Ollama defaults to `http://localhost:11434`; the embedding model is `nomic-embed-text` with 768 dimensions.
- AI migration versioning is stored in `ai_alembic_version`; the account backend uses `alembic_version`.
- Use HTTPS, strong unique secrets, secure cookies, restricted CORS origins, and production database credentials in deployed environments.

## Validation

```powershell
npm run lint
npm run build
```

Backend tests (integration tests use Docker-backed PostgreSQL and skip when Docker is unavailable):

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m pytest tests -q
Pop-Location
```

AI tests:

```powershell
Push-Location .\ai
..\backend\.venv\Scripts\python.exe -m pytest tests -q
Pop-Location
```
