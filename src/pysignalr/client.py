from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from typing import Any

from pysignalr.exceptions import ServerError
from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionClientStreamMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import Message
from pysignalr.messages import MessageType
from pysignalr.messages import PingMessage
from pysignalr.messages import StreamInvocationMessage
from pysignalr.messages import StreamItemMessage
from pysignalr.protocol.json import JSONProtocol
from pysignalr.transport.websocket import DEFAULT_CONNECTION_TIMEOUT
from pysignalr.transport.websocket import DEFAULT_MAX_SIZE
from pysignalr.transport.websocket import DEFAULT_PING_INTERVAL
from pysignalr.transport.websocket import DEFAULT_RETRY_COUNT
from pysignalr.transport.websocket import DEFAULT_RETRY_MULTIPLIER
from pysignalr.transport.websocket import DEFAULT_RETRY_SLEEP
from pysignalr.transport.websocket import DEFAULT_SIGNALR_PING_INTERVAL
from pysignalr.transport.websocket import WebsocketTransport

if TYPE_CHECKING:
    import ssl

    from pysignalr.protocol.abstract import Protocol
    from pysignalr.transport.abstract import Transport


EmptyCallback = Callable[[], Awaitable[None]]
AnyCallback = Callable[[Any], Awaitable[Any | None]]
MessageCallback = Callable[[Message], Awaitable[None | Any]]
CompletionMessageCallback = Callable[[CompletionMessage], Awaitable[None]]

_logger = logging.getLogger('pysignalr.client')


class ClientStream:
    """
    Client-to-server streaming handle.

    Created via `SignalRClient.client_stream()` context manager. Use `send()`
    to push items and let the context manager handle `invoke()`/`complete()`.

    See https://learn.microsoft.com/en-us/aspnet/core/signalr/streaming#client-to-server-streaming

    Attributes:
        transport (Transport): The transport used to send stream messages.
        target (str): The target method name on the server.
        invocation_id (str): The unique identifier for this stream.
    """

    def __init__(self, transport: Transport, target: str) -> None:
        self.transport: Transport = transport
        self.target: str = target
        self.invocation_id: str = str(uuid.uuid4())

    async def send(self, item: Any) -> None:
        """
        Sends the next stream item to the server.

        Args:
            item (Any): The item payload to send.
        """
        await self.transport.send(StreamItemMessage(self.invocation_id, item))

    async def invoke(self) -> None:
        """
        Sends the `InvocationClientStreamMessage` to start the stream on the server.
        """
        await self.transport.send(InvocationClientStreamMessage([self.invocation_id], self.target, []))

    async def complete(self) -> None:
        """
        Sends a `CompletionClientStreamMessage` to signal the end of the stream.
        """
        await self.transport.send(CompletionClientStreamMessage(self.invocation_id))


