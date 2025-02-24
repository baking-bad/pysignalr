from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


@dataclass
class HandshakeMessage:
    """
    Base class for handshake messages.
    """

    def dump(self) -> dict[str, Any]:
        """
        Dumps the handshake message into a dictionary.

        Returns:
            dict[str, Any]: The dictionary representation of the handshake message.
        """
        return self.__dict__


@dataclass
class HandshakeRequestMessage(HandshakeMessage):
    """
    Handshake request message.

    Attributes:
        protocol (str): The protocol name.
        version (int): The protocol version.
    """

    protocol: str
    version: int


@dataclass
class HandshakeResponseMessage(HandshakeMessage):
    """
    Handshake response message.

    Attributes:
        error (str | None): The error message if the handshake failed.
    """

    error: str | None


class MessageType(IntEnum):
    """
    Enum representing the type of messages.

    Attributes:
        invocation (int): Invocation message type.
        stream_item (int): Stream item message type.
        completion (int): Completion message type.
        stream_invocation (int): Stream invocation message type.
        cancel_invocation (int): Cancel invocation message type.
        ping (int): Ping message type.
        close (int): Close message type.
        invocation_binding_failure (int): Invocation binding failure message type.
    """

    _ = 9999
    invocation = 1
    stream_item = 2
    completion = 3
    stream_invocation = 4
    cancel_invocation = 5
    ping = 6
    close = 7
    invocation_binding_failure = -1


@dataclass
class Message:
    """
    Base class for all messages.

    Methods:
        dump() -> dict[str, Any]: Dumps the message into a dictionary.
    """

    def __init_subclass__(cls, type_: MessageType) -> None:
        cls.type = type_  # type: ignore[attr-defined]

    def dump(self) -> dict[str, Any]:
        """
        Dumps the message into a dictionary.

        Returns:
            dict[str, Any]: The dictionary representation of the message.
        """
        data = self.__dict__

        invocation_id = data.pop('invocation_id', None)
        stream_ids = data.pop('stream_ids', None)

        data['type'] = self.type  # type: ignore[attr-defined]
        if invocation_id is not None:
            data['invocationId'] = invocation_id
        if stream_ids is not None:
            data['streamIds'] = stream_ids

        return data


@dataclass
class ResponseMessage(Message, type_=MessageType._):
    """
    Response message.

    Attributes:
        error (str | None): The error message.
        result (Any | None): The result of the message.
    """

    error: str | None
    result: Any | None


@dataclass
class CancelInvocationMessage(Message, type_=MessageType.cancel_invocation):
    """
    Cancel invocation message.

    Attributes:
        invocation_id (str): The ID of the invocation to cancel.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    headers: dict[str, Any] | None = None


@dataclass
class CloseMessage(Message, type_=MessageType.close):
    """
    Close message.

    Attributes:
        error (str | None): Optional error message.
        allow_reconnect (bool | None): Whether reconnection is allowed.
        headers (dict[str, Any] | None): Optional headers.
    """

    error: str | None = None
    allow_reconnect: bool | None = None
    headers: dict[str, Any] | None = None


@dataclass
class CompletionClientStreamMessage(Message, type_=MessageType.stream_item):
    """
    Completion client stream message.

    Attributes:
        invocation_id (str): The ID of the invocation.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    headers: dict[str, Any] | None = None


@dataclass
class CompletionMessage(Message, type_=MessageType.completion):
    """
    Completion message.

    Attributes:
        invocation_id (str): The ID of the invocation.
        result (Any | None): The result of the invocation.
        error (str | None): The error message if the invocation failed.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    result: Any | None = None
    error: str | None = None
    headers: dict[str, Any] | None = None

    def dump(self) -> dict[str, Any]:
        data = super().dump()

        result = data.pop('result', None)
        error = data.pop('error', None)
        headers = data.pop('headers', None)

        if result is not None:
            data['result'] = result
        if error is not None:
            data['error'] = error
        if headers is not None:
            data['headers'] = headers

        return data


@dataclass
class InvocationMessage(Message, type_=MessageType.invocation):
    """
    Invocation message.

    Attributes:
        invocation_id (str): The ID of the invocation.
        target (str): The target method name.
        arguments: The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


@dataclass
class InvocationClientStreamMessage(Message, type_=MessageType.invocation):
    """
    Invocation client stream message.

    Attributes:
        stream_ids (list[str]): The stream IDs.
        target (str): The target method name.
        arguments: The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
    """

    stream_ids: list[str]
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


@dataclass
class PingMessage(Message, type_=MessageType.ping):
    """
    Ping message.
    """

    pass


@dataclass
class StreamInvocationMessage(Message, type_=MessageType.stream_invocation):
    """
    Stream invocation message.

    Attributes:
        invocation_id (str): The ID of the invocation.
        target (str): The target method name.
        arguments: The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


@dataclass
class StreamItemMessage(Message, type_=MessageType.stream_item):
    """
    Stream item message.

    Attributes:
        invocation_id (str): The ID of the invocation.
        item: The stream item.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    item: Any
    headers: dict[str, Any] | None = None


class JSONMessage(Message, type_=MessageType._):
    """
    JSON message used in BaseJSONProtocol to skip pysignalr-specific things.

    Attributes:
        data (dict[str, Any]): The JSON data.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def dump(self) -> dict[str, Any]:
        """
        Dumps the JSON message into a dictionary.

        Returns:
            dict[str, Any]: The dictionary representation of the JSON message.
        """
        return self.data
