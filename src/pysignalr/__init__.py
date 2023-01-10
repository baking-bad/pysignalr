__version__ = '0.1.2'

import asyncio
import random
from http import HTTPStatus
from typing import AsyncIterator

import websockets.legacy.client
from websockets.exceptions import InvalidStatusCode


class NegotiationTimeout(Exception):
    """Connection URL generated during negotiation is no longer valid"""

    pass


async def __aiter__(
    self: websockets.legacy.client.Connect,
) -> AsyncIterator[websockets.legacy.client.WebSocketClientProtocol]:
    backoff_delay = self.BACKOFF_MIN
    while True:
        try:
            async with self as protocol:
                yield protocol

        # NOTE: The following block was added to the original code to handle expired connection URLs.
        except InvalidStatusCode as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise NegotiationTimeout from e
        except asyncio.TimeoutError as e:
            raise NegotiationTimeout from e

        except Exception:
            # Add a random initial delay between 0 and 5 seconds.
            # See 7.2.3. Recovering from Abnormal Closure in RFC 6544.
            if backoff_delay == self.BACKOFF_MIN:
                initial_delay = random.random() * self.BACKOFF_INITIAL
                self.logger.info(
                    "! connect failed; reconnecting in %.1f seconds",
                    initial_delay,
                    exc_info=True,
                )
                await asyncio.sleep(initial_delay)
            else:
                self.logger.info(
                    "! connect failed again; retrying in %d seconds",
                    int(backoff_delay),
                    exc_info=True,
                )
                await asyncio.sleep(int(backoff_delay))
            # Increase delay with truncated exponential backoff.
            backoff_delay = backoff_delay * self.BACKOFF_FACTOR
            backoff_delay = min(backoff_delay, self.BACKOFF_MAX)
            continue
        else:
            # Connection succeeded - reset backoff delay
            backoff_delay = self.BACKOFF_MIN


websockets.legacy.client.Connect.__aiter__ = __aiter__  # type: ignore[assignment]