class SignalRClient:
    """
    Async SignalR client.

    Wraps a `WebsocketTransport` and routes decoded messages to user-registered
    callbacks.  Supports server-to-client streaming (`stream()`), client-to-server
    streaming (`client_stream()`), and client results (returning a value from
    an `on()` callback).

    Args:
        url (str): The SignalR hub URL (http/https; upgraded to ws/wss for the connection).
        protocol (Protocol | None): Message protocol. Defaults to `JSONProtocol`.
        headers (dict[str, str] | None): Extra HTTP headers included in the WebSocket handshake.
        ping_interval (int): WebSocket-level ping interval in seconds.
        signalr_ping_interval (int): SignalR-level keepalive ping interval in seconds.
        connection_timeout (int): Timeout in seconds waiting for the WebSocket connection.
        max_size (int | None): Maximum WebSocket frame size in bytes (`None` for unlimited).
        retry_sleep (float): Initial delay in seconds between reconnection attempts.
        retry_multiplier (float): Exponential backoff multiplier applied to `retry_sleep`.
        retry_count (int): Maximum number of consecutive reconnection attempts.
        access_token_factory (Callable[[], str] | None): Called before each connection to obtain a bearer token for the `Authorization` header.
        ssl (ssl.SSLContext | None): Custom SSL context for both HTTP negotiation and the WebSocket connection.
    """

    def __init__(
        self,
        url: str,
        protocol: Protocol | None = None,
        headers: dict[str, str] | None = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        signalr_ping_interval: int = DEFAULT_SIGNALR_PING_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        max_size: int | None = DEFAULT_MAX_SIZE,
        retry_sleep: float = DEFAULT_RETRY_SLEEP,
        retry_multiplier: float = DEFAULT_RETRY_MULTIPLIER,
        retry_count: int = DEFAULT_RETRY_COUNT,
        access_token_factory: Callable[[], str] | None = None,
        ssl: ssl.SSLContext | None = None,
    ) -> None:
        self._url = url
        self._protocol = protocol or JSONProtocol()
        self._headers = headers or {}
        self._access_token_factory = access_token_factory
        self._ssl = ssl

        self._message_handlers: defaultdict[str, list[MessageCallback | None]] = defaultdict(list)
        self._stream_handlers: dict[
            str, tuple[MessageCallback | None, MessageCallback | None, CompletionMessageCallback | None]
        ] = {}
        self._invocation_handlers: dict[str, MessageCallback | None] = {}

        self._transport = WebsocketTransport(
            url=self._url,
            protocol=self._protocol,
            callback=self._on_message,
            headers=self._headers,
            ping_interval=ping_interval,
            signalr_ping_interval=signalr_ping_interval,
            retry_sleep=retry_sleep,
            retry_multiplier=retry_multiplier,
            retry_count=retry_count,
            connection_timeout=connection_timeout,
            max_size=max_size,
            access_token_factory=access_token_factory,
            ssl=ssl,
        )
        self._error_callback: CompletionMessageCallback | None = None

    async def run(self) -> None:
        """
        Runs the SignalR client, managing the connection lifecycle.
        """
        await self._transport.run()

    def on(self, event: str, callback: AnyCallback) -> None:
        """
        Registers a callback for a hub method invocation.

        If the callback returns a value and the invocation has an `invocation_id`,
        the result is sent back to the server as a `CompletionMessage` (client results).

        Args:
            event (str): The hub method name to listen for.
            callback (AnyCallback): Async callable invoked with the message arguments.
        """
        self._message_handlers[event].append(callback)

    def on_open(self, callback: EmptyCallback) -> None:
        """
        Registers a callback function to be called when the connection is opened.

        Args:
            callback (EmptyCallback): The callback function.
        """
        self._transport.on_open(callback)

    def on_close(self, callback: EmptyCallback) -> None:
        """
        Registers a callback function to be called when the connection is closed.

        Args:
            callback (EmptyCallback): The callback function.
        """
        self._transport.on_close(callback)

    def on_error(self, callback: CompletionMessageCallback) -> None:
        """
        Registers a global error callback invoked on `CompletionMessage` errors.

        Stream-specific `on_error` callbacks (from `stream()`) take priority;
        this callback is used as a fallback when no stream-specific handler exists.

        Args:
            callback (CompletionMessageCallback): Async callable receiving the error message.
        """
        self._error_callback = callback

    async def send(
        self,
        method: str,
        arguments: list[dict[str, Any]],
        on_invocation: MessageCallback | None = None,
    ) -> None:
        """
        Invokes a hub method on the server.

        Without `on_invocation` this is a fire-and-forget call (no `invocationId`).
        With a callback, an `invocationId` is generated and the server's
        `CompletionMessage` response is routed to the callback.

        Args:
            method (str): The hub method name to invoke.
            arguments (list[dict[str, Any]]): The arguments to pass to the method.
            on_invocation (MessageCallback | None): Optional callback for the completion response.
        """
        invocation_id: str | None = None
        if on_invocation is not None:
            invocation_id = str(uuid.uuid4())
            self._invocation_handlers[invocation_id] = on_invocation
        message = InvocationMessage(invocation_id, method, arguments, self._headers)
        await self._transport.send(message)

    async def stream(
        self,
        event: str,
        event_params: list[str],
        on_next: MessageCallback | None = None,
        on_complete: MessageCallback | None = None,
        on_error: CompletionMessageCallback | None = None,
    ) -> None:
        """
        Starts a server-to-client streaming invocation.

        The server responds with zero or more `StreamItemMessage` routed to
        `on_next`, followed by a `CompletionMessage` routed to `on_complete`.

        Args:
            event (str): The hub method name to stream from.
            event_params (list[str]): The arguments for the streaming method.
            on_next (MessageCallback | None): Called with each stream item's payload.
            on_complete (MessageCallback | None): Called on the final `CompletionMessage`.
            on_error (CompletionMessageCallback | None): Called on error; falls back to global `on_error`.
        """
        invocation_id = str(uuid.uuid4())
        message = StreamInvocationMessage(invocation_id, event, event_params, self._headers)
        self._invocation_handlers[invocation_id] = on_complete
        self._stream_handlers[invocation_id] = (on_next, on_complete, on_error)
        await self._transport.send(message)

    @asynccontextmanager
    async def client_stream(self, target: str) -> AsyncIterator[ClientStream]:
        """
        Context manager for client-to-server streaming.

        Args:
            target (str): The target method name on the server.

        Yields:
            ClientStream: The client stream instance.
        """
        stream = ClientStream(self._transport, target)
        await stream.invoke()
        yield stream
        await stream.complete()

    async def _on_message(self, message: Message) -> None:
        """
        Main message dispatcher; routes decoded messages to type-specific handlers.

        Args:
            message (Message): The decoded message from the transport layer.
        """
        if message.type == MessageType.invocation_binding_failure:  # type: ignore[attr-defined]
            raise ServerError(str(message))

        elif isinstance(message, PingMessage):
            pass

        elif isinstance(message, InvocationMessage):
            await self._on_invocation_message(message)

        elif isinstance(message, CloseMessage):
            await self._on_close_message(message)

        elif isinstance(message, CompletionMessage):
            await self._on_completion_message(message)

        elif isinstance(message, StreamItemMessage):
            await self._on_stream_item_message(message)

        elif isinstance(message, StreamInvocationMessage):
            pass

        elif isinstance(message, CancelInvocationMessage):
            await self._on_cancel_invocation_message(message)

        else:
            raise NotImplementedError

    async def _on_invocation_message(self, message: InvocationMessage) -> None:
        """
        Handles a server-initiated hub method invocation.

        Looks up registered `on()` callbacks for `message.target`. If the server
        expects a response (`invocation_id is not None`), sends back a
        `CompletionMessage` with the callback's return value or error.

        Args:
            message (InvocationMessage): The invocation message from the server.
        """
        invocation_id = message.invocation_id
        callbacks = [callback for callback in self._message_handlers[message.target] if callback]

        if not callbacks:
            _logger.warning("No client method with the name '%s' found.", message.target)
            if invocation_id is not None:
                _logger.error(
                    "No result given for '%s' method and invocation ID '%s'.",
                    message.target,
                    invocation_id,
                )
                await self._transport.send(
                    CompletionMessage(invocation_id=invocation_id, error="Client didn't provide a result.")
                )
            return None

        if invocation_id is not None and len(callbacks) > 1:
            _logger.error("Multiple results provided for '%s'. Sending error to server.", message.target)
            await self._transport.send(
                CompletionMessage(invocation_id=invocation_id, error='Client provided multiple results.')
            )
            return None

        for callback in callbacks:
            try:
                res = await callback(message.arguments)
                if res:
                    if invocation_id is not None:
                        await self._transport.send(CompletionMessage(invocation_id=invocation_id, result=res))
                    else:
                        _logger.warning(
                            "Result given for '%s' method but server is not expecting a result.", message.target
                        )
                elif invocation_id is not None:
                    _logger.error(
                        "No result given for '%s' method and invocation ID '%s'.",
                        message.target,
                        invocation_id,
                    )
                    await self._transport.send(
                        CompletionMessage(
                            invocation_id=invocation_id,
                            error="Client didn't provide a result.",
                        )
                    )
            except Exception as exc:
                _logger.error("A callback for the method '%s' threw error '%s'.", message.target, exc)
                if invocation_id is None:
                    raise exc
                await self._transport.send(CompletionMessage(invocation_id=invocation_id, error=str(exc)))

        return None

    async def _on_completion_message(self, message: CompletionMessage) -> None:
        """
        Handles a completion message from the server.

        On error: routes to the stream-specific `on_error` if the invocation is a
        stream, otherwise to the global `on_error` callback.  Cleans up stream and
        invocation handler entries regardless of success or failure.

        Args:
            message (CompletionMessage): The completion message from the server.
        """
        if message.error:
            stream_handler = self._stream_handlers.get(message.invocation_id)
            if stream_handler is not None:
                _, _, on_error = stream_handler
                if on_error is not None:
                    await on_error(message)
                elif self._error_callback is not None:
                    await self._error_callback(message)
                else:
                    raise RuntimeError('Error callback is not set')
            elif self._error_callback is not None:
                await self._error_callback(message)
            else:
                raise RuntimeError('Error callback is not set')

        self._stream_handlers.pop(message.invocation_id, None)
        callback = self._invocation_handlers.pop(message.invocation_id, None)
        if callback is not None:
            await callback(message)

    async def _on_stream_item_message(self, message: StreamItemMessage) -> None:
        """
        Forwards a stream item to the `on_next` callback registered via `stream()`.

        Args:
            message (StreamItemMessage): The stream item message from the server.
        """
        callback, _, _ = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message.item)

    async def _on_cancel_invocation_message(self, message: CancelInvocationMessage) -> None:
        """
        Handles a cancel invocation message by forwarding it to the stream's `on_error` callback.

        Args:
            message (CancelInvocationMessage): The cancel invocation message from the server.
        """
        _, _, callback = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message)  # type: ignore[arg-type]

    async def _on_close_message(self, message: CloseMessage) -> None:
        """
        Handles a close message from the server.

        Raises `ServerError` if the close message contains an error.

        Args:
            message (CloseMessage): The close message from the server.
        """
        if message.error:
            raise ServerError(message.error)
