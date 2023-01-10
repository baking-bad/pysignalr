# TODO: Refactor this module
import json
from collections import deque
from typing import Any
from typing import Deque
from typing import Iterable
from typing import List
from typing import Sequence
from typing import Tuple
from typing import Union
from typing import cast

import msgpack  # type: ignore[import]

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
    def __init__(self) -> None:
        super().__init__(
            protocol='messagepack',
            version=1,
            record_separator=chr(0x1E),
        )

    def decode(self, raw_message: Union[str, bytes]) -> List[Message]:
        messages: List[Message] = []
        offset = 0
        while offset < len(raw_message):
            length = msgpack.unpackb(raw_message[offset : offset + 1])
            values = msgpack.unpackb(raw_message[offset + 1 : offset + length + 1])
            offset += length + 1
            message = self.parse_message(values)
            messages.append(message)
        return messages

    def encode(self, message: Union[Message, HandshakeRequestMessage]) -> bytes:
        raw_message: Deque[Any] = deque()

        for attr in _attribute_priority:
            if hasattr(message, attr):
                if attr == 'type_':
                    raw_message.append(getattr(message, attr).value)
                else:
                    raw_message.append(getattr(message, attr))

        encoded_message = cast(bytes, msgpack.packb(raw_message))
        varint_length = self._to_varint(len(encoded_message))
        return varint_length + encoded_message

    def decode_handshake(self, raw_message: Union[str, bytes]) -> Tuple[HandshakeResponseMessage, Iterable[Message]]:
        if isinstance(raw_message, str):
            raw_message = raw_message.encode()

        has_various_messages = 0x1E in raw_message
        handshake_data = raw_message[0 : raw_message.index(0x1E)] if has_various_messages else raw_message
        messages = self.decode(raw_message[raw_message.index(0x1E) + 1 :]) if has_various_messages else []
        data = json.loads(handshake_data)
        return HandshakeResponseMessage(data.get('error', None)), messages

    @staticmethod
    def parse_message(seq_message: Sequence[Any]) -> Message:
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
            if len(msg[5]) > 0:
                return InvocationClientStreamMessage(headers=msg[1], stream_ids=msg[5], target=msg[3], arguments=msg[4])
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
            return StreamInvocationMessage(headers=msg[1], invocation_id=msg[2], target=msg[3], arguments=msg[4])
        elif message_type is MessageType.cancel_invocation:
            return CancelInvocationMessage(headers=msg[1], invocation_id=msg[2])
        elif message_type is MessageType.ping:
            return PingMessage()
        elif message_type is MessageType.close:
            return CloseMessage(*msg[1:])
        else:
            raise NotImplementedError

    def _to_varint(self, value: int) -> bytes:
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
