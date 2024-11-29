from __future__ import annotations

import urllib.parse as parse
from contextlib import suppress

http_schemas = ('http', 'https')
websocket_schemas = ('ws', 'wss')
http_to_ws = {k: v for k, v in zip(http_schemas, websocket_schemas)}  # noqa: C416
ws_to_http = {k: v for k, v in zip(websocket_schemas, http_schemas)}  # noqa: C416


def replace_scheme(url: str, ws: bool) -> str:
    """
    Replaces the scheme of a given URL from HTTP to WebSocket or vice versa.

    Args:
        url (str): The URL whose scheme is to be replaced.
        ws (bool): If True, replace HTTP with WebSocket schemes. If False, replace WebSocket with HTTP schemes.

    Returns:
        str: The URL with the replaced scheme.
    """
    scheme, netloc, path, query, fragment = parse.urlsplit(url)

    with suppress(KeyError):
        mapping = http_to_ws if ws else ws_to_http
        scheme = mapping[scheme]

    return parse.urlunsplit((scheme, netloc, path, query, fragment))


def get_negotiate_url(url: str) -> str:
    """
    Constructs the negotiation URL for the given SignalR endpoint URL.

    Args:
        url (str): The base SignalR endpoint URL.

    Returns:
        str: The negotiation URL.
    """
    scheme, netloc, path, query, fragment = parse.urlsplit(url)

    path = path.rstrip('/') + '/negotiate'
    with suppress(KeyError):
        scheme = ws_to_http[scheme]

    return parse.urlunsplit((scheme, netloc, path, query, fragment))


def get_connection_url(url: str, id: list[str]) -> str:
    """
    Constructs the connection URL with the given connection ID.

    Args:
        url (str): The base SignalR endpoint URL.
        id (list[str]): The connection ID.

    Returns:
        str: The connection URL.
    """
    scheme, netloc, path, query, fragment = parse.urlsplit(url)

    parsed_query = parse.parse_qs(query)
    parsed_query['id'] = id
    query = parse.urlencode(parsed_query, doseq=True)
    with suppress(KeyError):
        scheme = http_to_ws[scheme]

    return parse.urlunsplit((scheme, netloc, path, query, fragment))
