"""CLI entry point for running SANGYAN multi-turn clarification evaluation."""

import asyncio
from ai.scripts.evaluate_clarification import main

if __name__ == "__main__":
    asyncio.run(main())
