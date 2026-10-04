"""Shim to run ai/scripts/check_db.py from workspace root."""

import asyncio
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from ai.scripts.check_db import check_database

if __name__ == "__main__":
    asyncio.run(check_database())
