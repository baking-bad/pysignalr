import asyncio
import logging
from contextlib import suppress
from unittest.async_case import IsolatedAsyncioTestCase

from pysignalr.client import SignalRClient

logging.basicConfig(level=logging.DEBUG)


class TestPysignalr(IsolatedAsyncioTestCase):
    async def test_connection(self) -> None:
        url = 'https://api.tzkt.io/v1/events'
        client = SignalRClient(url)

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            await task
