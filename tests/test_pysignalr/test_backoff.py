from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any
from typing import Literal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest
import websockets.asyncio.client
from websockets.exceptions import InvalidHandshake

import pysignalr
from pysignalr import BACKOFF_FACTOR
from pysignalr import BACKOFF_INITIAL
from pysignalr import BACKOFF_MAX
from pysignalr import BACKOFF_MIN
from pysignalr import __aiter__ as backoff_aiter
from pysignalr.exceptions import NegotiationFailure
from pysignalr.transport.websocket import WebsocketTransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connect_mock(side_effects: list[Any]) -> MagicMock:
    """
    Build a fake `websockets.asyncio.client.connect`-style object whose
    async-context-manager raises/returns items from side_effects in order.
    Raises CancelledError (BaseException) when the list is exhausted so that
    the infinite backoff loop can terminate in tests.
    """
    call_index = 0

    class _FakeConnect:
        logger = MagicMock()

        async def __aenter__(self_inner) -> Any:
            nonlocal call_index
            if call_index >= len(side_effects):
                raise asyncio.CancelledError('side_effects exhausted')
            effect = side_effects[call_index]
            call_index += 1
            if isinstance(effect, BaseException):
                raise effect
            if isinstance(effect, type) and issubclass(effect, BaseException):
                raise effect()
            return effect

        async def __aexit__(self_inner, *_: Any) -> Literal[False]:
            return False

    return _FakeConnect()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Monkey-patch
# ---------------------------------------------------------------------------

class TestMonkeyPatch:
    def test_aiter_is_patched(self) -> None:
        """pysignalr.__init__ must replace connect.__aiter__ with our version."""
        assert websockets.asyncio.client.connect.__aiter__ is pysignalr.__aiter__


# ---------------------------------------------------------------------------
# __aiter__ backoff behaviour
# ---------------------------------------------------------------------------

class TestBackoffAiter:
    async def test_raises_negotiation_failure_on_timeout(self) -> None:
        connect = _make_connect_mock([TimeoutError()])
        with pytest.raises(NegotiationFailure):
            async for _ in backoff_aiter(connect):
                pass

    async def test_raises_negotiation_failure_on_invalid_handshake(self) -> None:
        connect = _make_connect_mock([InvalidHandshake()])
        with pytest.raises(NegotiationFailure):
            async for _ in backoff_aiter(connect):
                pass

    async def test_yields_protocol_on_success(self) -> None:
        protocol = MagicMock()
        connect = _make_connect_mock([protocol])
        results = []
        with patch('pysignalr.asyncio.sleep', new_callable=AsyncMock):
            async for conn in backoff_aiter(connect):
                results.append(conn)
                break
        assert results == [protocol]

    async def test_first_failure_uses_initial_random_delay(self) -> None:
        """First failure sleeps a random fraction of BACKOFF_INITIAL, not the growing delay."""
        protocol = MagicMock()
        connect = _make_connect_mock([RuntimeError('boom'), protocol])
        sleep_mock = AsyncMock()

        with patch('pysignalr.asyncio.sleep', sleep_mock), \
             patch('pysignalr.random.random', return_value=0.5):
            async for _ in backoff_aiter(connect):
                break

        sleep_mock.assert_called_once_with(0.5 * BACKOFF_INITIAL)

    async def test_second_failure_uses_backoff_delay(self) -> None:
        """Second consecutive failure uses int(backoff_delay), not the random initial."""
        protocol = MagicMock()
        connect = _make_connect_mock([RuntimeError('first'), RuntimeError('second'), protocol])
        sleep_mock = AsyncMock()

        with patch('pysignalr.asyncio.sleep', sleep_mock), \
             patch('pysignalr.random.random', return_value=0.0):
            async for _ in backoff_aiter(connect):
                break

        assert sleep_mock.call_count == 2
        assert sleep_mock.call_args_list[0] == call(0.0)                                # initial random
        assert sleep_mock.call_args_list[1] == call(int(BACKOFF_MIN * BACKOFF_FACTOR))  # grown

    async def test_backoff_resets_after_success(self) -> None:
        """After a successful yield the backoff resets: the next failure uses initial delay again."""
        protocol = MagicMock()
        # fail → succeed → fail → (exhausted → CancelledError ends the loop)
        connect = _make_connect_mock([RuntimeError('first'), protocol, RuntimeError('second')])
        sleep_mock = AsyncMock()

        with patch('pysignalr.asyncio.sleep', sleep_mock), \
             patch('pysignalr.random.random', return_value=0.0):
            with suppress(asyncio.CancelledError):
                async for _ in backoff_aiter(connect):
                    pass  # consume the successful yield, let the generator continue

        # Both failures produce the initial-delay sleep (0.0), not a grown one.
        assert sleep_mock.call_count == 2
        assert sleep_mock.call_args_list[0] == call(0.0)
        assert sleep_mock.call_args_list[1] == call(0.0)

    async def test_backoff_capped_at_max(self) -> None:
        """Delay must never exceed BACKOFF_MAX regardless of how many failures occur."""
        failures = [RuntimeError(f'fail-{i}') for i in range(30)]
        protocol = MagicMock()
        connect = _make_connect_mock([*failures, protocol])
        sleep_mock = AsyncMock()

        with patch('pysignalr.asyncio.sleep', sleep_mock), \
             patch('pysignalr.random.random', return_value=0.0):
            async for _ in backoff_aiter(connect):
                break

        sleep_values = [c.args[0] for c in sleep_mock.call_args_list]
        assert all(s <= BACKOFF_MAX for s in sleep_values)
        assert any(s == int(BACKOFF_MAX) for s in sleep_values)


