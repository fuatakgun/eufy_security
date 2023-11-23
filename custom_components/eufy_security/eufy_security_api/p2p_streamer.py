""" Module to handle go2rtc interactions """
from __future__ import annotations

import asyncio
import logging
import socket
import json
from time import sleep
import traceback
import aiohttp
import os
from .const import GO2RTC_API_PORT, GO2RTC_API_URL

_LOGGER: logging.Logger = logging.getLogger(__package__)

class P2PStreamer:
    """Class to manage external stream provider and byte based ffmpeg streaming"""

    def __init__(self, camera) -> None:
        self.camera = camera

    async def chunk_generator(self):
        while True:
            try:
                item = await asyncio.wait_for(self.camera.video_queue.get(), timeout=2.5)
                _LOGGER.debug(f"chunk_generator yield data - {len(item)}")
                yield bytearray(item)
            except TimeoutError as te:
                _LOGGER.debug(f"chunk_generator timeout Exception %s - traceback: %s", te, traceback.format_exc())
                raise te

    async def write_bytes(self):
        url = GO2RTC_API_URL.format(self.camera.config.rtsp_server_address, GO2RTC_API_PORT)
        url = f"{url}?dst={str(self.camera.serial_no)}"

        retry = False
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(url, data = self.chunk_generator(), timeout=aiohttp.ClientTimeout(total=None, connect=5))
                _LOGGER.debug(f"write_bytes - post response - {resp.status} - {await resp.text()}")

        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as ex:
            # live stream probabaly stopped, handle peacefully
            _LOGGER.debug(f"write_bytes timeout/cancelled exception %s - traceback: %s", ex, traceback.format_exc())
        except aiohttp.client_exceptions.ServerDisconnectedError as ex:
            # connection to go2rtc server is broken, try again
            _LOGGER.debug(f"write_bytes server_disconnected exception %s - traceback: %s", ex, traceback.format_exc())
            retry = True
        except Exception as ex:  # pylint: disable=broad-except
            # other exceptions, log the error
            _LOGGER.debug(f"write_bytes general exception %s - traceback: %s", ex, traceback.format_exc())

        _LOGGER.debug("write_bytes - ended")

        await self.stop(retry)

    async def create_stream_on_go2rtc(self):
        parameters = {"name": str(self.camera.serial_no), "src": str(self.camera.serial_no)}
        url = GO2RTC_API_URL.format(self.camera.config.rtsp_server_address, GO2RTC_API_PORT)
        url = f"{url}s"
        async with aiohttp.ClientSession() as session:
            async with session.put(url, params=parameters) as response:
                result = response.status, await response.text()
                _LOGGER.debug(f"create_stream_on_go2rtc - put stream response {result}")

    async def start(self):
        """start streaming thread"""
        # send API command to go2rtc to create a new stream
        await self.create_stream_on_go2rtc()
        asyncio.get_event_loop().create_task(self.write_bytes())

    async def stop(self):
        await self.camera.check_and_stop_livestream()

    async def stop(self, retry: boolean):
        await self.camera.check_and_stop_livestream()
        await asyncio.sleep(5)
        if retry is True:
            await self.camera.start_livestream()
