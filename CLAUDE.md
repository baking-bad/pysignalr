# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General

- Spend tokens wisely.
- Keep commit messages brief.
- When there's Makefile in the root directory consider using it.

## Python

- Use typing annotations

## Commands

```bash
make install      # Install dependencies with uv
make lint         # Run black + ruff + mypy (strict)
make test         # Run pytest with coverage
make all          # lint + test

# Individual tools
make black        # Format
make ruff         # Lint/fix
make mypy         # Type-check

# Run a single test
pytest --asyncio-mode=auto -s -v tests/test_pysignalr/test_pysignalr.py::test_name
```

## Architecture

The library is an async SignalR client built on `websockets` and `aiohttp`.

**Entry point**: `SignalRClient` (`src/pysignalr/client.py`) — user-facing API. Wraps `WebsocketTransport` and routes incoming messages to registered callbacks.

**Transport layer** (`src/pysignalr/transport/`):
- `WebsocketTransport` manages the full lifecycle: HTTP negotiation (via `aiohttp`), WebSocket handshake, reconnection with exponential backoff, keepalive pings, and message dispatch.
- `BaseWebsocketTransport` subclass disables handshake and keepalive for simplified use cases.
- Negotiation supports both standard SignalR and Azure SignalR redirects.

**Protocol layer** (`src/pysignalr/protocol/`):
- `Protocol` (abstract) defines `encode`, `decode`, `decode_handshake`.
- `JSONProtocol` — default, uses `orjson`, record separator `\x1e`.
- `MessagePackProtocol` — binary alternative using `msgpack`.

**Messages** (`src/pysignalr/messages.py`): Dataclass hierarchy rooted at `Message`. Each subclass registers its `MessageType` via `__init_subclass__(type_=...)`. `dump()` serializes to dict with camelCase keys (`invocationId`, `streamIds`).

**Message flow**: raw bytes → `Protocol.decode()` → `Message` subclass → `WebsocketTransport._callback` → `SignalRClient._on_message()` → registered handler callbacks.

**Streaming patterns**:
- Server→client streaming: `client.stream()` with `on_next`/`on_complete`/`on_error` callbacks.
- Client→server streaming: `async with client.client_stream(target) as stream:` context manager.
- Client results: `client.on(event, callback)` where callback returns a value — sent back as `CompletionMessage`.
