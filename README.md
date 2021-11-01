# pysignalr
[![Pypi](https://img.shields.io/pypi/v/pysignalr.svg)](https://pypi.org/project/pysignalr/)

**pysignalr** is a modern, reliable and async-ready client for [SignalR protocol](https://docs.microsoft.com/en-us/aspnet/core/signalr/introduction?view=aspnetcore-5.0). This project started as an asyncio fork of mandrewcito's [signalrcore](https://github.com/mandrewcito/signalrcore) library.

## Usage

```python
import logging
import asyncio
from pysignalr.client import SignalRClient


async def on_connect():
    logging.info('Connected to the server')


async def on_message(message):
    logging.info('Message received: %s', message)


client = SignalRClient('wss://api.tzkt.io')
client.on_connect(on_connect)
client.on('channel', on_message)

try:
    await client.run()
except KeyboardInterrupt:
    pass
```

## Roadmap to the stable release

🌚
