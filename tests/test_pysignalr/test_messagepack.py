from __future__ import annotations

import json
from typing import Any
from typing import cast

import msgpack  # type: ignore[import-untyped]
import pytest

from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionClientStreamMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import HandshakeRequestMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import PingMessage
from pysignalr.messages import StreamInvocationMessage
from pysignalr.messages import StreamItemMessage
from pysignalr.protocol.messagepack import MessagepackProtocol


def _pack(data: list[Any]) -> bytes:
    """Build a length-prefixed msgpack frame as the server would send."""
    proto = MessagepackProtocol()
    packed = cast('bytes', msgpack.packb(data))
    return proto._to_varint(len(packed)) + packed


class TestVarint:
    def test_single_byte_values(self) -> None:
        proto = MessagepackProtocol()
        for n in (0, 1, 63, 127):
            assert proto._to_varint(n) == bytes([n])

    def test_two_byte_boundary(self) -> None:
        proto = MessagepackProtocol()
        # 128 = 0x80 encodes as 0x80 0x01
        assert proto._to_varint(128) == bytes([0x80, 0x01])

    def test_roundtrip(self) -> None:
        proto = MessagepackProtocol()
        for n in (0, 1, 127, 128, 255, 300, 16383, 16384, 2**21):
            encoded = proto._to_varint(n)
            decoded, offset = proto._from_varint(encoded, 0)
            assert decoded == n
            assert offset == len(encoded)

    def test_from_varint_respects_offset(self) -> None:
        proto = MessagepackProtocol()
        # Pad with a leading zero byte, start reading at offset 1
        data = bytes([0x00]) + proto._to_varint(300)
        value, new_offset = proto._from_varint(data, 1)
        assert value == 300
        assert new_offset == len(data)


