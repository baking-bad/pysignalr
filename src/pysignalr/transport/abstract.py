from abc import ABC
from abc import abstractmethod
from enum import IntEnum
from enum import auto

from pysignalr.messages import Message
from pysignalr.protocol.abstract import Protocol


class ConnectionState(IntEnum):
    """
    Enum representing the state of a connection.

    Attributes:
        connecting: The connection is being established.
        connected: The connection has been successfully established.
        reconnecting: The connection is being reestablished after being lost.
        disconnected: The connection has been lost or intentionally closed.
    """
    connecting = auto()
    connected = auto()
    reconnecting = auto()
    disconnected = auto()


class Transport(ABC):
    """
    Abstract base class for implementing a transport protocol.

    Attributes:
        protocol (Protocol): The protocol used by the transport.
        state (ConnectionState): The current state of the connection.
    """

    protocol: Protocol
    state: ConnectionState

    @abstractmethod
    async def run(self) -> None:
        """
        Abstract method for running the transport protocol.

        This method should be implemented by subclasses to handle the specifics of the transport protocol.
        """
        ...

    @abstractmethod
    async def send(self, message: Message) -> None:
        """
        Abstract method for sending a message.

        Args:
            message (Message): The message to be sent.

        This method should be implemented by subclasses to handle the specifics of the transport protocol.
        """
        ...
