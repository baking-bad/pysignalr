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
        data = dict(self.__dict__)

        invocation_id = data.pop('invocation_id', None)
        stream_ids = data.pop('stream_ids', None)
        headers = data.pop('headers', None)

        data['type'] = self.type  # type: ignore[attr-defined]
        if invocation_id is not None:
            data['invocationId'] = invocation_id
        if stream_ids is not None:
            data['streamIds'] = stream_ids
        if headers is not None:
            data['headers'] = headers

        return data


@dataclass
class CancelInvocationMessage(Message, type_=MessageType.cancel_invocation):
    """
    Sent by the client to cancel a streaming invocation on the server.

    Attributes:
        invocation_id (str): The ID of the streaming invocation to cancel.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    headers: dict[str, Any] | None = None


@dataclass
class CloseMessage(Message, type_=MessageType.close):
    """
    Sent by the server to indicate the connection is being closed.

    Attributes:
        error (str | None): The reason for closing, if it was due to an error.
        allow_reconnect (bool | None): Whether the client is allowed to reconnect.
        headers (dict[str, Any] | None): Optional headers.
    """

    error: str | None = None
    allow_reconnect: bool | None = None
    headers: dict[str, Any] | None = None


@dataclass
class CompletionClientStreamMessage(Message, type_=MessageType.completion):
    """
    Sent by the client to signal the end of a client-to-server stream.

    Attributes:
        invocation_id (str): The ID of the streaming invocation to complete.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    headers: dict[str, Any] | None = None


@dataclass
class CompletionMessage(Message, type_=MessageType.completion):
    """
    Sent by the server to indicate the completion of a method invocation or stream.

    Only optional fields that are present are included in the serialized output.

    Attributes:
        invocation_id (str): The ID of the invocation.
        result (Any | None): The result of the invocation, if successful.
        error (str | None): The error message, if the invocation failed.
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
    Invocation message requesting a method call on the remote peer.

    When `invocation_id` is `None` the invocation is fire-and-forget
    (non-blocking) and the server will not send a `CompletionMessage`.

    Attributes:
        invocation_id (str | None): The ID of the invocation, or None for non-blocking calls.
        target (str): The target method name.
        arguments (Any): The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
        stream_ids (list[str] | None): IDs of client-to-server streams attached to this invocation.
    """

    invocation_id: str | None
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None
    stream_ids: list[str] | None = None


@dataclass
class InvocationClientStreamMessage(Message, type_=MessageType.invocation):
    """
    Invocation message with attached client-to-server streams.

    Distinguished from `InvocationMessage` by the presence of `stream_ids`.

    Attributes:
        stream_ids (list[str]): The IDs of client-to-server streams.
        target (str): The target method name.
        arguments (Any): The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
        invocation_id (str | None): The ID of the invocation, if the server expects a response.
    """

    stream_ids: list[str]
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None
    invocation_id: str | None = None


@dataclass
class PingMessage(Message, type_=MessageType.ping):
    """
    Ping message.
    """

    pass


@dataclass
class StreamInvocationMessage(Message, type_=MessageType.stream_invocation):
    """
    Requests a server-to-client streaming invocation.

    The server responds with zero or more `StreamItemMessage` followed by
    a `CompletionMessage`.

    Attributes:
        invocation_id (str): The ID of the streaming invocation.
        target (str): The target method name.
        arguments (Any): The arguments for the method invocation.
        headers (dict[str, Any] | None): Optional headers.
        stream_ids (list[str] | None): IDs of client-to-server streams attached to this invocation.
    """

    invocation_id: str
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None
    stream_ids: list[str] | None = None


@dataclass
class StreamItemMessage(Message, type_=MessageType.stream_item):
    """
    A single item in a server-to-client or client-to-server stream.

    Attributes:
        invocation_id (str): The ID of the streaming invocation this item belongs to.
        item (Any): The stream item payload.
        headers (dict[str, Any] | None): Optional headers.
    """

    invocation_id: str
    item: Any
    headers: dict[str, Any] | None = None


class JSONMessage(Message, type_=MessageType._):
    """
    Raw JSON message wrapper used by `BaseJSONProtocol` to bypass typed message parsing.

    Attributes:
        data (dict[str, Any]): The raw JSON payload.
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
