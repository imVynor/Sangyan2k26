# 🚀 Sangyan — AI Agent Platform

A modern AI-agent application with a React frontend and a FastAPI backend, designed to support user authentication, persistent conversations, AI-agent interactions, and conversation-context management.

---

## 🌟 Key Highlights

- **FastAPI Backend:** Python-based REST API with a modular application structure.
- **PostgreSQL Persistence:** Durable storage for users, conversation threads, messages, and related application data.
- **Redis Integration:** Support for caching, session storage, rate limiting, and background-task infrastructure.
- **Google OAuth Authentication:** Planned integration for secure user authentication and account management.
- **Persistent Chat History:** Store and retrieve conversations across browser sessions.
- **AI-Agent Integration:** Connect user messages and supported image inputs to the AI agent and return responses to the frontend.
- **Conversation Context Management:** Use PostgreSQL as the source of truth and Redis to cache recent messages or summaries where appropriate.
- **Database Migrations:** Use Alembic to manage database schema changes.
- **Containerized Development:** Run PostgreSQL and Redis using Docker Compose while developing the FastAPI application locally.
- **React Frontend:** Integrate the backend with the existing React application through REST APIs.

---

## 📁 Project Structure

```text
Sangyan2k26/
├── .gitignore
├── package.json
├── package-lock.json
├── README.md
│
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   └── src/
│       ├── config/
│       │   ├── settings.py
│       │   └── enums.py
│       │
│       ├── infrastructure/
│       │   └── database/
│       │       ├── __init__.py
│       │       ├── session.py
│       │       ├── initialize.py
│       │       ├── model.py
│       │       ├── models/
│       │       └── repositories/
│       │
│       └── interfaces/
│           └── main.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│
└── docker-compose.yml
```

*Note: This is a logical overview of the discussed architecture. The final structure should match the actual repository; authentication, chat services, API routers, and individual model files may be added or located elsewhere according to the existing codebase.*

---

## ⚡ Development Setup

### 1. Prerequisites

Install the following tools:

- Python version supported by the backend dependencies
- `uv`, if used by the backend's existing dependency configuration
- Node.js and npm
- Docker and Docker Compose
- Git

### 2. Start PostgreSQL and Redis

From the repository root, start the configured infrastructure services:

```bash
docker compose up -d postgres redis
```

Verify that the containers are running:

```bash
docker compose ps
```

Check PostgreSQL readiness:

```bash
docker exec sangyan-postgres \
  pg_isready -U sangyan -d sangyan_db
```

Check Redis connectivity:

```bash
docker exec sangyan-redis redis-cli ping
```

Expected Redis response:

```text
PONG
```

The commands above assume the Compose service and container names match the local configuration.

### 3. Configure Environment Variables

Create the backend's local `.env` file using `.env.example` as the reference.

Example PostgreSQL settings for a backend running directly on the host:

```env
POSTGRES_USER=sangyan
POSTGRES_PASSWORD=local_dev_password
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sangyan_db
```

The application should use the database URL format supported by its SQLAlchemy configuration:

```text
postgresql+asyncpg://sangyan:local_dev_password@localhost:5432/sangyan_db
```

Use your existing settings implementation to determine whether the URL is constructed from individual variables or supplied through `DATABASE_URL`.

For Google OAuth, configure the client credentials and redirect base URL expected by the backend:

```env
OAUTH_REDIRECT_BASE_URL=http://localhost:8000
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
```

The actual OAuth callback URI must match the route implemented by the application. Do not assume the base URL alone is the callback endpoint.

Keep `.env` files and secrets out of version control.

### 4. Start the FastAPI Backend

Use the repository's existing Python environment and dependency manager. If the FastAPI entry point remains `backend/src/interfaces/main.py`, a possible development command is:

```bash
cd backend
uv run uvicorn src.interfaces.main:app --reload --port 8000
```

This command assumes that `backend` is the Python project root, the `src` package is importable in that environment, and the ASGI application is named `app`. Adjust it if the existing project configuration specifies another entry point.

- **Backend API:** `http://localhost:8000`
- **Interactive API documentation:** `http://localhost:8000/docs`
- **Health endpoint:** `http://localhost:8000/health`

The health endpoint is based on the currently discussed `/health` route; verify it against the running application.

### 5. Start the React Frontend

From the repository root:

```bash
npm install
npm run dev
```

If the frontend uses a separate package configuration, install its dependencies and run its development server according to the existing `package.json`.

