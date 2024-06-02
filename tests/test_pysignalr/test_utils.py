from unittest import TestCase

from pysignalr.utils import get_connection_url, get_negotiate_url, replace_scheme


class UtilsTest(TestCase):
    """
    Unit tests for the utility functions in the pysignalr.utils module.
    """

    def test_replace_scheme(self) -> None:
        """
        Tests the replace_scheme function to ensure it correctly replaces URL schemes.
        """
        url = 'http://localhost:8080'
        self.assertEqual('ws://localhost:8080', replace_scheme(url, ws=True))

        url = 'https://localhost:8080'
        self.assertEqual('https://localhost:8080', replace_scheme(url, ws=False))

        url = 'ws://localhost:8080'
        self.assertEqual('ws://localhost:8080', replace_scheme(url, ws=True))

        url = 'wss://localhost:8080'
        self.assertEqual('https://localhost:8080', replace_scheme(url, ws=False))

    def test_get_negotiate_url(self) -> None:
        """
        Tests the get_negotiate_url function to ensure it correctly constructs negotiation URLs.
        """
        url = 'http://localhost:8080'
        self.assertEqual('http://localhost:8080/negotiate', get_negotiate_url(url))

        url = 'https://localhost:8080?foo=bar'
        self.assertEqual('https://localhost:8080/negotiate?foo=bar', get_negotiate_url(url))

    def test_get_connection_url(self) -> None:
        """
        Tests the get_connection_url function to ensure it correctly constructs connection URLs with IDs.
        """
        url = 'http://localhost:8080/v1/events?foo=bar'
        self.assertEqual(
            'ws://localhost:8080/v1/events?foo=bar&id=1&id=2&id=3', get_connection_url(url, ['1', '2', '3'])
        )
