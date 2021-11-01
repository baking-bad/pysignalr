from abc import ABC
from abc import abstractmethod
from enum import IntEnum
from enum import auto

from pysignalr.messages import Message
from pysignalr.protocol.abstract import Protocol


class ConnectionState(IntEnum):
    connecting = auto()
    connected = auto()
    reconnecting = auto()
    disconnected = auto()


class Transport(ABC):
    protocol: Protocol
    state: ConnectionState

    @abstractmethod
    async def run(self) -> None:
        ...

    @abstractmethod
    async def send(self, message: Message) -> None:
        ...
