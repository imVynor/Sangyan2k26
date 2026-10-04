"""CLI entry point for running SANGYAN retrieval evaluation."""

import asyncio
from ai.scripts.evaluate_retrieval import main

if __name__ == "__main__":
    asyncio.run(main())
