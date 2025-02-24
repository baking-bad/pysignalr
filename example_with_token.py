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


async def on_client_result(message: list[dict[str, Any]]) -> str:
    """
    The server can request a result from a client.
    This requires the server to use ISingleClientProxy.InvokeAsync and the client to return a result from its .On handler.
    https://learn.microsoft.com/en-us/aspnet/core/signalr/hubs?view=aspnetcore-9.0#client-results
    """
    print(f'Received message: {message}')
    return 'reply'


async def on_error(message: CompletionMessage) -> None:
    print(f'Received error: {message.error}')


def token_factory() -> str:
    # Replace with logic to fetch or generate the token
    return 'your_access_token_here'


async def main() -> None:
    client = SignalRClient(
        url='https://api.tzkt.io/v1/ws',
        access_token_factory=token_factory,
        headers={'mycustomheader': 'mycustomheadervalue'},
    )

    client.on_open(on_open)
    client.on_close(on_close)
    client.on_error(on_error)
    client.on('operations', on_message)
    client.on('client_result', on_client_result)

    await asyncio.gather(
        client.run(),
        client.send('SubscribeToOperations', [{}]),
    )


with suppress(KeyboardInterrupt, asyncio.CancelledError):
    asyncio.run(main())
