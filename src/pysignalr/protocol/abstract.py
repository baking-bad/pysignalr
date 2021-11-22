from abc import ABC
from abc import abstractmethod
from typing import Iterable
from typing import Tuple
from typing import Union

from pysignalr.messages import HandshakeRequestMessage
from pysignalr.messages import HandshakeResponseMessage
from pysignalr.messages import Message


class Protocol(ABC):
    def __init__(self, protocol: str, version: int, record_separator: str) -> None:
        self.protocol = protocol
        self.version = version
        self.record_separator = record_separator

    @abstractmethod
    def decode(self, raw_message: Union[str, bytes]) -> Iterable[Message]:
        ...

    @abstractmethod
    def encode(self, message: Union[Message, HandshakeRequestMessage]) -> Union[str, bytes]:
        ...

    @abstractmethod
    def decode_handshake(self, raw_message: Union[str, bytes]) -> Tuple[HandshakeResponseMessage, Iterable[Message]]:
        ...

    def handshake_message(self) -> HandshakeRequestMessage:
        return HandshakeRequestMessage(self.protocol, self.version)
