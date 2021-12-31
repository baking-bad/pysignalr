from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HubError(Exception):
    ...


@dataclass(frozen=True)
class AuthorizationError(HubError):
    pass


@dataclass(frozen=True)
class ConnectionError(HubError):
    status: int


@dataclass(frozen=True)
class ServerError(HubError):
    message: Optional[str]
