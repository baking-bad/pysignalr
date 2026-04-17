# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to [Semantic Versioning].

## [Unreleased]

### Fixed

- Fixed `HandshakeRequestMessage` encoded as an empty MessagePack array when using `MessagepackProtocol` (handshake is always JSON per spec).

## [1.3.1] - 2026-04-11

### Added

- Added support for Python 3.14.
- Added `signalr_ping_interval` parameter to `SignalRClient` and `WebsocketTransport` (default: 15s, per `HubOptions.KeepAliveInterval`).

### Fixed

- Fixed SignalR Hub Protocol spec compliance in JSON and MessagePack codecs (`streamIds`, `invocationId`, `ResultKind`, headers, varint framing).
- Fixed `Message.dump()` mutating the message instance.
- Fixed `CompletionClientStreamMessage` using wrong message type.
- Fixed `send()` always generating `invocationId`, preventing non-blocking invocations.
- Fixed stream error routing: `on_complete` called after error, missing `on_error` fallback, `KeyError` on unknown invocation ID.
- Fixed client results treating falsy return values (`0`, `False`, `[]`) as missing.
- Fixed custom SSL context not being applied to HTTP negotiation.

### Changed

- Switched build tooling from Poetry to uv.
- Updated `websockets` library to 16.0.
- Changed default WebSocket `ping_interval` from 10s to 20s to match `websockets` library defaults.
- Applied `connection_timeout` as `close_timeout` in WebSocket connections.

## [1.3.0] - 2025-04-29

## Changed

- Updated `websockets` library to 15.0.

## Removed

- Dropped support for Python 3.9 (it was broken for several releases anyway).

## [1.2.0] - 2025-03-03

### Added

- Added support for client results from a server method. ([AntoninoBonanno](https://github.com/AntoninoBonann))

## [1.1.0] - 2024-11-30

### Fixed

- Fixed reconnection logic ([olalid](https://github.com/olalid))

### Added

- Added `access_token_factory` argument to allow custom token generation. ([caiolombello](https://github.com/caiolombello))
- Added an option to supply external `ssl` context. ([olalid](https://github.com/olalid))
- Added example ASP server with role-based JWT authentication for testing purposes. ([caiolombello](https://github.com/caiolombello))
- Added support for 3.13.

### Removed

- Dropped support for Python 3.8.

### Other

- Significantly improved user and internal documentation, test coverage. ([caiolombello](https://github.com/caiolombello))
- Loosened version constraints for `websockets` and other dependencies. ([MichaelMKKelly](https://github.com/MichaelMKKelly))

## [1.0.0] - 2024-03-07

### Added

- Python 3.12 support.
- `BaseJSONProtocol` and `BaseWebsocketTransport` classes for plain JSON over WebSockets and custom protocols.

### Other

- `websockets` library updated to 12.0.
- Use faster `orjson` library for JSON deserialization.

## [0.2.0] - 2023-04-07

### Added

- Python 3.11 support.
- macOS and arm64 support.

### Fixed

- Fixed client streaming methods.

### Other

- `websockets` library updated to 10.4.

## [0.1.2] - 2022-05-24

### Improved

- Now `max_size` argument can be None to disable message size limit. 

### Fixed

- Fixed crash with "Cannot connect while not disconnected".

### Other

- `websockets` library updated to 10.3.

## [0.1.1] - 2022-01-06

### Fixed

- Fixed exceptions raised on server error.

## [0.1.0] - 2021-11-22

Initial release.

<!-- Links -->
[keep a changelog]: https://keepachangelog.com/en/1.0.0/
[semantic versioning]: https://semver.org/spec/v2.0.0.html

<!-- Versions -->
[Unreleased]: https://github.com/baking-bad/pysignalr/compare/1.3.1...HEAD
[1.3.1]: https://github.com/baking-bad/pysignalr/compare/1.3.0...1.3.1
[1.3.0]: https://github.com/baking-bad/pysignalr/compare/1.2.0...1.3.0
[1.2.0]: https://github.com/baking-bad/pysignalr/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/baking-bad/pysignalr/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/baking-bad/pysignalr/compare/0.2.0...1.0.0
[0.2.0]: https://github.com/baking-bad/pysignalr/compare/0.1.2...0.2.0
[0.1.2]: https://github.com/baking-bad/pysignalr/compare/0.1.1...0.1.2
[0.1.1]: https://github.com/baking-bad/pysignalr/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/baking-bad/pysignalr/releases/tag/0.1.0
