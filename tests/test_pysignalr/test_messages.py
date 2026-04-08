from __future__ import annotations

from pysignalr.messages import CompletionClientStreamMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import JSONMessage
from pysignalr.messages import MessageType


class TestMessageDump:
    def test_dump_with_stream_ids(self) -> None:
        msg = InvocationClientStreamMessage(stream_ids=['s1'], target='Foo', arguments=[])
        data = msg.dump()
        assert data['streamIds'] == ['s1']
        assert 'stream_ids' not in data

    def test_completion_dump_with_error(self) -> None:
        msg = CompletionMessage(invocation_id='inv-1', error='fail')
        data = msg.dump()
        assert data['error'] == 'fail'

    def test_completion_dump_with_headers(self) -> None:
        msg = CompletionMessage(invocation_id='inv-1', headers={'x': '1'})
        data = msg.dump()
        assert data['headers'] == {'x': '1'}


    def test_dump_is_idempotent(self) -> None:
        msg = InvocationMessage(invocation_id='inv-1', target='Foo', arguments=[1, 2])
        first = msg.dump()
        second = msg.dump()
        assert first == second
        assert msg.invocation_id == 'inv-1'

    def test_completion_dump_is_idempotent(self) -> None:
        msg = CompletionMessage(invocation_id='inv-1', result=42, error='fail', headers={'x': '1'})
        first = msg.dump()
        second = msg.dump()
        assert first == second

    def test_dump_with_invocation_id(self) -> None:
        msg = InvocationClientStreamMessage(stream_ids=['s1'], target='Foo', arguments=[], invocation_id='inv-1')
        data = msg.dump()
        assert data['invocationId'] == 'inv-1'
        assert data['streamIds'] == ['s1']

    def test_completion_client_stream_type(self) -> None:
        msg = CompletionClientStreamMessage(invocation_id='inv-1')
        assert msg.type == MessageType.completion  # type: ignore[attr-defined]


class TestJSONMessage:
    def test_init_and_dump(self) -> None:
        msg = JSONMessage({'foo': 1})
        assert msg.dump() == {'foo': 1}
