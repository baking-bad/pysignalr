from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING
from typing import Any

from pysignalr.client import SignalRClient

if TYPE_CHECKING:
    from pysignalr.messages import CompletionMessage


async def on_open() -> None:
    print('Connected to the server')


async def on_close() -> None:
    print('Disconnected from the server')


async def on_message(message: list[dict[str, Any]]) -> None:
    print(f'Received message: {message}')


async def on_error(message: CompletionMessage) -> None:
    print(f'Received error: {message.error}')


async def main() -> None:
    client = SignalRClient('https://api.tzkt.io/v1/ws')

    client.on_open(on_open)
    client.on_close(on_close)
    client.on_error(on_error)
    client.on('operations', on_message)

    await asyncio.gather(
        client.run(),
        client.send('SubscribeToOperations', [{}]),
    )


with suppress(KeyboardInterrupt, asyncio.CancelledError):
    asyncio.run(main())
