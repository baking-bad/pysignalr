from __future__ import annotations

import pytest

from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import HandshakeResponseMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import MessageType
from pysignalr.messages import PingMessage
from pysignalr.messages import StreamInvocationMessage
from pysignalr.messages import StreamItemMessage
from pysignalr.protocol.json import JSONProtocol
from pysignalr.protocol.json import MessageEncoder

SEP = chr(0x1E)


class TestMessageEncoder:
    def test_message_type_returns_value(self) -> None:
        encoder = MessageEncoder()
        assert encoder.default(MessageType.ping) == 6


class TestJSONProtocolDecode:
    def test_decode_ping(self) -> None:
        proto = JSONProtocol()
        msgs = proto.decode(f'{{"type":6}}{SEP}')
        assert len(msgs) == 1
        assert isinstance(msgs[0], PingMessage)

    def test_decode_invocation(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":1,"invocationId":"inv-1","target":"Greet","arguments":["hi"]}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, InvocationMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.target == 'Greet'
        assert msg.arguments == ['hi']

    def test_decode_stream_item(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":2,"invocationId":"inv-1","item":42}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, StreamItemMessage)
        assert msg.item == 42

    def test_decode_completion(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":3,"invocationId":"inv-1","result":"ok"}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CompletionMessage)
        assert msg.result == 'ok'

    def test_decode_stream_invocation(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":4,"invocationId":"inv-1","target":"Counter","arguments":["5"]}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        assert isinstance(msgs[0], StreamInvocationMessage)

    def test_decode_cancel_invocation(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":5,"invocationId":"inv-1"}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        assert isinstance(msgs[0], CancelInvocationMessage)

    def test_decode_close_no_error(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":7}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CloseMessage)
        assert msg.error is None

    def test_decode_close_with_error(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":7,"error":"hub closed","allowReconnect":true}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, CloseMessage)
        assert msg.error == 'hub closed'
        assert msg.allow_reconnect is True

    def test_decode_invocation_with_stream_ids_preserves_invocation_id(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":1,"invocationId":"inv-1","target":"Upload","arguments":[],"streamIds":["s1"]}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        msg = msgs[0]
        assert isinstance(msg, InvocationClientStreamMessage)
        assert msg.invocation_id == 'inv-1'
        assert msg.stream_ids == ['s1']

    def test_decode_bytes_input(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":6}}{SEP}'.encode()
        msgs = proto.decode(raw)
        assert len(msgs) == 1
        assert isinstance(msgs[0], PingMessage)

    def test_decode_multiple_messages(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"type":6}}{SEP}{{"type":6}}{SEP}{{"type":6}}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 3
        assert all(isinstance(m, PingMessage) for m in msgs)

    def test_decode_skips_empty_segments(self) -> None:
        proto = JSONProtocol()
        raw = f'{SEP}{{"type":6}}{SEP}{SEP}'
        msgs = proto.decode(raw)
        assert len(msgs) == 1


class TestJSONProtocolEncode:
    def test_encode_ping(self) -> None:
        proto = JSONProtocol()
        encoded = proto.encode(PingMessage())
        assert encoded.endswith(SEP)
        assert '"type"' in encoded


class TestJSONProtocolDecodeHandshake:
    def test_no_error(self) -> None:
        proto = JSONProtocol()
        raw = f'{{}}{SEP}'
        response, messages = proto.decode_handshake(raw)
        assert isinstance(response, HandshakeResponseMessage)
        assert response.error is None
        assert list(messages) == []

    def test_with_error(self) -> None:
        proto = JSONProtocol()
        raw = f'{{"error":"bad version"}}{SEP}'
        response, _ = proto.decode_handshake(raw)
        assert response.error == 'bad version'

    def test_with_trailing_messages(self) -> None:
        proto = JSONProtocol()
        raw = f'{{}}{SEP}{{"type":6}}{SEP}'
        response, messages = proto.decode_handshake(raw)
        assert response.error is None
        msg_list = list(messages)
        assert len(msg_list) == 1
        assert isinstance(msg_list[0], PingMessage)

    def test_bytes_input(self) -> None:
        proto = JSONProtocol()
        raw = f'{{}}{SEP}'.encode()
        response, _ = proto.decode_handshake(raw)
        assert response.error is None


class TestJSONProtocolParseMessage:
    def test_unknown_message_type_raises(self) -> None:
        """MessageType._ (placeholder) is valid but unhandled → NotImplementedError."""
        with pytest.raises(NotImplementedError):
            JSONProtocol.parse_message({'type': MessageType._.value})