class TestMessagepackDecode:
    def test_decode_ping(self) -> None:
        proto = MessagepackProtocol()
        msgs = proto.decode(_pack([6]))
        assert len(msgs) == 1
        assert isinstance(msgs[0], PingMessage)

    def test_decode_invocation(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([1, {}, 'inv-1', 'Target', ['arg1', 'arg2'], []])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, InvocationMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.target == 'Target'
        assert msg.arguments == ['arg1', 'arg2']

    def test_decode_invocation_client_stream(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([1, {}, None, 'Target', [], ['stream-1']])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, InvocationClientStreamMessage)
        assert msg.stream_ids == ['stream-1']
        assert msg.target == 'Target'

    def test_decode_stream_item(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([2, {}, 'inv-1', 42])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, StreamItemMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.item == 42

    def test_decode_completion_with_error(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([3, {}, 'inv-1', 1, 'something went wrong'])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CompletionMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.error == 'something went wrong'
        assert msg.result is None

    def test_decode_completion_void(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([3, {}, 'inv-1', 2])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CompletionMessage)
        assert msg.result is None
        assert msg.error is None

    def test_decode_completion_with_result(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([3, {}, 'inv-1', 3, {'value': 99}])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CompletionMessage)
        assert msg.result == {'value': 99}
        assert msg.error is None

    def test_decode_completion_unknown_result_kind(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([3, {}, 'inv-1', 99])
        with pytest.raises(NotImplementedError):
            proto.decode(raw)

    def test_decode_stream_invocation(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([4, {}, 'inv-1', 'StreamMethod', ['p'], []])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, StreamInvocationMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.target == 'StreamMethod'

    def test_decode_cancel_invocation(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([5, {}, 'inv-1'])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CancelInvocationMessage)
        assert msg.invocation_id == 'inv-1'

    def test_decode_close_no_error(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([7, None, True])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CloseMessage)
        assert msg.error is None

    def test_decode_close_with_error(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([7, 'hub closed', False])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CloseMessage)
        assert msg.error == 'hub closed'

    def test_decode_multiple_concatenated(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([6]) + _pack([6]) + _pack([6])
        msgs = proto.decode(raw)
        assert len(msgs) == 3
        assert all(isinstance(m, PingMessage) for m in msgs)

    def test_decode_large_message(self) -> None:
        """Message body > 127 bytes requires multi-byte varint."""
        proto = MessagepackProtocol()
        big_arg = 'x' * 200
        raw = _pack([1, {}, 'inv-1', 'Target', [big_arg], []])
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        assert isinstance(msgs[0], InvocationMessage)
        assert msgs[0].arguments[0] == big_arg

    def test_decode_invocation_client_stream_preserves_invocation_id(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([1, {}, 'inv-1', 'Target', [], ['stream-1']])
        msgs = proto.decode(raw)
        msg = msgs[0]
        assert isinstance(msg, InvocationClientStreamMessage)
        assert msg.invocation_id == 'inv-1'

    def test_decode_invocation_without_stream_ids(self) -> None:
        proto = MessagepackProtocol()
        raw = _pack([1, {}, 'inv-1', 'Target', [42]])
        msgs = proto.decode(raw)
        msg = msgs[0]
        assert isinstance(msg, InvocationMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.arguments == [42]

    def test_encode_decode_ping_roundtrip(self) -> None:
        proto = MessagepackProtocol()
        encoded = proto.encode(PingMessage())
        msgs = proto.decode(encoded)
        assert len(msgs) == 1
        assert isinstance(msgs[0], PingMessage)

    def test_encode_decode_completion_error_roundtrip(self) -> None:
        proto = MessagepackProtocol()
        msg = CompletionMessage(invocation_id='inv-1', error='fail')
        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)
        assert len(decoded) == 1
        result = decoded[0]
        assert isinstance(result, CompletionMessage)
        assert result.error == 'fail'
        assert result.result is None

    def test_encode_decode_completion_void_roundtrip(self) -> None:
        proto = MessagepackProtocol()
        msg = CompletionMessage(invocation_id='inv-1')
        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)
        assert len(decoded) == 1
        result = decoded[0]
        assert isinstance(result, CompletionMessage)
        assert result.result is None
        assert result.error is None

    def test_encode_decode_completion_result_roundtrip(self) -> None:
        proto = MessagepackProtocol()
        msg = CompletionMessage(invocation_id='inv-1', result={'value': 99})
        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)
        assert len(decoded) == 1
        result = decoded[0]
        assert isinstance(result, CompletionMessage)
        assert result.result == {'value': 99}
        assert result.error is None

    def test_encode_headers_as_empty_map(self) -> None:
        proto = MessagepackProtocol()
        msg = InvocationMessage(invocation_id='inv-1', target='Foo', arguments=[], headers=None)
        encoded = proto.encode(msg)
        # Decode raw to inspect the array
        _, offset = proto._from_varint(encoded, 0)
        raw_array = msgpack.unpackb(encoded[offset:])
        # headers is at index 1
        assert raw_array[1] == {}, f'Expected empty map, got {raw_array[1]}'

    def test_encode_completion_client_stream_has_result_kind(self) -> None:
        """Client-stream end must serialize as a void completion `[3, {}, id, 2]`."""
        proto = MessagepackProtocol()
        encoded = proto.encode(CompletionClientStreamMessage(invocation_id='inv-1'))
        _, offset = proto._from_varint(encoded, 0)
        raw = msgpack.unpackb(encoded[offset:])
        assert raw == [3, {}, 'inv-1', 2]


class TestMessagepackEncodeHandshake:
    def test_encode_handshake_is_json(self) -> None:
        """Per SignalR spec, the handshake is always JSON even for MessagePack connections."""
        proto = MessagepackProtocol()
        encoded = proto.encode(HandshakeRequestMessage(protocol='messagepack', version=1))
        assert encoded.endswith(b'\x1e')
        payload = json.loads(encoded[:-1])
        assert payload == {'protocol': 'messagepack', 'version': 1}


class TestMessagepackDecodeHandshake:
    def test_no_error(self) -> None:
        proto = MessagepackProtocol()
        raw = json.dumps({}).encode() + b'\x1e'
        response, messages = proto.decode_handshake(raw)
        assert response.error is None
        assert list(messages) == []

    def test_with_error(self) -> None:
        proto = MessagepackProtocol()
        raw = json.dumps({'error': 'unsupported protocol'}).encode() + b'\x1e'
        response, _messages = proto.decode_handshake(raw)
        assert response.error == 'unsupported protocol'

    def test_with_trailing_messages(self) -> None:
        proto = MessagepackProtocol()
        raw = json.dumps({}).encode() + b'\x1e' + _pack([6])
        response, messages = proto.decode_handshake(raw)
        assert response.error is None
        msg_list = list(messages)
        assert len(msg_list) == 1
        assert isinstance(msg_list[0], PingMessage)

    def test_str_input(self) -> None:
        proto = MessagepackProtocol()
        raw = json.dumps({'error': None}).encode() + b'\x1e'
        response, _ = proto.decode_handshake(raw.decode('latin-1'))
        assert response.error is None
