from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pysignalr.client import ClientStream
from pysignalr.client import SignalRClient
from pysignalr.exceptions import ServerError
from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionClientStreamMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import MessageType
from pysignalr.messages import PingMessage
from pysignalr.messages import StreamInvocationMessage
from pysignalr.messages import StreamItemMessage


def _make_client() -> tuple[SignalRClient, AsyncMock]:
    client = SignalRClient('http://localhost/hub')
    send_mock = AsyncMock()
    client._transport.send = send_mock  # type: ignore[method-assign]
    return client, send_mock


class _FakeBindingFailure:
    """Mimics a message with invocation_binding_failure type that is not any known subclass."""

    type = MessageType.invocation_binding_failure


class TestOnInvocationMessage:
    async def test_no_handler_no_response(self) -> None:
        """Unregistered event without invocation_id → warning only, nothing sent."""
        client, send_mock = _make_client()
        await client._on_message(InvocationMessage(invocation_id=None, target='Unknown', arguments=[]))
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
            await client._on_message(InvocationMessage(invocation_id=None, target='Greet', arguments=[]))

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


class TestClientStream:
    async def test_send(self) -> None:
        transport_mock = AsyncMock()
        stream = ClientStream(transport_mock, 'Upload')
        await stream.send('item-1')
        sent = transport_mock.send.call_args[0][0]
        assert isinstance(sent, StreamItemMessage)
        assert sent.item == 'item-1'

    async def test_invoke(self) -> None:
        transport_mock = AsyncMock()
        stream = ClientStream(transport_mock, 'Upload')
        await stream.invoke()
        sent = transport_mock.send.call_args[0][0]
        assert isinstance(sent, InvocationClientStreamMessage)
        assert sent.target == 'Upload'

    async def test_complete(self) -> None:
        transport_mock = AsyncMock()
        stream = ClientStream(transport_mock, 'Upload')
        await stream.complete()
        sent = transport_mock.send.call_args[0][0]
        assert isinstance(sent, CompletionClientStreamMessage)


class TestClientStreamContextManager:
    async def test_client_stream_context(self) -> None:
        client, send_mock = _make_client()
        async with client.client_stream('Upload') as stream:
            assert isinstance(stream, ClientStream)
            # invoke() was called on enter
            assert isinstance(send_mock.call_args_list[0][0][0], InvocationClientStreamMessage)
        # complete() was called on exit
        assert isinstance(send_mock.call_args_list[1][0][0], CompletionClientStreamMessage)


class TestOnMessage:
    async def test_ping_message_ignored(self) -> None:
        client, send_mock = _make_client()
        await client._on_message(PingMessage())
        send_mock.assert_not_called()

    async def test_stream_invocation_message_ignored(self) -> None:
        client, send_mock = _make_client()
        await client._on_message(StreamInvocationMessage(invocation_id='inv-1', target='Foo', arguments=[]))
        send_mock.assert_not_called()

    async def test_invocation_binding_failure_raises(self) -> None:
        """A message with invocation_binding_failure type raises ServerError."""
        client, _ = _make_client()
        msg = _FakeBindingFailure()
        with pytest.raises(ServerError):
            await client._on_message(msg)  # type: ignore[arg-type]

    async def test_unknown_message_type_raises(self) -> None:
        """A message that matches no isinstance branch raises NotImplementedError."""
        client, _ = _make_client()
        # ResponseMessage is a Message subclass but not handled by _on_message
        from pysignalr.messages import ResponseMessage

        msg = ResponseMessage(error=None, result=None)
        with pytest.raises(NotImplementedError):
            await client._on_message(msg)


class TestOnInvocationMessageExtra:
    async def test_callback_returns_result_no_response_expected(self) -> None:
        """Callback returns value but invocation_id=None -> warning, nothing sent."""
        client, send_mock = _make_client()
        client.on('Greet', AsyncMock(return_value='hello'))
        await client._on_message(InvocationMessage(invocation_id=None, target='Greet', arguments=[]))
        send_mock.assert_not_called()


class TestSendNonBlocking:
    async def test_send_without_callback_has_no_invocation_id(self) -> None:
        client, send_mock = _make_client()
        await client.send('Fire', [])
        sent = send_mock.call_args[0][0]
        assert isinstance(sent, InvocationMessage)
        assert sent.invocation_id is None

    async def test_send_with_callback_has_invocation_id(self) -> None:
        client, send_mock = _make_client()
        await client.send('Compute', [], on_invocation=AsyncMock())
        sent = send_mock.call_args[0][0]
        assert isinstance(sent, InvocationMessage)
        assert sent.invocation_id is not None


class TestStreamErrorRouting:
    async def test_completion_error_routes_to_stream_on_error(self) -> None:
        client, _ = _make_client()
        on_error = AsyncMock()
        client._stream_handlers['inv-1'] = (None, None, on_error)
        client._invocation_handlers['inv-1'] = None
        msg = CompletionMessage(invocation_id='inv-1', error='stream failed')
        await client._on_message(msg)
        on_error.assert_called_once_with(msg)

    async def test_completion_error_falls_back_to_global_when_stream_on_error_none(self) -> None:
        client, _ = _make_client()
        global_cb = AsyncMock()
        client.on_error(global_cb)
        client._stream_handlers['inv-1'] = (None, None, None)
        client._invocation_handlers['inv-1'] = None
        msg = CompletionMessage(invocation_id='inv-1', error='stream failed')
        await client._on_message(msg)
        global_cb.assert_called_once_with(msg)

    async def test_completion_error_no_stream_no_global_raises(self) -> None:
        client, _ = _make_client()
        client._stream_handlers['inv-1'] = (None, None, None)
        msg = CompletionMessage(invocation_id='inv-1', error='stream failed')
        with pytest.raises(RuntimeError):
            await client._on_message(msg)


class TestSignalRClientMethods:
    async def test_on_close_registers_callback(self) -> None:
        client, _ = _make_client()
        cb = AsyncMock()
        client.on_close(cb)
        assert client._transport._close_callback is cb

    async def test_stream_sends_stream_invocation(self) -> None:
        client, send_mock = _make_client()
        on_next = AsyncMock()
        on_complete = AsyncMock()
        on_error = AsyncMock()
        await client.stream('Counter', ['5'], on_next=on_next, on_complete=on_complete, on_error=on_error)
        sent = send_mock.call_args[0][0]
        assert isinstance(sent, StreamInvocationMessage)
        assert sent.target == 'Counter'
        # Handlers registered
        assert len(client._stream_handlers) == 1
