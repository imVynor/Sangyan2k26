# Sangyan 2K26 - Financial Grievance Assistant

A React frontend and FastAPI backend for a guided financial-grievance workflow. PostgreSQL stores user accounts and saved grievance discussions/reports. Redis provides cache, session, and rate-limit services. The current discussion is a scripted workflow; a live AI agent is not configured.

## Project structure

```text
Sangyan2k26/
├── compose.yaml                  # PostgreSQL and Redis development services
├── backend/
│   ├── .env                      # Local configuration and secrets; do not commit
│   ├── .env.example              # Documented environment-variable template
│   ├── migrations/               # Alembic setup; schema migrations are pending
│   ├── src/
│   │   ├── infrastructure/       # Database, auth, Redis, and application setup
│   │   ├── interfaces/            # FastAPI application and API routers
│   │   └── modules/               # User, tier, role, API key, and grievance features
│   └── tests/
├── frontend/
│   ├── vite.config.js             # Proxies /api and /health to FastAPI
│   └── src/
│       ├── context/                # Authentication and grievance state
│       ├── components/             # UI and pages
│       └── services/api.js         # Backend HTTP client
└── docs/
    └── PROJECT_STATUS_REPORT.md
```

## Local setup (Windows PowerShell)

### 1. Start PostgreSQL and Redis with Compose

Docker Desktop must be running. From the repository root:

```powershell
docker compose up -d postgres redis
docker compose ps
```

`compose.yaml` starts PostgreSQL 16 and Redis 7. It publishes PostgreSQL on `localhost:5432` and Redis on `localhost:6379`, and persists their data under `docker-data/postgres` and `docker-data/redis`. These development containers are dependencies for the backend; the Compose file does not run the FastAPI backend or frontend.

The PostgreSQL service is initialized with:

| Compose setting | Development value |
|---|---|
| Database | `sangyan_db` |
| User | `sangyan` |
| Password | `local_dev_password` |
| Host port | `5432` |

These are local-development credentials only. If you change the Compose values, update the matching `POSTGRES_*` values in `backend/.env` and recreate/reinitialize the local database as appropriate. Do not use these credentials in production.

### 2. Configure the backend `.env`

Create `backend/.env` from the template only when you do not already have a local `.env`:

```powershell
if (-not (Test-Path .\backend\.env)) {
    Copy-Item .\backend\.env.example .\backend\.env
}
```

Edit `backend/.env` locally and keep it out of source control. When FastAPI runs directly on Windows (as in the commands below), use `localhost` for database and Redis hosts. Use these values to connect to the Compose services:

```env
ENVIRONMENT=development

# PostgreSQL from compose.yaml
POSTGRES_USER=sangyan
POSTGRES_PASSWORD=local_dev_password
POSTGRES_DB=sangyan_db
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_SYNC_PREFIX=postgresql://
POSTGRES_ASYNC_PREFIX=postgresql+asyncpg://
CREATE_TABLES_ON_STARTUP=true

# Redis from compose.yaml
CACHE_ENABLED=true
CACHE_BACKEND=redis
CACHE_REDIS_HOST=localhost
CACHE_REDIS_PORT=6379
CACHE_REDIS_DB=0
CACHE_REDIS_PASSWORD=

RATE_LIMITER_ENABLED=true
RATE_LIMITER_BACKEND=redis
RATE_LIMITER_REDIS_HOST=localhost
RATE_LIMITER_REDIS_PORT=6379
RATE_LIMITER_REDIS_DB=1
RATE_LIMITER_REDIS_PASSWORD=

SESSION_BACKEND=redis
SESSION_REDIS_DB=2
SESSION_SECURE_COOKIES=false
CSRF_ENABLED=true

TASKIQ_ENABLED=true
TASKIQ_BROKER_TYPE=redis
TASKIQ_REDIS_HOST=localhost
TASKIQ_REDIS_PORT=6379
TASKIQ_REDIS_DB=3
TASKIQ_REDIS_PASSWORD=

# Development frontend origin and Google OAuth callback base
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
OAUTH_REDIRECT_BASE_URL=http://localhost:5173
```

The `.env.example` file contains the full set of options. The groups are:

| Group | Main variables | Purpose |
|---|---|---|
| Application | `ENVIRONMENT`, `DEBUG`, `APP_NAME`, `VERSION` | Runtime mode and application metadata. |
| PostgreSQL | `POSTGRES_*`, `DATABASE_URL`, `CREATE_TABLES_ON_STARTUP`, `POSTGRES_POOL_*` | Connection credentials, async driver, optional hosted-database URL override, table initialization, and connection pool. `DATABASE_URL`, when set, overrides the individual PostgreSQL connection settings. |
| Cache | `CACHE_ENABLED`, `CACHE_BACKEND`, `CACHE_REDIS_*`, `DEFAULT_CACHE_EXPIRATION` | Selects Redis or Memcached for cache operations and configures Redis host, port, logical database, optional password, and timeouts. |
| Rate limiting | `RATE_LIMITER_*`, `DEFAULT_RATE_LIMIT_*` | Enables per-route limits. Redis-backed limits use their own Redis logical database, separate from the cache. |
| Sessions and security | `SESSION_*`, `CSRF_ENABLED`, `SECRET_KEY`, `TRUSTED_PROXY_HOPS`, `PASSWORD_*` | Configures login sessions, cookie behavior, CSRF, signing key, proxy handling, and password policy. |
| Task queue | `TASKIQ_*` | Selects Redis or RabbitMQ as the Taskiq broker and configures its connection and worker settings. |
| Web server | `CORS_*`, `GZIP_*`, `ENABLE_DOCS_IN_PRODUCTION`, `OPENAPI_PREFIX` | Configures browser origins, compression, and API documentation. |
| OAuth | `OAUTH_REDIRECT_BASE_URL`, `OAUTH_GOOGLE_*`, `OAUTH_GITHUB_*` | Configures provider credentials and the public base URL used to construct OAuth callbacks. Google is the configured sign-in provider in this application. |
| Admin | `ADMIN_*`, `ADMIN_ENABLED` | Configures the admin interface and initial admin account settings. |