Configure the Vite `/api` proxy to point to the FastAPI backend if that matches the frontend's API client. The backend port is `8000` in this development setup.

---

## 🗄️ Database Architecture

### PostgreSQL

PostgreSQL is the durable source of truth for application data.

The planned core entities are:

- **Users:** Application account information.
- **User identities:** OAuth-provider identity mappings, if maintained separately.
- **Threads:** Conversations owned by users.
- **Messages:** User, assistant, and optional tool messages associated with a thread.
- **Attachments:** Optional metadata and file references for image or other supported inputs.

Use SQLAlchemy for database access and Alembic for schema migrations. The precise schema should follow the project's existing base classes, UUID mixins, timestamp mixins, and soft-delete conventions.

### Redis

Redis provides supporting infrastructure rather than replacing PostgreSQL as the permanent conversation store.

The intended responsibilities are:

- Application caching
- Session storage
- Rate limiting
- Taskiq background-job infrastructure, if enabled
- Optional recent-message or conversation-summary caching

The project configuration defines separate Redis database indices for some of these purposes. Verify the actual settings and enabled backends before assuming every component uses Redis.

If cached conversation context is missing or expires, the application should be able to reconstruct it from PostgreSQL.

---

## 🔐 Authentication

The planned authentication flow is:

1. The frontend initiates Google OAuth login.
2. The backend handles the OAuth callback.
3. The backend identifies or creates the corresponding application user.
4. The application establishes an authenticated session.
5. Protected endpoints derive the current user from that session.
6. Logout invalidates the session.

Authentication must be verified before accessing private conversation data. A client-supplied thread or user UUID must not be sufficient to authorize access.

The exact session-cookie settings, OAuth callback route, and current-user endpoint depend on the existing implementation.

---

## 💬 Chat and Conversation Workflow

The intended request flow is:

```text
React Frontend
      |
      v
FastAPI Chat Endpoint
      |
      v
Authenticate User
      |
      v
Verify Thread Ownership
      |
      v
Persist User Message
      |
      v
Load Conversation Context
(PostgreSQL + optional Redis cache)
      |
      v
Invoke AI Agent
      |
      v
Persist Assistant Response
      |
      v
Return Response to Frontend
```

The backend should preserve the user's message even if agent processing fails. Failure and retry handling should be designed so that messages are not silently lost or duplicated.

For image inputs, store attachment metadata and a reference to the actual image in suitable file storage. Avoid storing large binary images directly in ordinary message-text fields.

---

## 📡 Proposed API Reference

The following endpoints are proposed for the application; they are not all confirmed to exist in the current codebase.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Check backend health |
| `GET` | `/api/v1/auth/me` | Retrieve the authenticated user |
| `POST` | `/api/v1/threads` | Create a conversation |
| `GET` | `/api/v1/threads` | List the current user's conversations |
| `GET` | `/api/v1/threads/{thread_uuid}/messages` | Retrieve conversation history |
| `POST` | `/api/v1/threads/{thread_uuid}/messages` | Submit a message and initiate agent processing |
| `PATCH` | `/api/v1/threads/{thread_uuid}` | Update thread metadata, such as its title |

The API contract should be finalized alongside the React frontend so that request payloads, response formats, error handling, and authentication behavior remain consistent.

---

## 🧪 Testing and Verification

The backend should be validated in stages:

1. **Infrastructure tests:** Verify PostgreSQL and Redis connectivity.
2. **Database tests:** Apply migrations to an empty database and verify model discovery.
3. **Authentication tests:** Verify login, session handling, protected routes, and logout.
4. **Chat API tests:** Verify thread creation, message persistence, and history retrieval.
5. **Authorization tests:** Ensure users cannot read or modify other users' threads.
6. **Agent integration tests:** Verify input handling, context loading, response persistence, and failure handling.
7. **End-to-end tests:** Verify the full workflow through the React frontend.

---

## 🚀 Implementation Roadmap

- [ ] **Phase 1:** Finalize environment configuration and database connectivity.
- [ ] **Phase 2:** Verify SQLAlchemy models and establish Alembic migrations.
- [ ] **Phase 3:** Implement and test authentication.
- [ ] **Phase 4:** Implement user-owned threads and persistent messages.
- [ ] **Phase 5:** Integrate the AI agent with the chat workflow.
- [ ] **Phase 6:** Add Redis context caching and any required background workers.
- [ ] **Phase 7:** Complete frontend integration, security checks, and deployment preparation.

The implementation should reuse existing backend modules wherever possible rather than duplicating functionality that is already available.
