# Sangyan 2K26 - Implementation Status Report

**Report date:** October 4, 2026  
**Project:** Guided Financial Grievance Assistant  
**Status:** Core local-development workflow implemented; database schema remains provisional

## Executive summary

The project has a working React frontend and FastAPI backend for a guided financial-grievance workflow. PostgreSQL is used for user and grievance data, while Redis supports application caching, sessions, and rate limiting. The owner reports testing PostgreSQL and Redis, Google sign-in, the grievance discussion, report generation/printing, and saved-thread behavior across logout and sign-in.

The database table design is **not final**. Current SQLAlchemy models support the working application, but the schema and migration plan must be reviewed with the agents before they are approved as final. The Alembic migrations directory currently has no versioned migration revisions.

## Implemented and reported working

| Area | Current implementation and reported status |
|---|---|
| Frontend and backend | React/Vite frontend and FastAPI backend run locally. The frontend proxies API and health requests to the backend. |
| PostgreSQL | Stores user accounts and grievance snapshots. The owner reports that the database connection and data operations are working. |
| Redis | Configured for cache/session/rate-limit services. The owner reports that Redis is working. |
| Authentication | Password-based account flows and Google OAuth routes are implemented. The owner reports that Google sign-in is working after correcting the OAuth client callback configuration. |
| OAuth callback | The application sends Google to `http://localhost:5173/api/v1/auth/oauth/callback/google`. The Google client must keep this exact URI in its Authorized redirect URIs. |
| Grievance discussion | A guided, scripted conversation collects answers and builds report entries. The owner reports that the discussion flow is working. The current flow is scripted; a live AI agent is not configured. |
| Saving and resuming | Grievance snapshots contain the title, current step, messages, and report entries. The backend stores them per user; the frontend loads saved records after authentication. The owner reports that a thread remains available after logout and signing back in. |
| Report output | The frontend presents a report and has a print action. The owner reports that report generation/printing works. |
| Ownership protection | Grievance routes require an authenticated user and scope reads/updates/deletes to that user's records. |

The logout/resume behavior is intended to end the login session without deleting saved grievance data. Saved threads are application records, not browser-only session memory.

## Backend implementation

The backend currently includes:

- FastAPI application startup, health endpoint, API routing, and local development configuration.
- User, tier, role, API-key, rate-limit, and grievance modules.
- Password authentication, session cookies, CSRF handling, Google OAuth integration, and configurable Redis-backed sessions/rate limits.
- Grievance create, list, read, update, and delete endpoints under `/api/v1/grievances/`.
- Request/response validation for conversation messages, report entries, workflow step, and snapshot sizes.
- Unit and integration tests for authentication, OAuth behavior, users, API keys, rate limits, infrastructure, and grievances.

Relevant implementation locations:

- `backend/src/infrastructure/auth/` - authentication and OAuth setup.
- `backend/src/modules/grievance/` - grievance model, request schemas, and endpoints.
- `backend/src/infrastructure/database/` - database setup and session management.
- `backend/tests/` - unit and integration tests.
- `frontend/src/context/GrievanceContext.jsx` - load/save/resume workflow state.
- `frontend/src/components/ReportPanel.jsx` - report display and print action.

## Database schema and migration status

**The database schema is provisional and must not yet be treated as finalized.** The current runtime model includes users and a grievance snapshot record containing JSON message/entry data. This structure supports the current workflow, but the final table boundaries, relationships, constraints, indexes, data lifecycle, and migration strategy are pending review with the agents.

The Alembic environment exists, but `backend/migrations/versions/` currently contains no versioned migration revisions. Local development can create tables from SQLAlchemy models at startup; that is not a substitute for an approved, versioned production migration history.

Before schema sign-off:

1. Review the proposed schema with the agents and agree on the ownership and lifecycle of users, saved threads, messages, and report data.
2. Decide whether conversation/report JSON snapshots are appropriate long term or whether parts should become normalized relational tables.
3. Review deletion, retention, privacy, indexing, uniqueness, and cascade behavior.
4. Create and review the initial Alembic migration against a clean database.
5. Test both fresh installation and upgrade from any existing development data before calling the schema final.

## Validation completed so far

### Owner-reported manual checks

- PostgreSQL connection and data operations.
- Redis-backed application behavior.
- Google OAuth sign-in.
- Guided grievance discussion.
- Report generation/printing.
- Saved thread remains available after logout and subsequent sign-in.

### Automated and local checks previously run

- Focused OAuth and authentication setup tests: **32 passed**.
- Full backend test suite: **425 passed, 1 failed**.
- The one failure was `test_a_route_module_imports_on_its_own`; its subprocess failed on Windows with `WinError 10106` while Python initialized `_overlapped`/`asyncio`. It was not an OAuth or grievance assertion failure.
- Local frontend, backend health endpoint, FastAPI docs, and frontend health proxy returned HTTP 200 in a development-server smoke check.

The OAuth automated tests stub Google's token and profile endpoints; they validate the application flow but are not a substitute for a live Google-provider test. The live sign-in success above is reported by the owner.

## Recommended next steps

### Priority 1 - Finalize and version the data model

- Complete the agent review described above.
- Agree on canonical schema and data retention/deletion behavior.
- Add Alembic migration revisions, then verify clean-database setup and upgrade paths.
- Add/adjust model, API, and migration tests to match the approved schema.

### Priority 2 - Complete an end-to-end acceptance pass

- Test registration and password login, Google login, logout, and sign-in again.
- Create a grievance, progress through the discussion, print the report, leave the session, and confirm the same saved thread loads after signing back in.
- Verify one account cannot read or modify another account's grievances.
- Record the exact browser, OS, database, and Redis versions used for acceptance.

### Priority 3 - Make validation repeatable

- Resolve or isolate the Windows subprocess import failure and rerun the complete backend suite.
- Run frontend lint and production build, plus backend lint/type checks where configured.
- Add a repeatable local smoke-test checklist or script for service health and the primary user journey.

### Priority 4 - Prepare for deployment

- Review production secrets, secure-cookie settings, OAuth production origins/callback URI, CORS, HTTPS, and trusted proxy configuration.
- Plan database backups and restore testing, logging/monitoring, and operational error handling.
- Confirm that the current scripted discussion meets product requirements before deciding whether to add a live AI agent.

## Current limitations and cautions

- Database schema and migrations are pending agent review and approval.
- Google OAuth depends on the Google Cloud OAuth client having the exact redirect URI and the matching client ID/secret configured in the backend environment.
- The conversation is a scripted workflow; it is not currently backed by a live AI agent.
- The full backend test suite has one known Windows environment failure described above.
- Successful local development checks do not by themselves establish production readiness.

## Local run and quick checks

From the repository root:

```powershell
npm run dev
```

Local URLs:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- FastAPI docs: `http://localhost:8000/docs`

Do not include `.env` values, OAuth credentials, or other secrets in shared copies of this report.
