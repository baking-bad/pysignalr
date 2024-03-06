from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HubError(Exception): ...


@dataclass(frozen=True)
class AuthorizationError(HubError):
    pass


@dataclass(frozen=True)
class ConnectionError(HubError):
    status: int


@dataclass(frozen=True)
class ServerError(HubError):
    message: str | None
