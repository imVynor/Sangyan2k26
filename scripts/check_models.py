"""Shim to run ai/scripts/check_models.py from root."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from ai.scripts.check_models import main

if __name__ == "__main__":
    main()
