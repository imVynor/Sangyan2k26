import os
import sys
import sqlalchemy

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


db_url = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:AniAnu%401203@localhost:5432/ai_knowledge")
engine = sqlalchemy.create_engine(db_url)

with engine.connect() as c:
    total_provisions = c.execute(sqlalchemy.text("SELECT count(*) FROM knowledge_provisions")).scalar()
    total_embeddings = c.execute(sqlalchemy.text("SELECT count(*) FROM knowledge_provision_embeddings")).scalar()
    print(f"Total provisions: {total_provisions}, Total embeddings: {total_embeddings}")

    queries = {
        "zerodha_dp": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ZERODHA' AND (source_text ILIKE '%dp%' OR source_text ILIKE '%depository participant%') LIMIT 3",
        "zerodha_brokerage": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ZERODHA' AND source_text ILIKE '%brokerage%' LIMIT 3",
        "zerodha_policy": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ZERODHA' AND source_class = 'ORGANISATION_POLICY' AND process IS NOT NULL LIMIT 3",
        "icici_brokerage": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ICICIDIRECT' AND source_text ILIKE '%brokerage%' LIMIT 3",
        "icici_escalation": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ICICIDIRECT' AND source_class = 'ORGANISATION_PROCEDURE' LIMIT 3",
        "angel_charges": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ANGELONE' AND source_text ILIKE '%charges%' LIMIT 3",
        "angel_escalation": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_ANGELONE' AND source_class = 'ORGANISATION_PROCEDURE' LIMIT 3",
        "upstox_brokerage": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_UPSTOX' AND source_text ILIKE '%brokerage%' LIMIT 3",
        "groww_grievance": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE organisation_id = 'ORG_GROWW' LIMIT 3",
        "sebi_mf": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'SEBI' AND (source_text ILIKE '%mutual fund%' OR source_text ILIKE '%standing instructions%') LIMIT 3",
        "sebi_prefunded": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'SEBI' AND source_text ILIKE '%pre-funded%' LIMIT 3",
        "sebi_circular": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'SEBI' AND (source_text ILIKE '%SEBI/HO%' OR source_text ILIKE '%circular%') LIMIT 3",
        "cdsl_investor": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'CDSL' LIMIT 3",
        "nsdl_grievance": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'NSDL' AND source_text ILIKE '%grievance%' LIMIT 3",
        "nsdl_charter": "SELECT provision_id, substring(source_text from 1 for 70) FROM knowledge_provisions WHERE authority = 'NSDL' AND source_text ILIKE '%charter%' LIMIT 3",
    }

    for k, q in queries.items():
        res = c.execute(sqlalchemy.text(q)).fetchall()
        print(f"\n=== {k} ===")
        for r in res:
            print(f"  {r[0]}: {r[1]}...")
