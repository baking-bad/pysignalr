# pysignalr

[![GitHub stars](https://img.shields.io/github/stars/baking-bad/pysignalr?color=2c2c2c&style=plain)](https://github.com/baking-bad/pysignalr)
[![Latest stable release](https://img.shields.io/github/v/release/baking-bad/pysignalr?label=stable%20release&color=2c2c2c)](https://github.com/baking-bad/pysignalr/releases)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pysignalr?color=2c2c2c)](https://www.python.org)
[![License: MIT](https://img.shields.io/github/license/baking-bad/pysignalr?color=2c2c2c)](https://github.com/baking-bad/pysignalr/blob/master/LICENSE)
<br>
[![PyPI monthly downloads](https://img.shields.io/pypi/dm/pysignalr?color=2c2c2c)](https://pypi.org/project/pysignalr/)
[![GitHub issues](https://img.shields.io/github/issues/baking-bad/pysignalr?color=2c2c2c)](https://github.com/baking-bad/pysignalr/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/baking-bad/pysignalr?color=2c2c2c)](https://github.com/baking-bad/pysignalr/pulls)

**pysignalr** is a modern, reliable, and async-ready client for the [SignalR protocol](https://docs.microsoft.com/en-us/aspnet/core/signalr/introduction?view=aspnetcore-5.0). This project started as an asyncio fork of mandrewcito's [signalrcore](https://github.com/mandrewcito/signalrcore) library and ended up as a complete rewrite.

## Table of Contents

1. [Installation](#installation)
2. [Basic Usage](#basic-usage)
3. [Usage with Token Authentication](#usage-with-token-authentication)
4. [API Reference](#api-reference)
5. [License](#license)

## Installation

To install `pysignalr`, simply use pip:

```bash
pip install pysignalr
```

## Basic Usage

Let's connect to [TzKT](https://tzkt.io/), an API and block explorer of Tezos blockchain, and subscribe to all operations:

```python
import asyncio
from contextlib import suppress
from typing import Any
from typing import Dict
from typing import List

from pysignalr.client import SignalRClient
from pysignalr.messages import CompletionMessage

async def on_open() -> None:
    print('Connected to the server')

async def on_close() -> None:
    print('Disconnected from the server')

async def on_message(message: List[Dict[str, Any]]) -> None:
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

async def main() -> None:
    client = SignalRClient('https://api.tzkt.io/v1/ws')

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
```

## Usage with Token Authentication

To connect to the SignalR server using token authentication:

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
    return "your_access_token_here"

async def main() -> None:
    client = SignalRClient(
        url='https://api.tzkt.io/v1/ws',
        access_token_factory=token_factory,
        headers={"mycustomheader": "mycustomheadervalue"},
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
```

## API Reference

### `SignalRClient`

#### Parameters

- `url` (str): The SignalR server URL.
- `access_token_factory` (Callable[[], str], optional): A function that returns the access token.
- `headers` (Dict[str, str], optional): Additional headers to include in the WebSocket handshake.

#### Methods

- `on_open(callback: Callable[[], Awaitable[None]])`: Set the callback for connection open event.
- `on_close(callback: Callable[[], Awaitable[None]])`: Set the callback for connection close event.
- `on_error(callback: Callable[[CompletionMessage], Awaitable[None]])`: Set the callback for error events.
- `on(event: str, callback: Callable[[List[Dict[str, Any]]], Awaitable[Any | None]])`: Set the callback for a specific event.
- `send(method: str, args: List[Any])`: Send a message to the server.

### `CompletionMessage`

A message received from the server upon completion of a method invocation.

#### Attributes

- `error` (str): The error message, if any.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
