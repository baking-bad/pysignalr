from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import msgpack  # type: ignore[import-untyped]
import orjson

from pysignalr.messages import CancelInvocationMessage
from pysignalr.messages import CloseMessage
from pysignalr.messages import CompletionMessage
from pysignalr.messages import HandshakeRequestMessage
from pysignalr.messages import HandshakeResponseMessage
from pysignalr.messages import InvocationClientStreamMessage
from pysignalr.messages import InvocationMessage
from pysignalr.messages import Message
from pysignalr.messages import MessageType
from pysignalr.messages import PingMessage
from pysignalr.messages import StreamInvocationMessage
from pysignalr.messages import StreamItemMessage
from pysignalr.protocol.abstract import Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

_attribute_priority = (
    # NOTE: Python limitation, left as is
    'type_',
    'type',
    'headers',
    'invocation_id',
    'target',
    'arguments',
    'item',
    'result_kind',
    'result',
    'stream_ids',
)


class MessagepackProtocol(Protocol):
    """
    Class for handling MessagePack protocols.

    This class provides methods for encoding and decoding messages using the MessagePack protocol.
    """

    def __init__(self) -> None:
        """
        Initializes a MessagepackProtocol object.
        """
        super().__init__(
            protocol='messagepack',
            version=1,
            record_separator=chr(0x1E),
        )

    def decode(self, raw_message: str | bytes) -> list[Message]:
        """
        Decodes a raw message into a list of Message objects.

        Args:
            raw_message (str | bytes): The raw message to be decoded.

        Returns:
            list[Message]: A list of Message objects.
        """
        messages: list[Message] = []
        data: bytes = raw_message.encode() if isinstance(raw_message, str) else raw_message
        offset = 0
        while offset < len(data):
            length, offset = self._from_varint(data, offset)
            values = msgpack.unpackb(data[offset : offset + length])
            offset += length
            message = self.parse_message(values)
            messages.append(message)
        return messages

    def encode(self, message: Message | HandshakeRequestMessage) -> bytes:
        """
        Encodes a message into a raw representation.

        Args:
            message (Message | HandshakeRequestMessage): The message to be encoded.

        Returns:
            bytes: The raw representation of the message.
        """
        # NOTE: Per SignalR spec, the handshake is always JSON, even for MessagePack connections.
        if isinstance(message, HandshakeRequestMessage):
            return orjson.dumps(message.dump()) + b'\x1e'

        if isinstance(message, CompletionMessage):
            raw_message = self._encode_completion(message)
        else:
            raw_message = []
            for attr in _attribute_priority:
                if hasattr(message, attr):
                    if attr == 'type_':
                        raw_message.append(getattr(message, attr).value)
                    elif attr == 'headers':
                        raw_message.append(getattr(message, attr) or {})
                    elif attr == 'stream_ids':
                        raw_message.append(getattr(message, attr) or [])
                    else:
                        raw_message.append(getattr(message, attr))

        encoded_message = cast('bytes', msgpack.packb(raw_message))
        varint_length = self._to_varint(len(encoded_message))
        return varint_length + encoded_message

    def _encode_completion(self, message: CompletionMessage) -> list[Any]:
        headers = message.headers or {}
        if message.error is not None:
            return [MessageType.completion.value, headers, message.invocation_id, 1, message.error]
        elif message.result is not None:
            return [MessageType.completion.value, headers, message.invocation_id, 3, message.result]
        else:
            return [MessageType.completion.value, headers, message.invocation_id, 2]

    def decode_handshake(self, raw_message: str | bytes) -> tuple[HandshakeResponseMessage, Iterable[Message]]:
        """
        Decodes a handshake message.

        Args:
            raw_message (str | bytes): The raw handshake message to be decoded.

        Returns:
            tuple[HandshakeResponseMessage, Iterable[Message]]: A tuple containing a HandshakeResponseMessage and a sequence of Message objects.
        """
        if isinstance(raw_message, str):
            raw_message = raw_message.encode()

        has_various_messages = 0x1E in raw_message
        handshake_data = raw_message[0 : raw_message.index(0x1E)] if has_various_messages else raw_message
        messages = self.decode(raw_message[raw_message.index(0x1E) + 1 :]) if has_various_messages else []
        data = orjson.loads(handshake_data)
        return HandshakeResponseMessage(data.get('error', None)), messages

    @staticmethod
    def parse_message(seq_message: Sequence[Any]) -> Message:
        """
        Parses a sequence into a Message object.

        Args:
            seq_message (Sequence[Any]): The sequence to be parsed.

        Returns:
            Message: The resulting Message object.
        """
        # {} {'error'}
        # [1, Headers, InvocationId, Target, [Arguments], [StreamIds]]
        # [2, Headers, InvocationId, Item]
        # [3, Headers, InvocationId, ResultKind, Result]
        # [4, Headers, InvocationId, Target, [Arguments], [StreamIds]]
        # [5, Headers, InvocationId]
        # [6]
        # [7, Error, AllowReconnect?]

        msg = seq_message
        message_type = MessageType(msg[0])

        if message_type is MessageType.invocation:
            if len(msg) > 5 and len(msg[5]) > 0:
                return InvocationClientStreamMessage(headers=msg[1], stream_ids=msg[5], target=msg[3], arguments=msg[4], invocation_id=msg[2])
            else:
                return InvocationMessage(headers=msg[1], invocation_id=msg[2], target=msg[3], arguments=msg[4])
        elif message_type is MessageType.stream_item:
            return StreamItemMessage(headers=msg[1], invocation_id=msg[2], item=msg[3])
        elif message_type is MessageType.completion:
            if msg[3] == 1:
                return CompletionMessage(headers=msg[1], invocation_id=msg[2], result=None, error=msg[4])
            elif msg[3] == 2:
                return CompletionMessage(headers=msg[1], invocation_id=msg[2], result=None, error=None)
            elif msg[3] == 3:
                return CompletionMessage(headers=msg[1], invocation_id=msg[2], result=msg[4], error=None)
            else:
                raise NotImplementedError
        elif message_type is MessageType.stream_invocation:
            stream_ids = msg[5] if len(msg) > 5 else None
            return StreamInvocationMessage(headers=msg[1], invocation_id=msg[2], target=msg[3], arguments=msg[4], stream_ids=stream_ids or None)
        elif message_type is MessageType.cancel_invocation:
            return CancelInvocationMessage(headers=msg[1], invocation_id=msg[2])
        elif message_type is MessageType.ping:
            return PingMessage()
        elif message_type is MessageType.close:
            return CloseMessage(*msg[1:])
        else:
            raise NotImplementedError

    def _from_varint(self, data: bytes, offset: int) -> tuple[int, int]:
        """
        Decodes a variable-length integer from data starting at offset.

        Args:
            data (bytes): The data containing the varint.
            offset (int): The starting offset.

        Returns:
            tuple[int, int]: The decoded integer and the new offset after the varint.
        """
        length = 0
        shift = 0
        while True:
            byte = data[offset]
            offset += 1
            length |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
        return length, offset

    def _to_varint(self, value: int) -> bytes:
        """
        Converts an integer into a variable-length integer.

        Args:
            value (int): The integer to be converted.

        Returns:
            bytes: The variable-length integer.
        """
        buffer = b''

        while True:
            byte = value & 0x7F
            value >>= 7

            if value:
                buffer += bytes((byte | 0x80,))
            else:
                buffer += bytes((byte,))
                break

        return buffer
