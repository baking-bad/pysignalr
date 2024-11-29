import asyncio
import importlib.metadata
import random
from collections.abc import AsyncIterator

import websockets.legacy.client
from websockets.exceptions import InvalidStatusCode

from pysignalr.exceptions import NegotiationFailure

# Get the version of the 'pysignalr' package
__version__ = importlib.metadata.version('pysignalr')


async def __aiter__(
    self: websockets.legacy.client.Connect,
) -> AsyncIterator[websockets.legacy.client.WebSocketClientProtocol]:
    """
    Asynchronous iterator for the Connect object.

    This function attempts to establish a connection and yields the protocol when successful.
    If the connection fails, it retries with an exponential backoff.

    Args:
        self (websockets.legacy.client.Connect): The Connect object.

    Yields:
        websockets.legacy.client.WebSocketClientProtocol: The WebSocket protocol.

    Raises:
        NegotiationFailure: If the connection URL is no longer valid during negotiation.
    """
    backoff_delay = self.BACKOFF_MIN
    while True:
        try:
            async with self as protocol:
                yield protocol
        # Handle expired connection URLs by raising a NegotiationFailure exception.
        except (TimeoutError, InvalidStatusCode) as e:
            raise NegotiationFailure from e

        except Exception:
            # Add a random initial delay between 0 and 5 seconds.
            # See 7.2.3. Recovering from Abnormal Closure in RFC 6544.
            if backoff_delay == self.BACKOFF_MIN:
                initial_delay = random.random() * self.BACKOFF_INITIAL
                self.logger.info(
                    '! connect failed; reconnecting in %.1f seconds',
                    initial_delay,
                    exc_info=True,
                )
                await asyncio.sleep(initial_delay)
            else:
                self.logger.info(
                    '! connect failed again; retrying in %d seconds',
                    int(backoff_delay),
                    exc_info=True,
                )
                await asyncio.sleep(int(backoff_delay))
            # Increase delay with truncated exponential backoff.
            backoff_delay = backoff_delay * self.BACKOFF_FACTOR
            backoff_delay = min(backoff_delay, self.BACKOFF_MAX)
            continue
        else:
            # Connection succeeded - reset backoff delay.
            backoff_delay = self.BACKOFF_MIN


# Override the __aiter__ method of the Connect class
websockets.legacy.client.Connect.__aiter__ = __aiter__  # type: ignore[method-assign]
