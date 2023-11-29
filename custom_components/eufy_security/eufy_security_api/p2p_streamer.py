""" Module to handle go2rtc interactions """
from __future__ import annotations

import asyncio
import logging
import socket
import threading
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
        self.retry = None

    async def chunk_generator(self, queue, queue_name):
        retry_count = 0
        max_retry_count = 10
        try:
            await asyncio.wait_for(self.camera.p2p_started_event.wait(), 5)
        except asyncio.TimeoutError as te:
            _LOGGER.debug(f"chunk_generator {queue_name} - event did not receive in timeout")
            raise te

        while retry_count < max_retry_count:
            try:
                item = queue.popleft()
                _LOGGER.debug(f"chunk_generator {queue_name} yield data {retry_count} - {len(item)}")
                retry_count = 0
                yield item
            except IndexError as qe:
                retry_count = retry_count + 1
                await asyncio.sleep(0.1)

    async def write_bytes(self, queue, queue_name):
        url = GO2RTC_API_URL.format(self.camera.config.rtsp_server_address, GO2RTC_API_PORT)
        url = f"{url}?dst={str(self.camera.serial_no)}"

        self.retry = None
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(url, data = self.chunk_generator(queue, queue_name), timeout=aiohttp.ClientTimeout(total=None, connect=5))
                _LOGGER.debug(f"write_bytes {queue_name} - post response - {resp.status} - {await resp.text()}")
            _LOGGER.debug("write_bytes - post ended - no retry")
            self.retry = False
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as ex:
            # live stream probabaly stopped, handle peacefully
            _LOGGER.debug(f"write_bytes {queue_name} timeout/cancelled no retry exception {ex} - traceback: {traceback.format_exc()}")
            self.retry = False
        except aiohttp.client_exceptions.ServerDisconnectedError as ex:
            # connection to go2rtc server is broken, try again``
            _LOGGER.debug(f"write_bytes {queue_name} server_disconnected retry exception {ex} - traceback: {traceback.format_exc()}")
            self.retry = True
        except Exception as ex:  # pylint: disable=broad-except
            # other exceptions, log the error
            _LOGGER.debug(f"write_bytes {queue_name} general exception no retry {ex} - traceback: {traceback.format_exc()}")
            self.retry = False

        _LOGGER.debug("write_bytes {queue_name} - ended")

    async def create_stream_on_go2rtc(self):
        parameters = {"name": str(self.camera.serial_no)}
        url = GO2RTC_API_URL.format(self.camera.config.rtsp_server_address, GO2RTC_API_PORT)
        url = f"{url}s"
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, params=parameters) as response:
                result = response.status, await response.text()
                _LOGGER.debug(f"create_stream_on_go2rtc - delete stream response {result}")

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
        await asyncio.gather(
            self.write_bytes(self.camera.audio_queue, "audio"),
            self.write_bytes(self.camera.video_queue, "video")
        )
