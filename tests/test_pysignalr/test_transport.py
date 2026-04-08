from __future__ import annotations

import ssl
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pysignalr.client import SignalRClient


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
