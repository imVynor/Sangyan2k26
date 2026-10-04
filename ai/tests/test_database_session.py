import asyncio

from ai.app.db.session import psycopg_event_loop_factory


def test_psycopg_event_loop_factory_uses_selector_loop():
    loop = psycopg_event_loop_factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
