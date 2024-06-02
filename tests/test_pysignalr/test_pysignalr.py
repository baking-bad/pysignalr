import asyncio
import logging
import time
from contextlib import suppress
from unittest.async_case import IsolatedAsyncioTestCase

import pytest
import requests

from pysignalr.client import SignalRClient
from pysignalr.exceptions import AuthorizationError, ServerError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def wait_for_server(url, timeout=30):
    """
    Waits for the server to be ready.

    Args:
        url (str): The URL to check the server status.
        timeout (int): The maximum time to wait for the server to be ready.
    """
    start = time.time()
    while True:
        try:
            response = requests.post(url, json={'username': 'test', 'password': 'password'}, timeout=10)
            if response.status_code in [200, 401, 403]:
                logging.info('Server is up and running at %s', url)
                break
        except requests.exceptions.RequestException as e:
            logging.info('Waiting for server: %s', e)
        if time.time() - start > timeout:
            raise TimeoutError('Server did not start in time')
        time.sleep(2)


class TestPysignalr(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Sets up the test class by waiting for the server to be ready.
        """
        logging.info('Waiting for ASP.NET server to be ready...')
        time.sleep(5)  # Small additional delay
        wait_for_server('http://aspnet-server/api/auth/login', timeout=30)

    async def test_connection(self) -> None:
        """
        Tests connection to the SignalR server.
        """
        url = 'http://aspnet-server/weatherHub'
        logging.info('Testing connection to %s', url)
        client = SignalRClient(url)

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection opened, cancelling task')
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            await task

    async def test_connection_with_token(self) -> None:
        """
        Tests connection to the SignalR server with a valid token.
        """
        login_url = 'http://aspnet-server/api/auth/login'
        logging.info('Attempting to log in at %s', login_url)
        login_data = {'username': 'test', 'password': 'password'}
        response = requests.post(login_url, json=login_data, timeout=10)
        token = response.json().get('token')
        if not token:
            self.fail('Failed to obtain token from login response')

        url = 'http://aspnet-server/weatherHub'
        logging.info('Testing connection with token to %s', url)

        def token_factory():
            return token

        client = SignalRClient(
            url=url,
            access_token_factory=token_factory,
            headers={'mycustomheader': 'mycustomheadervalue'},
        )

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection with token opened, cancelling task')
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            await task

        # Verify the token in the connection headers
        self.assertIn('Authorization', client._transport._headers)
        self.assertEqual(client._transport._headers['Authorization'], f'Bearer {token}')

    async def test_invalid_token(self) -> None:
        """
        Tests connection to the SignalR server with an invalid token.
        """
        url = 'http://aspnet-server/weatherHub'
        logging.info('Testing connection with invalid token to %s', url)

        def invalid_token_factory():
            return 'invalid_token'  # Simulate an invalid token

        client = SignalRClient(
            url=url,
            access_token_factory=invalid_token_factory,
            headers={'mycustomheader': 'mycustomheadervalue'},
        )

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection with invalid token opened, cancelling task')
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            try:
                await task
            except AuthorizationError:
                logging.info('AuthorizationError caught as expected')
                pass

        # Verify if the AuthorizationError was raised correctly
        self.assertTrue(task.cancelled())

    @pytest.mark.asyncio
    async def test_send_and_receive_message(self) -> None:
        """
        Tests sending and receiving a message with the SignalR server.
        """
        login_url = 'http://aspnet-server/api/auth/login'
        logging.info('Attempting to log in at %s', login_url)
        login_data = {'username': 'test', 'password': 'password'}
        response = requests.post(login_url, json=login_data, timeout=10)
        token = response.json().get('token')
        if not token:
            logging.error('Failed to obtain token from login response')
            raise AssertionError('Failed to obtain token from login response')
        logging.info('Obtained token: %s', token)

        url = 'http://aspnet-server/weatherHub'
        logging.info('Testing send and receive message with token to %s', url)

        def token_factory():
            return token

        client = SignalRClient(
            url=url,
            access_token_factory=token_factory,
            headers={'mycustomheader': 'mycustomheadervalue'},
        )

        received_messages = []

        async def on_message_received(arguments):
            user, message = arguments
            logging.info('Message received from %s: %s', user, message)
            received_messages.append((user, message))
            if len(received_messages) >= 1:
                task.cancel()

        client.on('ReceiveMessage', on_message_received)

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection with token opened, sending message')
            await client.send('SendMessage', ['testuser', 'Hello, World!'])

        client.on_open(_on_open)

        try:
            with suppress(asyncio.CancelledError):
                await task
        except ServerError as e:
            logging.error('Server error: %s', e)
            raise

        # Verify if the message was received correctly
        assert received_messages, 'No messages were received'
        assert received_messages[0] == (
            'testuser',
            'Hello, World!',
        ), f'Unexpected message received: {received_messages[0]}'

        # Log detailed messages received
        for user, message in received_messages:
            logging.info('Detailed Log: Message from %s - %s', user, message)
