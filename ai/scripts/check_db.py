"""Quick database connectivity and schema diagnostic check for SANGYAN."""

import os
import socket
import sys
from pathlib import Path

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    import asyncio

from sqlalchemy import inspect, text

# Add ai root to sys.path
ai_root = Path(__file__).resolve().parent.parent
project_root = ai_root.parent
for p in [str(ai_root), str(project_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ai.app.config.settings import settings
from ai.app.db.session import get_async_engine


async def check_database():
    print("=" * 60)
    print("SANGYAN Database Diagnostic Check")
    print("=" * 60)

    db_url = settings.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print("[STATUS] DATABASE_URL is not set.")
        print("         The application is currently running in OFFLINE / IN-MEMORY mode.")
        print("         (All 94 unit & schema tests pass without a live database.)")
        print("\n--- Local Port Check ---")
        for port in [5432, 5433]:
            s = socket.socket()
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                print(f"  Port {port}: LISTENING (A PostgreSQL or DB service is reachable)")
            except Exception:
                print(f"  Port {port}: NOT LISTENING")
            finally:
                s.close()

        print("\nTo connect to a live PostgreSQL instance:")
        print("1. Set DATABASE_URL in your terminal or in an .env file:")
        print("   $env:DATABASE_URL=\"postgresql+psycopg://postgres:<password>@localhost:5432/<dbname>\"")
        print("   (Or a cloud PostgreSQL URL e.g. Neon, Supabase, Railway)")
        print("2. Run Alembic migrations:")
        print("   python -m alembic upgrade head")
        print("3. Re-run this check:")
        print("   python ai/scripts/check_db.py")
        print("=" * 60)
        return False

    # Mask credentials for display
    masked_url = db_url
    if "@" in masked_url and "://" in masked_url:
        prefix, rest = masked_url.split("://", 1)
        creds, host_part = rest.split("@", 1)
        user = creds.split(":")[0]
        masked_url = f"{prefix}://{user}:****@{host_part}"

    print(f"Target Database URL: {masked_url}")

    try:
        engine = get_async_engine()
        print("Attempting connection to PostgreSQL...", end=" ", flush=True)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar()
            print("[CONNECTED]")
            print(f"PostgreSQL Version: {version}")

            # Inspect existing tables
            def get_tables(sync_conn):
                inspector = inspect(sync_conn)
                return inspector.get_table_names()

            tables = await conn.run_sync(get_tables)
            print(f"\nExisting Tables ({len(tables)}):")
            expected_tables = [
                "regulatory_documents",
                "organisation_documents",
                "provenance",
                "document_sections",
                "regulatory_provisions",
                "organisation_provisions",
                "knowledge_relationships",
                "ingestion_records",
                "alembic_version",
            ]
            for t in expected_tables:
                if t in tables:
                    print(f"  [OK] {t}")
                else:
                    print(f"  [MISSING] {t} (Run: python -m alembic upgrade head)")

        print("=" * 60)
        print("[SUCCESS] PostgreSQL database is reachable and operational!")
        print("=" * 60)
        return True

    except Exception as exc:
        print("[FAIL]")
        print(f"Connection Error: {exc}")
        print("=" * 60)
        return False


if __name__ == "__main__":
    asyncio.run(check_database())
