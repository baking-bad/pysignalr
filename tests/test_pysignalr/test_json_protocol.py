from __future__ import annotations

from pysignalr.messages import MessageType
from pysignalr.protocol.json import MessageEncoder


class TestMessageEncoder:
    def test_message_type_returns_value(self) -> None:
        encoder = MessageEncoder()
        assert encoder.default(MessageType.ping) == 6
