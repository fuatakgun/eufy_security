import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any, Text
import traceback

import aiohttp

from .exceptions import WebSocketConnectionError

_LOGGER: logging.Logger = logging.getLogger(__package__)


class WebSocketClient:
    """Websocket Client to communicate with eufy-security-ws"""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
        open_callback: Callable[[], Coroutine[Any, Any, None]],
        message_callback: Callable[[], Coroutine[Any, Any, None]],
        close_callback: Callable[[], Coroutine[Any, Any, None]],
        error_callback: Callable[[Text], Coroutine[Any, Any, None]],
    ) -> None:
        self.host = host
        self.port = port
        self.session = session
        self.open_callback = open_callback
        self.message_callback = message_callback
        self.close_callback = close_callback
        self.error_callback = error_callback

        self.socket: aiohttp.ClientWebSocketResponse = None
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.task = None

    async def connect(self):
        """Set up web socket connection"""
        try:
            self.socket = await self.session.ws_connect(f"ws://{self.host}:{self.port}", autoclose=False, autoping=True, heartbeat=60)
        except Exception as exc:
            raise WebSocketConnectionError() from exc
        self.task = self.loop.create_task(self._process_messages())
        self.task.add_done_callback(self._on_close)
        await self._on_open()

    async def disconnect(self):
        """Close web socket connection"""
        if self.socket is not None:
            await self.socket.close()
            self.socket = None
        if self.task is not None:
            self.task.cancel()
            self.task = None

    async def _on_open(self) -> None:
        if self.open_callback is not None:
            await self.open_callback()

    async def _process_messages(self):
        async for msg in self.socket:
            await self._on_message(msg)

    async def _on_message(self, message):
        try:
            if self.message_callback is not None:
                await self.message_callback(message.json())
        except:
            # printing stack trace
            traceback.print_exc()

    async def _on_error(self, error: Text = "Unspecified") -> None:
        if self.error_callback is not None:
            await self.error_callback(error)

    def _on_close(self, future="") -> None:
        self.socket = None
        if self.close_callback is not None:
            self.close_callback()

    async def send_message(self, message):
        """Send message to websocket"""
        if self.socket is None:
            raise WebSocketConnectionError()
        await self.socket.send_str(message)
