from unittest import TestCase

from pysignalr.utils import get_connection_url
from pysignalr.utils import get_negotiate_url
from pysignalr.utils import replace_scheme


class UtilsTest(TestCase):
    def test_replace_scheme(self) -> None:
        url = 'http://localhost:8080'
        self.assertEqual('ws://localhost:8080', replace_scheme(url, ws=True))

        url = 'https://localhost:8080'
        self.assertEqual('https://localhost:8080', replace_scheme(url, ws=False))

        url = 'ws://localhost:8080'
        self.assertEqual('ws://localhost:8080', replace_scheme(url, ws=True))

        url = 'wss://localhost:8080'
        self.assertEqual('https://localhost:8080', replace_scheme(url, ws=False))

    def test_get_negotiate_url(self) -> None:
        url = 'http://localhost:8080'
        self.assertEqual('http://localhost:8080/negotiate', get_negotiate_url(url))

        url = 'https://localhost:8080?foo=bar'
        self.assertEqual('https://localhost:8080/negotiate?foo=bar', get_negotiate_url(url))

    def test_get_connection_url(self) -> None:
        url = 'http://localhost:8080/v1/events?foo=bar'
        self.assertEqual('ws://localhost:8080/v1/events?foo=bar&id=1&id=2&id=3', get_connection_url(url, ['1', '2', '3']))
