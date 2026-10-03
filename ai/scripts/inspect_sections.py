import os
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:AniAnu%401203@localhost:5432/ai_knowledge")
engine = create_engine(db_url)
with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, document_id, section_key, heading, length(content) FROM document_sections LIMIT 10")).fetchall()
    print("Found", len(rows), "sections:")
    for r in rows:
        print(f"ID={r[0]}, doc={r[1]}, key={r[2]}, heading={r[3]!r}, length={r[4]}")
