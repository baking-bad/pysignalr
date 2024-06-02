import asyncio
import atexit
import logging
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from typing import cast

import _pytest.outcomes
import pytest
import requests
from docker.client import DockerClient  # type: ignore[import-untyped]

from pysignalr.client import SignalRClient
from pysignalr.exceptions import AuthorizationError
from pysignalr.exceptions import ServerError

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def get_docker_client() -> 'DockerClient':
    """Get Docker client instance if socket is available; skip test otherwise."""

    docker_socks = (
        Path('/var/run/docker.sock'),
        Path.home() / 'Library' / 'Containers' / 'com.docker.docker' / 'Data' / 'vms' / '0' / 'docker.sock',
        Path.home() / 'Library' / 'Containers' / 'com.docker.docker' / 'Data' / 'docker.sock',
    )
    for path in docker_socks:
        if path.exists():
            return DockerClient(base_url=f'unix://{path}')

    raise _pytest.outcomes.Skipped(  # pragma: no cover
        'Docker socket not found',
        allow_module_level=True,
    )


@pytest.fixture(scope='module')
async def aspnet_server() -> str:
    """Run dummy ASPNet server container (destroyed on exit) and return its IP."""
    docker = get_docker_client()

    logging.info('Building ASPNet server image (this may take a while)')
    docker.images.build(
        path=Path(__file__).parent.parent.parent.joinpath('AspNetAuthExample').as_posix(),
        tag='aspnet_server',
    )

    logging.info('Starting ASPNet server container')
    container = docker.containers.run(
        image='aspnet_server',
        environment={
            'ASPNETCORE_ENVIRONMENT': 'Development',
            'ASPNETCORE_URLS': 'http://+:80',
        },
        detach=True,
        remove=True,
    )
    atexit.register(container.stop)
    container.reload()
    ip = cast(str, container.attrs['NetworkSettings']['IPAddress'])

    logging.info('Waiting for server to start')
    wait_for_server(f'http://{ip}/api/auth/login')

    return ip


def wait_for_server(url: str, timeout: int = 30) -> None:
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


class TestPysignalr:
    async def test_connection(self, aspnet_server: str) -> None:
        """
        Tests connection to the SignalR server.
        """
        url = f'http://{aspnet_server}/weatherHub'
        logging.info('Testing connection to %s', url)
        client = SignalRClient(url)

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection opened, cancelling task')
            task.cancel()

        client.on_open(_on_open)

        with suppress(asyncio.CancelledError):
            await task

    async def test_connection_with_token(self, aspnet_server: str) -> None:
        """
        Tests connection to the SignalR server with a valid token.
        """
        login_url = f'http://{aspnet_server}/api/auth/login'
        logging.info('Attempting to log in at %s', login_url)
        login_data = {'username': 'test', 'password': 'password'}
        response = requests.post(login_url, json=login_data, timeout=10)
        token = response.json().get('token')
        if not token:
            pytest.fail('Failed to obtain token from login response')

        url = f'http://{aspnet_server}/weatherHub'
        logging.info('Testing connection with token to %s', url)

        def token_factory() -> str:
            return cast(str, token)

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
        assert 'Authorization' in client._transport._headers
        assert client._transport._headers['Authorization'] == f'Bearer {token}'

    async def test_invalid_token(self, aspnet_server: str) -> None:
        """
        Tests connection to the SignalR server with an invalid token.
        """
        url = f'http://{aspnet_server}/weatherHub'
        logging.info('Testing connection with invalid token to %s', url)

        def invalid_token_factory() -> str:
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
        assert task.cancelled() is True

    async def test_send_and_receive_message(self, aspnet_server: str) -> None:
        """
        Tests sending and receiving a message with the SignalR server.
        """
        login_url = f'http://{aspnet_server}/api/auth/login'
        logging.info('Attempting to log in at %s', login_url)
        login_data = {'username': 'test', 'password': 'password'}
        response = requests.post(login_url, json=login_data, timeout=10)
        token = response.json().get('token')
        if not token:
            logging.error('Failed to obtain token from login response')
            raise AssertionError('Failed to obtain token from login response')
        logging.info('Obtained token: %s', token)

        url = f'http://{aspnet_server}/weatherHub'
        logging.info('Testing send and receive message with token to %s', url)

        def token_factory() -> str:
            return cast(str, token)

        client = SignalRClient(
            url=url,
            access_token_factory=token_factory,
            headers={'mycustomheader': 'mycustomheadervalue'},
        )

        received_messages = []

        async def on_message_received(arguments: Any) -> None:
            user, message = arguments
            logging.info('Message received from %s: %s', user, message)
            received_messages.append((user, message))
            if len(received_messages) >= 1:
                task.cancel()

        client.on('ReceiveMessage', on_message_received)

        task = asyncio.create_task(client.run())

        async def _on_open() -> None:
            logging.info('Connection with token opened, sending message')
            await client.send('SendMessage', ['testuser', 'Hello, World!'])  # type: ignore[list-item]

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
