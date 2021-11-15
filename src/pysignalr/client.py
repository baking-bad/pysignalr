import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any
from typing import AsyncIterator
from typing import Awaitable
from typing import Callable
from typing import DefaultDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

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
from pysignalr.transport.websocket import DEFAULT_PING_INTERVAL
from pysignalr.transport.websocket import WebsocketTransport


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
        self.transport.send(StreamItemMessage(self.invocation_id, item))

    async def invoke(self) -> None:
        """Start streaming"""
        self.transport.send(InvocationClientStreamMessage([self.invocation_id], self.target, []))

    async def complete(self) -> None:
        """Finish streaming"""
        self.transport.send(CompletionClientStreamMessage(self.invocation_id))


class SignalRClient:
    def __init__(
        self,
        url: str,
        protocol: Optional[Protocol] = None,
        headers: Optional[Dict[str, str]] = None,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
    ) -> None:
        self._url = url
        self._protocol = protocol or JSONProtocol()
        self._headers = headers or {}

        self._message_handlers: DefaultDict[str, List[Optional[Callable]]] = defaultdict(list)
        self._stream_handlers: Dict[str, Tuple[Optional[Callable], Optional[Callable], Optional[Callable]]] = {}
        self._invocation_handlers: Dict[str, Optional[Callable]] = {}

        self._transport = WebsocketTransport(
            url=self._url,
            protocol=self._protocol,
            callback=self._on_message,
            headers=self._headers,
            ping_interval=ping_interval,
            connection_timeout=connection_timeout,
        )
        self._error_callback: Optional[Callable[[CompletionMessage], Awaitable[None]]] = None

    async def run(self) -> None:
        await self._transport.run()

    def on(self, event: str, callback: Callable[..., Awaitable[None]]) -> None:
        """Register a callback on the specified event"""
        self._message_handlers[event].append(callback)

    def on_open(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback on successful connection"""
        self._transport.on_open(callback)

    def on_close(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback on connection close"""
        self._transport.on_close(callback)

    def on_error(self, callback: Callable[[CompletionMessage], Awaitable[None]]) -> None:
        """Register a callback on error"""
        self._error_callback = callback

    async def send(
        self,
        method: str,
        arguments: List[Dict[str, Any]],
        on_invocation: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> None:
        """Send a message to the server"""
        invocation_id = str(uuid.uuid4())
        message = InvocationMessage(invocation_id, method, arguments, self._headers)
        self._invocation_handlers[invocation_id] = on_invocation
        await self._transport.send(message)

    async def stream(
        self,
        event: str,
        event_params: List[str],
        on_next: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
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
        if message.type == MessageType.invocation_binding_failure:  # type: ignore
            raise ServerError(message)

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
            if not self._error_callback:
                raise Exception
            await self._error_callback(message)

        callback = self._invocation_handlers.pop(message.invocation_id)
        if callback:
            await callback(message)

    async def _on_stream_item_message(self, message: StreamItemMessage) -> None:
        callback, _, _ = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message.item)

    async def _on_cancel_invocation_message(self, message: CancelInvocationMessage) -> None:
        _, _, callback = self._stream_handlers[message.invocation_id]
        if callback:
            await callback(message)

    async def _on_close_message(self, message: CloseMessage) -> None:
        if message.error:
            raise ServerError(message.error)
