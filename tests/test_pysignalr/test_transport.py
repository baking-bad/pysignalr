from __future__ import annotations

import asyncio
import ssl
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from aiohttp import ServerConnectionError
from websockets.exceptions import ConnectionClosed
from websockets.frames import Close
from websockets.frames import CloseCode

from pysignalr.client import SignalRClient
from pysignalr.exceptions import ConnectionError as SignalRConnectionError
from pysignalr.exceptions import NegotiationFailure
from pysignalr.exceptions import ServerError
from pysignalr.messages import HandshakeResponseMessage
from pysignalr.messages import PingMessage
from pysignalr.transport.abstract import ConnectionState
from pysignalr.transport.websocket import BaseWebsocketTransport
from pysignalr.transport.websocket import WebsocketTransport


def _response_mock(status: int = 200, json_data: dict[str, Any] | None = None) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {'connectionId': 'test-id'})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def _session_mock(response: MagicMock) -> MagicMock:
    session = MagicMock()
    session.post = MagicMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


class TestNegotiateSSL:
    async def test_no_ssl_no_connector(self) -> None:
        """Without ssl=, ClientSession is created without a TCPConnector."""
        client = SignalRClient('http://localhost/hub')
        response = _response_mock()
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector') as mock_connector, \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            await client._transport._negotiate()
            mock_connector.assert_not_called()

    async def test_ssl_context_passed_to_connector(self) -> None:
        """Custom SSLContext is forwarded to TCPConnector during negotiation."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        client = SignalRClient('http://localhost/hub', ssl=ctx)
        response = _response_mock()
        session = _session_mock(response)
        connector_instance = MagicMock()

        with patch('pysignalr.transport.websocket.TCPConnector', return_value=connector_instance) as mock_connector, \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session) as mock_session:
            await client._transport._negotiate()
            mock_connector.assert_called_once_with(ssl=ctx)
            mock_session.assert_called_once()
            _, kwargs = mock_session.call_args
            assert kwargs['connector'] is connector_instance

    async def test_negotiate_sets_connection_url(self) -> None:
        """Negotiation appends connectionId to the transport URL."""
        client = SignalRClient('http://localhost/hub')
        response = _response_mock(json_data={'connectionId': 'abc-123'})
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector'), \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            await client._transport._negotiate()

        assert 'abc-123' in client._transport._url

    async def test_negotiate_unauthorized_raises(self) -> None:
        """HTTP 401 from server raises AuthorizationError."""
        from pysignalr.exceptions import AuthorizationError

        client = SignalRClient('http://localhost/hub')
        response = _response_mock(status=401)
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector'), \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            with pytest.raises(AuthorizationError):
                await client._transport._negotiate()

    async def test_negotiate_azure_redirect(self) -> None:
        """Azure SignalR redirect (url + accessToken) updates URL and Authorization header."""
        client = SignalRClient('http://localhost/hub')
        response = _response_mock(json_data={
            'url': 'https://azure.signalr.net/hub',
            'accessToken': 'azure-token',
        })
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector'), \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            await client._transport._negotiate()

        assert client._transport._headers.get('Authorization') == 'Bearer azure-token'
        assert client._transport._url.startswith('wss://')

    async def test_negotiate_other_http_error(self) -> None:
        """HTTP 500 raises ConnectionError."""
        client = SignalRClient('http://localhost/hub')
        response = _response_mock(status=500)
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector'), \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            with pytest.raises(SignalRConnectionError):
                await client._transport._negotiate()

    async def test_negotiate_no_connection_id_no_azure(self) -> None:
        """JSON response with neither connectionId nor Azure fields raises ServerError."""
        client = SignalRClient('http://localhost/hub')
        response = _response_mock(json_data={'someOtherField': True})
        session = _session_mock(response)

        with patch('pysignalr.transport.websocket.TCPConnector'), \
             patch('pysignalr.transport.websocket.ClientSession', return_value=session):
            with pytest.raises(ServerError):
                await client._transport._negotiate()

    async def test_negotiate_server_connection_error_raises_negotiation_failure(self) -> None:
        """ServerConnectionError during negotiate in _loop raises NegotiationFailure."""
        transport = _make_transport()

        async def raise_server_connection_error() -> None:
            raise ServerConnectionError()

        with patch.object(transport, '_negotiate', side_effect=raise_server_connection_error):
            with pytest.raises(NegotiationFailure):
                await transport._loop()


def _make_transport(**kwargs: Any) -> WebsocketTransport:
    defaults: dict[str, Any] = {
        'url': 'http://localhost/hub',
        'protocol': MagicMock(),
        'callback': AsyncMock(),
    }
    defaults.update(kwargs)
    return WebsocketTransport(**defaults)


class TestOnCloseCallback:
    def test_on_close_registers_callback(self) -> None:
        transport = _make_transport()
        cb = AsyncMock()
        transport.on_close(cb)
        assert transport._close_callback is cb


class TestOnErrorCallback:
    def test_on_error_registers_callback(self) -> None:
        transport = _make_transport()
        cb = AsyncMock()
        transport.on_error(cb)
        assert transport._error_callback is cb


class TestSetState:
    async def test_connecting_from_non_disconnected_raises(self) -> None:
        transport = _make_transport()
        # Get to connected state
        await transport._set_state(ConnectionState.connecting)
        await transport._set_state(ConnectionState.connected)
        # Now trying to connect from connected should raise
        with pytest.raises(RuntimeError, match='Cannot connect while not disconnected'):
            await transport._set_state(ConnectionState.connecting)

    async def test_connected_from_disconnected_raises(self) -> None:
        transport = _make_transport()
        # State starts as disconnected; going directly to connected is invalid
        with pytest.raises(RuntimeError, match='Cannot connect while not connecting'):
            await transport._set_state(ConnectionState.connected)

    async def test_reconnecting_calls_close_callback(self) -> None:
        transport = _make_transport()
        cb = AsyncMock()
        transport.on_close(cb)
        # Get to connecting → connected first
        await transport._set_state(ConnectionState.connecting)
        await transport._set_state(ConnectionState.connected)
        await transport._set_state(ConnectionState.reconnecting)
        cb.assert_called_once()

    async def test_disconnected_calls_close_callback(self) -> None:
        transport = _make_transport()
        cb = AsyncMock()
        transport.on_close(cb)
        await transport._set_state(ConnectionState.connecting)
        await transport._set_state(ConnectionState.connected)
        await transport._set_state(ConnectionState.disconnected)
        cb.assert_called_once()

    async def test_same_state_is_noop(self) -> None:
        transport = _make_transport()
        await transport._set_state(ConnectionState.disconnected)
        # No error, no state change


class TestGetConnection:
    async def test_timeout_raises_runtime_error(self) -> None:
        transport = _make_transport(connection_timeout=0.01)
        with pytest.raises(RuntimeError, match='never run'):
            await transport._get_connection()

    async def test_closed_ws_raises_runtime_error(self) -> None:
        transport = _make_transport()
        transport._connected.set()
        transport._ws = None
        with pytest.raises(RuntimeError, match='closed'):
            await transport._get_connection()


class TestHandshake:
    async def test_handshake_error_raises(self) -> None:
        transport = _make_transport()
        transport._protocol.decode_handshake.return_value = (  # type: ignore[attr-defined]
            HandshakeResponseMessage(error='bad protocol'),
            [],
        )
        transport._protocol.handshake_message.return_value = MagicMock()  # type: ignore[attr-defined]
        transport._protocol.encode.return_value = b'handshake'  # type: ignore[attr-defined]

        conn = AsyncMock()
        conn.recv = AsyncMock(return_value=b'response')

        with pytest.raises(ValueError, match='Handshake error'):
            await transport._handshake(conn)

    async def test_handshake_trailing_messages(self) -> None:
        transport = _make_transport()
        trailing_msg = PingMessage()
        transport._protocol.decode_handshake.return_value = (  # type: ignore[attr-defined]
            HandshakeResponseMessage(error=None),
            [trailing_msg],
        )
        transport._protocol.handshake_message.return_value = MagicMock()  # type: ignore[attr-defined]
        transport._protocol.encode.return_value = b'handshake'  # type: ignore[attr-defined]

        conn = AsyncMock()
        conn.recv = AsyncMock(return_value=b'response')

        await transport._handshake(conn)
        transport._callback.assert_called_once_with(trailing_msg)  # type: ignore[attr-defined]


class TestLoop:
    async def test_connection_closed_triggers_reconnect(self) -> None:
        transport = _make_transport(skip_negotiation=True)
        transport._ssl = None

        states_seen: list[ConnectionState] = []
        original_set_state = transport._set_state

        async def tracking_set_state(state: ConnectionState) -> None:
            states_seen.append(state)
            await original_set_state(state)

        mock_conn = AsyncMock()

        class FakeConnectIter:
            def __init__(self) -> None:
                self._count = 0

            def __aiter__(self) -> FakeConnectIter:
                return self

            async def __anext__(self) -> Any:
                self._count += 1
                if self._count > 1:
                    raise StopAsyncIteration
                return mock_conn

        async def fake_gather(*coros: Any, **kwargs: Any) -> None:
            raise ConnectionClosed(Close(CloseCode.NORMAL_CLOSURE, ''), None)

        with patch('pysignalr.transport.websocket.connect', return_value=FakeConnectIter()), \
             patch.object(transport, '_handshake', new_callable=AsyncMock), \
             patch.object(transport, '_set_state', side_effect=tracking_set_state), \
             patch('asyncio.gather', side_effect=fake_gather):
            await transport._loop()

        assert ConnectionState.reconnecting in states_seen

    async def test_loop_with_ssl(self) -> None:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        transport = _make_transport(skip_negotiation=True, ssl=ctx)

        class FakeConnectIter:
            def __aiter__(self) -> FakeConnectIter:
                return self

            async def __anext__(self) -> Any:
                raise StopAsyncIteration

        with patch('pysignalr.transport.websocket.connect', return_value=FakeConnectIter()) as mock_connect:
            await transport._loop()
            _, kwargs = mock_connect.call_args
            assert kwargs['ssl'] is ctx


class TestKeepalive:
    async def test_keepalive_sends_ping(self) -> None:
        transport = _make_transport(signalr_ping_interval=0)
        transport._protocol.encode.return_value = b'ping'  # type: ignore[attr-defined]

        conn = AsyncMock()
        call_count = 0

        async def fake_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.CancelledError

        with patch('pysignalr.transport.websocket.asyncio.sleep', side_effect=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await transport._keepalive(conn)

        conn.send.assert_called_with(b'ping')


class TestBaseWebsocketTransport:
    async def test_keepalive_noop(self) -> None:
        transport = BaseWebsocketTransport(
            url='http://localhost/hub',
            protocol=MagicMock(),
            callback=AsyncMock(),
        )
        await transport._keepalive(AsyncMock())

    async def test_handshake_noop(self) -> None:
        transport = BaseWebsocketTransport(
            url='http://localhost/hub',
            protocol=MagicMock(),
            callback=AsyncMock(),
        )
        await transport._handshake(AsyncMock())
