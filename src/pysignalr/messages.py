from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


@dataclass
class HandshakeMessage:
    def dump(self) -> dict[str, Any]:
        return self.__dict__


@dataclass
class HandshakeRequestMessage(HandshakeMessage):
    protocol: str
    version: int


@dataclass
class HandshakeResponseMessage(HandshakeMessage):
    error: str | None


class MessageType(IntEnum):
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
    def __init_subclass__(cls, type_: MessageType) -> None:
        cls.type = type_  # type: ignore[attr-defined]

    def dump(self) -> dict[str, Any]:
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
    error: str | None
    result: Any | None


"""
A `CancelInvocation` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `5`,
    indicating that this message is a `CancelInvocation`.
* `invocationId` - A `String` encoding the `Invocation ID` for a message.

Example
```json
{
    "type": 5,
    "invocationId": "123"
}
"""


@dataclass
class CancelInvocationMessage(Message, type_=MessageType.cancel_invocation):
    invocation_id: str
    headers: dict[str, Any] | None = None


"""
A `Close` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `7`,
    indicating that this message is a `Close`.
* `error` - An optional `String` encoding the error message.

Example - A `Close` message without an error
```json
{
    "type": 7
}
```

Example - A `Close` message with an error
```json
{
    "type": 7,
    "error": "Connection closed because of an error!"
}
```
"""


@dataclass
class CloseMessage(Message, type_=MessageType.close):
    error: str | None = None
    allow_reconnect: bool | None = None
    headers: dict[str, Any] | None = None


"""
A `Completion` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `3`,
    indicating that this message is a `Completion`.
* `invocationId` - A `String` encoding the `Invocation ID` for a message.
* `result` - A `Token` encoding the result value
    (see "JSON Payload Encoding" for details).
    This field is **ignored** if `error` is present.
* `error` - A `String` encoding the error message.

It is a protocol error to include both a `result` and an `error` property
    in the `Completion` message. A conforming endpoint may immediately
    terminate the connection upon receiving such a message.

Example - A `Completion` message with no result or error

```json
{
    "type": 3,
    "invocationId": "123"
}
```

Example - A `Completion` message with a result

```json
{
    "type": 3,
    "invocationId": "123",
    "result": 42
}
```

Example - A `Completion` message with an error

```json
{
    "type": 3,
    "invocationId": "123",
    "error": "It didn't work!"
}
```

Example - The following `Completion` message is a protocol error
    because it has both of `result` and `error`

```json
{
    "type": 3,
    "invocationId": "123",
    "result": 42,
    "error": "It didn't work!"
}
```
"""


@dataclass
class CompletionClientStreamMessage(Message, type_=MessageType.stream_item):
    invocation_id: str
    headers: dict[str, Any] | None = None


@dataclass
class CompletionMessage(Message, type_=MessageType.completion):
    invocation_id: str
    result: Any | None = None
    error: str | None = None
    headers: dict[str, Any] | None = None


"""

An `Invocation` message is a JSON object with the following properties:

* `type` - A `Number` with the literal value 1, indicating that this message
    is an Invocation.
* `invocationId` - An optional `String` encoding the `Invocation ID`
    for a message.
* `target` - A `String` encoding the `Target` name, as expected by the Callee's
    Binder
* `arguments` - An `Array` containing arguments to apply to the method
    referred to in Target. This is a sequence of JSON `Token`s,
        encoded as indicated below in the "JSON Payload Encoding" section

Example:

```json
{
    "type": 1,
    "invocationId": "123",
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
```
Example (Non-Blocking):

```json
{
    "type": 1,
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
```

"""


@dataclass
class InvocationMessage(Message, type_=MessageType.invocation):
    invocation_id: str
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


@dataclass
class InvocationClientStreamMessage(Message, type_=MessageType.invocation):
    stream_ids: list[str]
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


"""
A `Ping` message is a JSON object with the following properties:

* `type` - A `Number` with the literal value `6`,
    indicating that this message is a `Ping`.

Example
```json
{
    "type": 6
}
```
"""


@dataclass
class PingMessage(Message, type_=MessageType.ping):
    pass


"""
A `StreamInvocation` message is a JSON object with the following properties:

* `type` - A `Number` with the literal value 4, indicating that
    this message is a StreamInvocation.
* `invocationId` - A `String` encoding the `Invocation ID` for a message.
* `target` - A `String` encoding the `Target` name, as expected
    by the Callee's Binder.
* `arguments` - An `Array` containing arguments to apply to
    the method referred to in Target. This is a sequence of JSON
    `Token`s, encoded as indicated below in the
    "JSON Payload Encoding" section.

Example:

```json
{
    "type": 4,
    "invocationId": "123",
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
```
"""


@dataclass
class StreamInvocationMessage(Message, type_=MessageType.stream_invocation):
    invocation_id: str
    target: str
    arguments: Any
    headers: dict[str, Any] | None = None


"""
A `StreamItem` message is a JSON object with the following properties:

* `type` - A `Number` with the literal value 2, indicating
    that this message is a `StreamItem`.
* `invocationId` - A `String` encoding the `Invocation ID` for a message.
* `item` - A `Token` encoding the stream item
    (see "JSON Payload Encoding" for details).

Example

```json
{
    "type": 2,
    "invocationId": "123",
    "item": 42
}
```
"""


@dataclass
class StreamItemMessage(Message, type_=MessageType.stream_item):
    invocation_id: str
    item: Any
    headers: dict[str, Any] | None = None


class JSONMessage(Message, type_=MessageType._):
    """Not a real message type; used in BaseJSONProtocol to skip pysignalr-specific things"""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def dump(self) -> dict[str, Any]:
        return self.data
