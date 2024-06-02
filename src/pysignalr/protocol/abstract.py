from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Iterable

from pysignalr.messages import (
    HandshakeRequestMessage,
    HandshakeResponseMessage,
    Message
)

class Protocol(ABC):
    """
    Abstract base class for implementing a communication protocol.

    Attributes:
        protocol (str): Name of the protocol.
        version (int): Version of the protocol.
        record_separator (str): Record separator used in the protocol.
    """

    def __init__(self, protocol: str, version: int, record_separator: str) -> None:
        """
        Initializes a Protocol object.

        Args:
            protocol (str): Name of the protocol.
            version (int): Version of the protocol.
            record_separator (str): Record separator used in the protocol.
        """
        self.protocol = protocol
        self.version = version
        self.record_separator = record_separator

    @abstractmethod
    def decode(self, raw_message: str | bytes) -> Iterable[Message]:
        """
        Decodes a raw message into a sequence of messages.

        Args:
            raw_message (str | bytes): The raw message to be decoded.

        Returns:
            Iterable[Message]: A sequence of Message objects.
        """
        ...

    @abstractmethod
    def encode(self, message: Message | HandshakeRequestMessage) -> str | bytes:
        """
        Encodes a message into a raw representation.

        Args:
            message (Message | HandshakeRequestMessage): The message to be encoded.

        Returns:
            str | bytes: The raw representation of the message.
        """
        ...

    @abstractmethod
    def decode_handshake(self, raw_message: str | bytes) -> tuple[HandshakeResponseMessage, Iterable[Message]]:
        """
        Decodes a handshake message.

        Args:
            raw_message (str | bytes): The raw handshake message to be decoded.

        Returns:
            tuple[HandshakeResponseMessage, Iterable[Message]]: A tuple containing a HandshakeResponseMessage and a sequence of Message objects.
        """
        ...

    def handshake_message(self) -> HandshakeRequestMessage:
        """
        Creates a handshake message.

        Returns:
            HandshakeRequestMessage: A HandshakeRequestMessage object.
        """
        return HandshakeRequestMessage(self.protocol, self.version)