For local Redis, cache uses logical database `0`, rate limiting `1`, sessions `2`, and Taskiq `3`. They are logical databases on the same Redis service, not separate Redis servers. Redis sessions use the cache Redis connection unless `SESSION_REDIS_URL` is explicitly set. Keep the corresponding host, port, database number, and password aligned with the service you run.

For a backend running inside Docker Compose, the service DNS names are `postgres` and `redis`; for the host-run backend in this guide, use `localhost`. Do not point a host-run backend at `postgres` or `redis`, as those names are only resolvable between Compose containers.

### 3. Create the backend virtual environment

From the repository root:

```powershell
cd .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ..
```

If PowerShell blocks virtual-environment activation, use the explicit interpreter path in subsequent commands: `.\backend\.venv\Scripts\python.exe`.

`CREATE_TABLES_ON_STARTUP=true` can create missing tables from the current SQLAlchemy models for local development. **The database schema is provisional and is not finalized**; review it with the agents before approving the table design. The Alembic environment exists, but versioned migration revisions are still pending. Startup table creation is not a replacement for production migrations.

### 4. Set up Google OAuth

Google sign-in requires a Google OAuth client. Set up a client in Google Cloud Console:

1. Select or create a Google Cloud project.
2. Configure the OAuth consent screen / Google Auth Platform branding and audience. While the app is in testing mode, add the Google accounts that will test sign-in as test users.
3. Create an OAuth client with application type **Web application**.
4. Add this under **Authorized JavaScript origins**:

   ```text
   http://localhost:5173
   ```

5. Add this under **Authorized redirect URIs**:

   ```text
   http://localhost:5173/api/v1/auth/oauth/callback/google
   ```

6. Copy the generated client ID and client secret into the local `backend/.env`:

   ```env
   OAUTH_GOOGLE_CLIENT_ID=your-google-client-id
   OAUTH_GOOGLE_CLIENT_SECRET=your-google-client-secret
   OAUTH_REDIRECT_BASE_URL=http://localhost:5173
   ```

Use values from the same Google Cloud project and OAuth client. Redirect URIs must match exactly, including scheme, host, port, and path. The JavaScript origin is only the origin (no API path); it is not a substitute for the redirect URI. Do not use `http://localhost:8000/auth/google` as the callback. Never share or commit the client secret. Restart the backend after changing its environment.

Vite proxies `/api` requests, including the Google callback, to FastAPI on port 8000. The sign-in route is `/api/v1/auth/oauth/google`; the callback route is `/api/v1/auth/oauth/callback/google`.

### 5. Install frontend dependencies and run the product

For a fresh checkout, install the root and frontend Node dependencies:

```powershell
npm run install:all
```

After completing backend setup and starting PostgreSQL/Redis, run from the repository root:

```powershell
npm run dev
```

This starts the backend and frontend together. Open:

- Product frontend: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`
- Backend health check: `http://localhost:8000/health`

### 6. Using the product

1. Register with an account or choose **Continue with Google** after OAuth has been configured.
2. Start a grievance and follow the guided discussion, selecting or entering the requested details.
3. Review the generated report and use its print action to print or save it as a PDF from the browser print dialog.
4. Sign out when finished. Saved grievance threads belong to the user account and are loaded again after that user signs back in; signing out does not delete them.

The discussion currently follows a scripted questionnaire and persists its conversation and report snapshot. It is not currently connected to a live AI agent.

## Tests and build

From the repository root:

```powershell
npm run lint
npm run build
```

Backend tests:

```powershell
cd .\backend
.\.venv\Scripts\Activate.ps1
python -m pytest tests/integration -q
python -m pytest -q
cd ..
```

The grievance API is available at `/api/v1/grievances/`. Its list, read, create, update, and delete routes require authentication and only expose records owned by the current user.

## Production notes

The values above are for local development. Before deployment, use HTTPS and the production frontend origin/callback URI, set secure cookies, generate a strong `SECRET_KEY`, use unique database credentials, restrict CORS to trusted origins, set Redis passwords where appropriate, and configure trusted proxy hops. Do not use the Compose sample credentials in production. Plan and apply reviewed Alembic migrations before relying on a finalized production schema.
