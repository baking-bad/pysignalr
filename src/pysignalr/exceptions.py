from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HubError(Exception):
    """
    Base class for all Hub-related errors.
    """
    pass


@dataclass(frozen=True)
class AuthorizationError(HubError):
    """
    Exception raised for authorization errors.
    """
    pass


@dataclass(frozen=True)
class ConnectionError(HubError):
    """
    Exception raised for connection errors.

    Attributes:
        status (int): The HTTP status code related to the connection error.
    """
    status: int


@dataclass(frozen=True)
class ServerError(HubError):
    """
    Exception raised for server errors.

    Attributes:
        message (str | None): The error message from the server.
    """
    message: str | None
