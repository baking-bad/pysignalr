from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pysignalr.client import SignalRClient
from pysignalr.exceptions import ServerError
from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import StreamItemMessage


def _make_client() -> tuple[SignalRClient, AsyncMock]:
    client = SignalRClient('http://localhost/hub')
    send_mock = AsyncMock()
    client._transport.send = send_mock  # type: ignore[method-assign]
    return client, send_mock


class TestOnInvocationMessage:
    async def test_no_handler_no_response(self) -> None:
        """Unregistered event without invocation_id → warning only, nothing sent."""
        client, send_mock = _make_client()
        await client._on_message(InvocationMessage(invocation_id=None, target='Unknown', arguments=[]))  # type: ignore[arg-type]
        send_mock.assert_not_called()

    async def test_no_handler_expects_response(self) -> None:
        """Unregistered event with invocation_id → sends error CompletionMessage."""
        client, send_mock = _make_client()
        await client._on_message(InvocationMessage(invocation_id='abc', target='Unknown', arguments=[]))
        send_mock.assert_called_once()
        sent: CompletionMessage = send_mock.call_args[0][0]
        assert isinstance(sent, CompletionMessage)
        assert sent.invocation_id == 'abc'
        assert sent.error is not None

    async def test_multiple_handlers_expects_response(self) -> None:
        """Two handlers registered for an event that expects a result → sends error."""
        client, send_mock = _make_client()
        client.on('Greet', AsyncMock(return_value='a'))
        client.on('Greet', AsyncMock(return_value='b'))
        await client._on_message(InvocationMessage(invocation_id='abc', target='Greet', arguments=[]))
        send_mock.assert_called_once()
        sent: CompletionMessage = send_mock.call_args[0][0]
        assert isinstance(sent, CompletionMessage)
        assert sent.error is not None

    async def test_callback_raises_expects_response(self) -> None:
        """Callback raises with invocation_id → sends error CompletionMessage."""
        client, send_mock = _make_client()
        client.on('Greet', AsyncMock(side_effect=ValueError('boom')))
        await client._on_message(InvocationMessage(invocation_id='abc', target='Greet', arguments=[]))
        send_mock.assert_called_once()
        sent: CompletionMessage = send_mock.call_args[0][0]
        assert isinstance(sent, CompletionMessage)
        assert 'boom' in (sent.error or '')

    async def test_callback_raises_no_response(self) -> None:
        """Callback raises without invocation_id → exception propagates."""
        client, _ = _make_client()
        client.on('Greet', AsyncMock(side_effect=ValueError('boom')))
        with pytest.raises(ValueError, match='boom'):
            await client._on_message(InvocationMessage(invocation_id=None, target='Greet', arguments=[]))  # type: ignore[arg-type]

    async def test_callback_returns_result(self) -> None:
        """Callback returns a value with invocation_id → sends CompletionMessage with result."""
        client, send_mock = _make_client()
        client.on('Compute', AsyncMock(return_value=42))
        await client._on_message(InvocationMessage(invocation_id='abc', target='Compute', arguments=[]))
        send_mock.assert_called_once()
        sent: CompletionMessage = send_mock.call_args[0][0]
        assert isinstance(sent, CompletionMessage)
        assert sent.result == 42
        assert sent.error is None

    async def test_callback_returns_none_expects_response(self) -> None:
        """Callback returns None with invocation_id → sends error (no result provided)."""
        client, send_mock = _make_client()
        client.on('Compute', AsyncMock(return_value=None))
        await client._on_message(InvocationMessage(invocation_id='abc', target='Compute', arguments=[]))
        send_mock.assert_called_once()
        sent: CompletionMessage = send_mock.call_args[0][0]
        assert isinstance(sent, CompletionMessage)
        assert sent.error is not None


class TestOnCompletionMessage:
    async def test_error_no_callback_raises(self) -> None:
        """Completion with error and no error_callback → RuntimeError."""
        client, _ = _make_client()
        with pytest.raises(RuntimeError):
            await client._on_message(CompletionMessage(invocation_id='abc', error='oops'))

    async def test_error_with_callback(self) -> None:
        """Completion with error and registered error_callback → callback called."""
        client, _ = _make_client()
        error_cb = AsyncMock()
        client.on_error(error_cb)
        msg = CompletionMessage(invocation_id='abc', error='oops')
        await client._on_message(msg)
        error_cb.assert_called_once_with(msg)

    async def test_untracked_invocation_id(self) -> None:
        """Completion for an ID not in invocation_handlers → no KeyError."""
        client, _ = _make_client()
        await client._on_message(CompletionMessage(invocation_id='unknown', result='ok'))

    async def test_stream_handlers_cleaned_up(self) -> None:
        """stream_handlers entry removed when completion arrives."""
        client, _ = _make_client()
        client._stream_handlers['inv-1'] = (AsyncMock(), AsyncMock(), None)
        client._invocation_handlers['inv-1'] = None
        await client._on_message(CompletionMessage(invocation_id='inv-1', result='done'))
        assert 'inv-1' not in client._stream_handlers

    async def test_invocation_callback_called(self) -> None:
        """Registered invocation callback is called on completion."""
        client, _ = _make_client()
        cb = AsyncMock()
        client._invocation_handlers['inv-1'] = cb
        msg = CompletionMessage(invocation_id='inv-1', result='done')
        await client._on_message(msg)
        cb.assert_called_once_with(msg)


class TestOnStreamItemMessage:
    async def test_routes_to_on_next(self) -> None:
        client, _ = _make_client()
        on_next = AsyncMock()
        client._stream_handlers['inv-1'] = (on_next, None, None)
        await client._on_message(StreamItemMessage(invocation_id='inv-1', item='chunk'))
        on_next.assert_called_once_with('chunk')

    async def test_null_on_next_no_error(self) -> None:
        client, _ = _make_client()
        client._stream_handlers['inv-1'] = (None, None, None)
        await client._on_message(StreamItemMessage(invocation_id='inv-1', item='chunk'))


class TestOnCancelInvocationMessage:
    async def test_routes_to_on_error(self) -> None:
        client, _ = _make_client()
        on_error = AsyncMock()
        client._stream_handlers['inv-1'] = (None, None, on_error)
        msg = CancelInvocationMessage(invocation_id='inv-1')
        await client._on_message(msg)
        on_error.assert_called_once_with(msg)


class TestOnCloseMessage:
    async def test_with_error_raises_server_error(self) -> None:
        client, _ = _make_client()
        with pytest.raises(ServerError, match='hub closed'):
            await client._on_message(CloseMessage(error='hub closed'))

    async def test_without_error_no_raise(self) -> None:
        client, _ = _make_client()
        await client._on_message(CloseMessage())