# ---------------------------------------------------------------------------
# WebsocketTransport.run() retry logic
# ---------------------------------------------------------------------------

class TestTransportRetry:
    def _make_transport(self, retry_count: int = 3, retry_sleep: float = 0.0) -> WebsocketTransport:
        return WebsocketTransport(
            url='http://localhost/hub',
            protocol=MagicMock(),
            callback=AsyncMock(),
            retry_count=retry_count,
            retry_sleep=retry_sleep,
        )

    async def test_raises_after_retry_count_exhausted(self) -> None:
        """run() propagates NegotiationFailure once retry_count reaches 0."""
        transport = self._make_transport(retry_count=2, retry_sleep=0.0)

        with patch.object(transport, '_loop', side_effect=NegotiationFailure), \
             patch('pysignalr.transport.websocket.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(NegotiationFailure):
                await transport.run()

    async def test_sleep_increases_between_retries(self) -> None:
        """Sleep duration grows by retry_multiplier between NegotiationFailure retries."""
        transport = WebsocketTransport(
            url='http://localhost/hub',
            protocol=MagicMock(),
            callback=AsyncMock(),
            retry_count=3,
            retry_sleep=1.0,
            retry_multiplier=2.0,
        )
        sleep_mock = AsyncMock()

        with patch.object(transport, '_loop', side_effect=NegotiationFailure), \
             patch('pysignalr.transport.websocket.asyncio.sleep', sleep_mock):
            with pytest.raises(NegotiationFailure):
                await transport.run()

        assert sleep_mock.call_count == 2  # 3 retries → 2 sleeps (last raises)
        sleep_values = [c.args[0] for c in sleep_mock.call_args_list]
        assert sleep_values[1] > sleep_values[0]

    async def test_successful_loop_does_not_retry(self) -> None:
        """A _loop() that returns normally must not trigger any retry sleep."""
        transport = self._make_transport(retry_count=3)
        call_count = 0

        async def _loop_then_cancel() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        sleep_mock = AsyncMock()
        with patch.object(transport, '_loop', side_effect=_loop_then_cancel), \
             patch.object(transport, '_set_state', new_callable=AsyncMock), \
             patch('pysignalr.transport.websocket.asyncio.sleep', sleep_mock):
            with suppress(asyncio.CancelledError):
                await transport.run()

        sleep_mock.assert_not_called()
