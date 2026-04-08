# pysignalr

Async SignalR client built on `websockets` and `aiohttp`.

## Commands

```bash
make install      # Install dependencies with uv
make lint         # black + ruff + mypy (strict)
make test         # pytest with coverage
make all          # lint + test

# Single test
pytest --asyncio-mode=auto -s -v tests/test_pysignalr/test_pysignalr.py::test_name
```

## Architecture

**Client**: `SignalRClient` (`src/pysignalr/client.py`) — user-facing API wrapping transport + message routing.

**Transport** (`src/pysignalr/transport/`):

- `WebsocketTransport` — full lifecycle: HTTP negotiation (aiohttp), WS handshake, reconnect with exponential backoff, keepalive pings, message dispatch. Supports standard and Azure SignalR negotiation.
- `BaseWebsocketTransport` — simplified subclass, no handshake/keepalive.

**Protocol** (`src/pysignalr/protocol/`):

- `JSONProtocol` (default) — orjson, record separator `\x1e`.
- `MessagePackProtocol` — msgpack, varint-prefixed length frames.

**Messages** (`src/pysignalr/messages.py`): Dataclass hierarchy rooted at `Message`. Subclasses register via `__init_subclass__(type_=...)`. `dump()` → camelCase dict.

**Flow**: raw bytes → `Protocol.decode()` → `Message` → `WebsocketTransport._callback` → `SignalRClient._on_message()` → handler callbacks.

**Streaming**: server→client (`client.stream()`), client→server (`client.client_stream()` context manager), client results (callback return value → `CompletionMessage`).

**Backoff** (`src/pysignalr/__init__.py`): `__aiter__` with reset on success, exponential growth on failure, cap at `BACKOFF_MAX`. `TimeoutError`/`InvalidHandshake` → `NegotiationFailure`.

## Tests

- `test_client.py` — unit tests for `_on_message()` routing, `send()`, `stream()`, `client_stream()`, error routing (AsyncMock, no network)
- `test_transport.py` — unit tests for transport (SSL, negotiate, backoff, state machine, keepalive, handshake, `_loop`)
- `test_backoff.py` — unit tests for backoff logic
- `test_messagepack.py` — MessagePack encode/decode + varint helpers + `CompletionMessage` roundtrips
- `test_json_protocol.py` — JSON protocol encode/decode + handshake + all message types
- `test_messages.py` — `Message.dump()` idempotency, camelCase conversion, `streamIds`/`invocationId` handling
- `test_utils.py` — URL helpers
- `test_pysignalr.py` — integration tests (Docker, AspNetAuthExample container, auto-skipped without Docker)

Hub methods available: `SendMessage`, `AddToGroup`, `SendMessageToGroup`, `GetCurrentTime` on `weatherHub`.

## Gotchas

**Docker IP lookup**: On Docker Desktop/rootless, `container.attrs['NetworkSettings']['IPAddress']` is empty. Fall back to `NetworkSettings['Networks'][<first_network>]['IPAddress']`.

**Patching `asyncio.sleep`**: Patch the module-local reference (`pysignalr.asyncio.sleep` or `pysignalr.transport.websocket.asyncio.sleep`), not the global.

**Stopping retry loops in tests**: Raise `asyncio.CancelledError` (a `BaseException`) from a mock — not caught by `except Exception`, cleanly terminates the loop.
