from __future__ import annotations

from json import JSONEncoder
from typing import TYPE_CHECKING
from typing import Any

import orjson

from pysignalr.messages import CancelInvocationMessage  # 5
from pysignalr.messages import CloseMessage  # 7
from pysignalr.messages import CompletionMessage  # 3
from pysignalr.messages import HandshakeMessage
from pysignalr.messages import HandshakeRequestMessage
from pysignalr.messages import HandshakeResponseMessage
from pysignalr.messages import InvocationMessage  # 1
from pysignalr.messages import JSONMessage  # virtual
from pysignalr.messages import Message
from pysignalr.messages import MessageType
from pysignalr.messages import PingMessage  # 6
from pysignalr.messages import StreamInvocationMessage  # 4
from pysignalr.messages import StreamItemMessage  # 2
from pysignalr.protocol.abstract import Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable


class MessageEncoder(JSONEncoder):
    """
    Custom JSONEncoder for encoding Message and MessageType objects.

    This class is a subclass of JSONEncoder and overrides the default() method
    to provide custom serialization for Message and MessageType objects.
    """

    def default(self, obj: Message | MessageType) -> str | int | dict[str, Any]:
        """
        Overrides the default() method for custom serialization.

        Args:
            obj (Message | MessageType): The object to be serialized.

        Returns:
            str | int | dict[str, Any]: The serialized object.
        """
        if isinstance(obj, MessageType):
            return obj.value
        return obj.dump()


message_encoder = MessageEncoder()


class BaseJSONProtocol(Protocol):
    """
    Base class for JSON protocols.

    This class provides the basic structure for JSON protocols and defines
    some abstract methods that must be implemented by subclasses.
    """

    def __init__(self) -> None:
        pass

    def decode(self, raw_message: str | bytes) -> tuple[JSONMessage]:
        """
        Decodes a raw message into a JSONMessage object.

        Args:
            raw_message (str | bytes): The raw message to be decoded.

        Returns:
            tuple[JSONMessage]: A tuple containing a single JSONMessage object.
        """
        json_message = orjson.loads(raw_message)
        return (JSONMessage(data=json_message),)

    def encode(self, message: Message | HandshakeRequestMessage) -> str | bytes:
        """
        Encodes a message into a raw representation.

        Args:
            message (Message | HandshakeRequestMessage): The message to be encoded.

        Returns:
            str | bytes: The raw representation of the message.
        """
        return orjson.dumps(message.dump())

    def decode_handshake(self, raw_message: str | bytes) -> tuple[HandshakeResponseMessage, Iterable[Message]]:
        """
        Decodes a handshake message.

        Args:
            raw_message (str | bytes): The raw handshake message to be decoded.

        Returns:
            tuple[HandshakeResponseMessage, Iterable[Message]]: A tuple containing a HandshakeResponseMessage and a sequence of Message objects.
        """
        raise NotImplementedError


class JSONProtocol(Protocol):
    """
    Class for handling JSON protocols.

    This class provides methods for encoding and decoding messages using the JSON protocol.
    """

    def __init__(self) -> None:
        super().__init__(
            protocol='json',
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
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode()

        raw_messages = raw_message.split(self.record_separator)
        messages: list[Message] = []

        for item in raw_messages:
            if item in ('', self.record_separator):
                continue

            dict_message = orjson.loads(item)
            if dict_message:
                messages.append(self.parse_message(dict_message))

        return messages

    def encode(self, message: Message | HandshakeMessage) -> str:
        """
        Encodes a message into a raw representation.

        Args:
            message (Message | HandshakeMessage): The message to be encoded.

        Returns:
            str: The raw representation of the message.
        """
        return message_encoder.encode(message) + self.record_separator

    def decode_handshake(self, raw_message: str | bytes) -> tuple[HandshakeResponseMessage, Iterable[Message]]:
        """
        Decodes a handshake message.

        Args:
            raw_message (str | bytes): The raw handshake message to be decoded.

        Returns:
            tuple[HandshakeResponseMessage, Iterable[Message]]: A tuple containing a HandshakeResponseMessage and a sequence of Message objects.
        """
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode()

        messages = raw_message.split(self.record_separator)
        messages = list(filter(bool, messages))
        data = orjson.loads(messages[0])
        idx = raw_message.index(self.record_separator)
        return (
            HandshakeResponseMessage(data.get('error', None)),
            self.decode(raw_message[idx + 1 :]) if len(messages) > 1 else [],
        )

    @staticmethod
    def parse_message(dict_message: dict[str, Any]) -> Message:
        """
        Parses a dictionary into a Message object.

        Args:
            dict_message (dict[str, Any]): The dictionary to be parsed.

        Returns:
            Message: The resulting Message object.
        """
        message_type = MessageType(dict_message.pop('type', 'close'))

        if message_type is MessageType.invocation:
            dict_message['invocation_id'] = dict_message.pop('invocationId', None)
            return InvocationMessage(**dict_message)
        elif message_type is MessageType.stream_item:
            return StreamItemMessage(**dict_message)
        elif message_type is MessageType.completion:
            dict_message['invocation_id'] = dict_message.pop('invocationId', None)
            return CompletionMessage(**dict_message)
        elif message_type is MessageType.stream_invocation:
            return StreamInvocationMessage(**dict_message)
        elif message_type is MessageType.cancel_invocation:
            return CancelInvocationMessage(**dict_message)
        elif message_type is MessageType.ping:
            return PingMessage()
        elif message_type is MessageType.close:
            dict_message['allow_reconnect'] = dict_message.pop('allowReconnect', None)
            return CloseMessage(**dict_message)
        else:
            raise NotImplementedError
