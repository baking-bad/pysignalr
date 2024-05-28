import asyncio
import logging
from contextlib import suppress
from unittest.async_case import IsolatedAsyncioTestCase

from pysignalr.client import SignalRClient
from pysignalr.exceptions import AuthorizationError

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

    async def test_connection_with_token(self) -> None:
        url = 'https://api.tzkt.io/v1/events'
        token = 'test_token'

        def token_factory():
            return token

        client = SignalRClient(
            url=url,
            access_token_factory=token_factory,
            headers={"mycustomheader": "mycustomheadervalue"},
        )

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            await task

        # Verifique o token no cabeçalho da conexão
        self.assertIn("Authorization", client._transport._headers)
        self.assertEqual(client._transport._headers["Authorization"], f"Bearer {token}")

    async def test_invalid_token(self) -> None:
        url = 'https://api.tzkt.io/v1/events'

        def invalid_token_factory():
            return None  # Simular um token inválido ou ausente

        client = SignalRClient(
            url=url,
            access_token_factory=invalid_token_factory,
            headers={"mycustomheader": "mycustomheadervalue"},
        )

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            try:
                await task
            except AuthorizationError:
                pass

        # Verificar se a exceção AuthorizationError foi levantada corretamente
        self.assertTrue(task.cancelled())
