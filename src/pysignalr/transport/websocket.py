from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from http import HTTPStatus
from typing import Awaitable, Callable

from aiohttp import ClientSession, ClientTimeout
from aiohttp import ServerConnectionError
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

import pysignalr.exceptions as exceptions
from pysignalr import NegotiationTimeout, NegotiationNotfound, NegotiationFailure
from pysignalr.messages import CompletionMessage, Message, PingMessage
from pysignalr.protocol.abstract import Protocol
from pysignalr.transport.abstract import ConnectionState, Transport
from pysignalr.utils import get_connection_url, get_negotiate_url, replace_scheme

DEFAULT_MAX_SIZE = 2**20  # 1 MB
DEFAULT_PING_INTERVAL = 10
DEFAULT_CONNECTION_TIMEOUT = 10

DEFAULT_RETRY_WAIT = 1
DEFAULT_RETRY_MULTIPLIER = 1.1
DEFAULT_RETRY_COUNT = 10

_logger = logging.getLogger('pysignalr.transport')


class WebsocketTransport(Transport):
    """
    WebsocketTransport is a class that manages WebSocket connections, handles sending and receiving messages,
    and manages connection states.

    Attributes:
        url (str): The URL of the WebSocket server.
        protocol (Protocol): The protocol used for message encoding/decoding.
        callback (Callable[[Message], Awaitable[None]]): The callback function to handle incoming messages.
        headers (dict[str, str] | None): Optional HTTP headers to include in the WebSocket handshake.
        skip_negotiation (bool): Whether to skip the negotiation step.
        ping_interval (int): The interval for sending ping messages to keep the connection alive.
        connection_timeout (int): The timeout for establishing a connection.
        max_size (int | None): The maximum size for incoming messages.
        access_token_factory (Callable[[], str] | None): A factory function to provide access tokens.
    """

    def __init__(
        self,
        url: str,
        protocol: Protocol,
        callback: Callable[[Message], Awaitable[None]],
        headers: dict[str, str] | None = None,
        skip_negotiation: bool = False,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT,
        retry_sleep: float = DEFAULT_RETRY_SLEEP,
        retry_multiplier: float = DEFAULT_RETRY_MULTIPLIER,
        retry_count: int = DEFAULT_RETRY_COUNT,
        max_size: int | None = DEFAULT_MAX_SIZE,
        access_token_factory: Callable[[], str] | None = None,
    ):
        """
        Initializes the WebSocket transport with the provided parameters.

        Args:
            url (str): The URL of the WebSocket server.
            protocol (Protocol): The protocol used for message encoding/decoding.
            callback (Callable[[Message], Awaitable[None]]): The callback function to handle incoming messages.
            headers (dict[str, str] | None): Optional HTTP headers to include in the WebSocket handshake.
            skip_negotiation (bool): Whether to skip the negotiation step.
            ping_interval (int): The interval for sending ping messages to keep the connection alive.
            connection_timeout (int): The timeout for establishing a connection.
            max_size (int | None): The maximum size for incoming messages.
            access_token_factory (Callable[[], str] | None): A factory function to provide access tokens.
        """
        super().__init__()
        self._url = url
        self._protocol = protocol
        self._callback = callback
        self._headers = headers or {}
        self._skip_negotiation = skip_negotiation
        self._ping_interval = ping_interval
        self._connection_timeout = connection_timeout
        self._max_size = max_size
        self._access_token_factory = access_token_factory
        self._retry_sleep = retry_sleep
        self._retry_multiplier = retry_multiplier
        self._retry_count = retry_count

        self._state = ConnectionState.disconnected
        self._connected = asyncio.Event()
        self._ws: WebSocketClientProtocol | None = None
        self._open_callback: Callable[[], Awaitable[None]] | None = None
        self._close_callback: Callable[[], Awaitable[None]] | None = None

    def on_open(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        Registers a callback function to be called when the connection is opened.

        Args:
            callback (Callable[[], Awaitable[None]]): The callback function.
        """
        self._open_callback = callback

    def on_close(self, callback: Callable[[], Awaitable[None]]) -> None:
        """
        Registers a callback function to be called when the connection is closed.

        Args:
            callback (Callable[[], Awaitable[None]]): The callback function.
        """
        self._close_callback = callback

    def on_error(self, callback: Callable[[CompletionMessage], Awaitable[None]]) -> None:
        """
        Registers a callback function to be called when an error occurs.

        Args:
            callback (Callable[[CompletionMessage], Awaitable[None]]): The callback function.
        """
        self._error_callback = callback

    async def run(self) -> None:
        """
        Runs the WebSocket transport, managing the connection lifecycle.
        """
        while True:
            try:
                await self._loop()
            except (NegotiationNotfound, NegotiationFailure, NegotiationTimeout) as e:
                await self._set_state(ConnectionState.disconnected)
                if self._retry_count <= 0:
                    raise e
                self._retry_count -=  1
                self._retry_sleep *= self._retry_multiplier
                await asyncio.sleep(self_retry_sleep)
            else:
                await self._set_state(ConnectionState.disconnected)

    async def send(self, message: Message) -> None:
        """
        Sends a message over the WebSocket connection.

        Args:
            message (Message): The message to be sent.
        """
        conn = await self._get_connection()
        await conn.send(self._protocol.encode(message))

    async def _loop(self) -> None:
        """
        Manages the connection lifecycle, including reconnection logic.
        """
        await self._set_state(ConnectionState.connecting)

        if not self._skip_negotiation:
            try:
                await self._negotiate()
            except ServerConnectionError as e:
                raise NegotiationTimeout from e

        connection_loop = connect(
            self._url,
            extra_headers=self._headers,
            ping_interval=self._ping_interval,
            open_timeout=self._connection_timeout,
            max_size=self._max_size,
            logger=_logger,
        )

        async for conn in connection_loop:
            try:
                await self._handshake(conn)
                self._ws = conn
                await self._set_state(ConnectionState.connected)
                await asyncio.gather(
                    self._process(conn),
                    self._keepalive(conn),
                )

            except ConnectionClosed as e:
                _logger.warning('Connection closed: %s', e)
                self._ws = None
                await self._set_state(ConnectionState.reconnecting)

    async def _set_state(self, state: ConnectionState) -> None:
        """
        Sets the connection state and triggers appropriate callbacks.

        Args:
            state (ConnectionState): The new connection state.
        """
        if state == self._state:
            return

        _logger.info('State change: %s -> %s', self._state.name, state.name)

        if state == ConnectionState.connecting:
            if self._state != ConnectionState.disconnected:
                raise RuntimeError('Cannot connect while not disconnected')

            self._connected.clear()

        elif state == ConnectionState.connected:
            if self._state not in (ConnectionState.connecting, ConnectionState.reconnecting):
                raise RuntimeError('Cannot connect while not connecting or reconnecting')

            self._connected.set()

            if self._open_callback:
                await self._open_callback()

        elif state in (ConnectionState.reconnecting, ConnectionState.disconnected):
            self._connected.clear()

            if self._close_callback:
                await self._close_callback()

        else:
            raise NotImplementedError

        self._state = state

    async def _get_connection(self) -> WebSocketClientProtocol:
        """
        Gets the active WebSocket connection, ensuring it is open.

        Returns:
            WebSocketClientProtocol: The active WebSocket connection.

        Raises:
            RuntimeError: If the connection is closed or was never run.
        """
        try:
            await asyncio.wait_for(self._connected.wait(), self._connection_timeout)
        except asyncio.TimeoutError as e:
            raise RuntimeError('The socket was never run') from e
        if not self._ws or self._ws.state != State.OPEN:
            raise RuntimeError('Connection is closed')
        return self._ws

    async def _process(self, conn: WebSocketClientProtocol) -> None:
        """
        Processes incoming messages from the WebSocket connection.

        Args:
            conn (WebSocketClientProtocol): The WebSocket connection.
        """
        while True:
            raw_message = await conn.recv()
            await self._on_raw_message(raw_message)

    async def _keepalive(self, conn: WebSocketClientProtocol) -> None:
        """
        Sends periodic ping messages to keep the connection alive.

        Args:
            conn (WebSocketClientProtocol): The WebSocket connection.
        """
        while True:
            await asyncio.sleep(10)
            await conn.send(self._protocol.encode(PingMessage()))

    async def _handshake(self, conn: WebSocketClientProtocol) -> None:
        """
        Performs the WebSocket handshake with the server.

        Args:
            conn (WebSocketClientProtocol): The WebSocket connection.
        """
        _logger.info('Sending handshake to server')
        token = self._access_token_factory() if self._access_token_factory else None
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        our_handshake = self._protocol.handshake_message()
        await conn.send(self._protocol.encode(our_handshake))

        _logger.info('Awaiting handshake from server')
        raw_message = await conn.recv()
        handshake, messages = self._protocol.decode_handshake(raw_message)
        if handshake.error:
            raise ValueError(f'Handshake error: {handshake.error}')
        for message in messages:
            await self._on_message(message)

    async def _negotiate(self) -> None:
        """
        Performs the negotiation step to establish the connection.
        """
        negotiate_url = get_negotiate_url(self._url)
        _logger.info('Performing negotiation, URL: `%s`', negotiate_url)

        session = ClientSession(
            timeout=ClientTimeout(connect=self._connection_timeout),
        )
        async with session:
            async with session.post(negotiate_url, headers=self._headers) as response:
                if response.status == HTTPStatus.OK:
                    data = await response.json()
                elif response.status == HTTPStatus.UNAUTHORIZED:
                    raise exceptions.AuthorizationError
                else:
                    raise exceptions.ConnectionError(response.status)

        connection_id = data.get('connectionId')
        url = data.get('url')
        access_token = data.get('accessToken')

        if connection_id:
            _logger.info('Negotiation completed')
            self._url = get_connection_url(self._url, connection_id)
        elif url and access_token:
            _logger.info('Negotiation completed (Azure)')
            self._url = replace_scheme(url, ws=True)
            self._headers['Authorization'] = f'Bearer {access_token}'
        else:
            raise exceptions.ServerError(str(data))

    async def _on_raw_message(self, raw_message: str | bytes) -> None:
        """
        Handles raw incoming messages, decoding them into protocol-specific messages.

        Args:
            raw_message (str | bytes): The raw incoming message.
        """
        for message in self._protocol.decode(raw_message):
            await self._on_message(message)

    async def _on_message(self, message: Message) -> None:
        """
        Handles decoded messages, passing them to the registered callback.

        Args:
            message (Message): The decoded message.
        """
        await self._callback(message)


class BaseWebsocketTransport(WebsocketTransport):
    """
    BaseWebsocketTransport is a subclass of WebsocketTransport that disables keepalive and handshake 
    for simplified use cases.
    """

    async def _keepalive(self, conn: WebSocketClientProtocol) -> None:
        """
        Disabled keepalive method.

        Args:
            conn (WebSocketClientProtocol): The WebSocket connection.
        """
        return

    async def _handshake(self, conn: WebSocketClientProtocol) -> None:
        """
        Disabled handshake method.

        Args:
            conn (WebSocketClientProtocol): The WebSocket connection.
        """
        return
