from __future__ import annotations

import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any
from typing import AsyncIterator
from typing import Awaitable
from typing import Callable

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
from pysignalr.protocol.abstract import Protocol
from pysignalr.protocol.json import JSONProtocol
from pysignalr.transport.abstract import Transport
from pysignalr.transport.websocket import DEFAULT_CONNECTION_TIMEOUT
from pysignalr.transport.websocket import DEFAULT_MAX_SIZE
from pysignalr.transport.websocket import DEFAULT_PING_INTERVAL
from pysignalr.transport.websocket import WebsocketTransport

EmptyCallback = Callable[[], Awaitable[None]]
AnyCallback = Callable[[Any], Awaitable[None]]
MessageCallback = Callable[[Message], Awaitable[None]]
CompletionMessageCallback = Callable[[CompletionMessage], Awaitable[None]]


class ClientStream:
    """Client to server streaming
    https://docs.microsoft.com/en-gb/aspnet/core/signalr/streaming?view=aspnetcore-5.0#client-to-server-streaming
    """

    def __init__(self, transport: Transport, target: str) -> None:
        self.transport: Transport = transport
        self.target: str = target
        self.invocation_id: str = str(uuid.uuid4())

    async def send(self, item: Any) -> None:
        """Send next item to the server"""
        await self.transport.send(StreamItemMessage(self.invocation_id, item))

    async def invoke(self) -> None:
        """Start streaming"""
        await self.transport.send(InvocationClientStreamMessage([self.invocation_id], self.target, []))

    async def complete(self) -> None:
        """Finish streaming"""
        await self.transport.send(CompletionClientStreamMessage(self.invocation_id))


class SignalRClient:
    def __init__(
        self,
        url: str,
        protocol: Protocol | None = None,
        headers: dict[str, str] | None = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        max_size: int | None = DEFAULT_MAX_SIZE,
    ) -> None:
        self._url = url
        self._protocol = protocol or JSONProtocol()
        self._headers = headers or {}

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
            connection_timeout=connection_timeout,
            max_size=max_size,
        )
        self._error_callback: CompletionMessageCallback | None = None

    async def run(self) -> None:
        await self._transport.run()

    def on(self, event: str, callback: AnyCallback) -> None:
        """Register a callback on the specified event"""
        self._message_handlers[event].append(callback)

    def on_open(self, callback: EmptyCallback) -> None:
        """Register a callback on successful connection"""
        self._transport.on_open(callback)

    def on_close(self, callback: EmptyCallback) -> None:
        """Register a callback on connection close"""
        self._transport.on_close(callback)

    def on_error(self, callback: CompletionMessageCallback) -> None:
        """Register a callback on error"""
        self._error_callback = callback

    async def send(
        self,
        method: str,
        arguments: list[dict[str, Any]],
        on_invocation: MessageCallback | None = None,
    ) -> None:
        """Send a message to the server"""
        invocation_id = str(uuid.uuid4())
        message = InvocationMessage(invocation_id, method, arguments, self._headers)
        self._invocation_handlers[invocation_id] = on_invocation
        await self._transport.send(message)

    async def stream(
        self,
        event: str,
        event_params: list[str],
        on_next: MessageCallback | None = None,
        on_complete: MessageCallback | None = None,
        on_error: CompletionMessageCallback | None = None,
    ) -> None:
        """Invoke stream on the specified event"""
        invocation_id = str(uuid.uuid4())
        message = StreamInvocationMessage(invocation_id, event, event_params, self._headers)
        self._stream_handlers[invocation_id] = (on_next, on_complete, on_error)
        await self._transport.send(message)

    @asynccontextmanager
    async def client_stream(self, target: str) -> AsyncIterator[ClientStream]:
        """Start a client stream"""
        stream = ClientStream(self._transport, target)
        await stream.invoke()
        yield stream
        await stream.complete()

    async def _on_message(self, message: Message) -> None:
        # TODO: https://github.com/aspnet/SignalR/blob/master/clients/java/signalr/src/main/java/com/microsoft/signalr/InvocationBindingFailureMessage.java
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
        for callback in self._message_handlers[message.target]:
            if callback:
                await callback(message.arguments)

    async def _on_completion_message(self, message: CompletionMessage) -> None:
        if message.error:
            if self._error_callback is None:
                raise RuntimeError('Error callback is not set')
            await self._error_callback(message)

        callback = self._invocation_handlers.pop(message.invocation_id)
        if callback is not None:
            await callback(message)

    async def _on_stream_item_message(self, message: StreamItemMessage) -> None:
        callback, _, _ = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message.item)

    async def _on_cancel_invocation_message(self, message: CancelInvocationMessage) -> None:
        _, _, callback = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message)  # type: ignore[arg-type]

    async def _on_close_message(self, message: CloseMessage) -> None:
        if message.error:
            raise ServerError(message.error)
