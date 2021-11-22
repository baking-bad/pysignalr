# pysignalr
[![Pypi](https://img.shields.io/pypi/v/pysignalr.svg)](https://pypi.org/project/pysignalr/)

**pysignalr** is a modern, reliable and async-ready client for [SignalR protocol](https://docs.microsoft.com/en-us/aspnet/core/signalr/introduction?view=aspnetcore-5.0). This project started as an asyncio fork of mandrewcito's [signalrcore](https://github.com/mandrewcito/signalrcore) library.

## Usage

Let's connect to [TzKT](https://tzkt.io/), indexer and explorer of Tezos blockchain, and subscribe to all operations:

```python
import asyncio
from contextlib import suppress
from typing import Any, Dict, List
from pysignalr.client import SignalRClient
from pysignalr.messages import CompletionMessage


async def on_open() -> None:
    print('Connected to the server')


async def on_close() -> None:
    print('Disconnected from the server')


async def on_message(message: List[Dict[str, Any]]) -> None:
    print(f'Received message: {message}')


async def on_error(message: CompletionMessage) -> None:
    print(f'Received error: {message.error}')


async def main():
    client = SignalRClient('https://api.tzkt.io/v1/events')

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
```

## Roadmap to the stable release

- [ ] More documentation, both internal and user.
- [ ] Integration tests with containerized ASP hello-world server.
- [ ] Ensure that authentication works correctly.
