from __future__ import annotations

from pysignalr.messages import CompletionMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import JSONMessage


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


class TestJSONMessage:
    def test_init_and_dump(self) -> None:
        msg = JSONMessage({'foo': 1})
        assert msg.dump() == {'foo': 1}
