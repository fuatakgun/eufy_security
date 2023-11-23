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
from .const import GO2RTC_API_PORT

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
                break

    async def write_bytes(self):
        url = f"http://{self.camera.config.rtsp_server_address}:{GO2RTC_API_PORT}/api/stream?dst={str(self.camera.serial_no)}"
        headers = {'Content-Type': 'application/octet-stream'}

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(url, data = self.chunk_generator(), headers=headers, timeout=aiohttp.ClientTimeout(total=None, connect=5))
                _LOGGER.debug(f"write_bytes - post response - {resp.status} - {await resp.text()}")

        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(f"write_bytes exception %s - traceback: %s", ex, traceback.format_exc())

        _LOGGER.debug("write_bytes - ended")

        # await self.stop()

    async def create_stream_on_go2rtc(self):
        parameters = {"name": str(self.camera.serial_no), "src": str(self.camera.serial_no)}
        url = f"http://{self.camera.config.rtsp_server_address}:{GO2RTC_API_PORT}/api/streams"
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
