import importlib.metadata

# Get the version of the 'pysignalr' package
__version__ = importlib.metadata.version('pysignalr')

import asyncio
import random
from typing import AsyncIterator

import websockets.legacy.client
from websockets.exceptions import InvalidStatusCode


class NegotiationNotfound(Exception):
    """
    Exception raised when the connection URL generated during negotiation is no longer valid (HTTP error 404).
    """
    pass

class NegotiationFailure(Exception):
    """
    Exception raised when the connection fails (all other HTTP return codes except 404).
    """
    pass

class NegotiationTimeout(Exception):
    """
    Exception raised when the connection times out.
    """
    pass


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
        NegotiationTimeout: If the connection URL is no longer valid during negotiation.
    """
    backoff_delay = self.BACKOFF_MIN
    while True:
        try:
            async with self as protocol:
                yield protocol

        # Handle expired connection URLs by raising a NegotiationTimeout exception.
        except InvalidStatusCode as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise NegotiationNotfound from e
            else:
                raise NegotiationFailure from e
        except asyncio.TimeoutError as e:
            raise NegotiationTimeout from e

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
