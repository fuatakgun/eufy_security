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
        while retry_count < max_retry_count:
            try:
                item = queue.popleft()
                #_LOGGER.debug(f"chunk_generator {queue_name} yield data {retry_count} - {len(item)}")
                retry_count = 0
                yield item
            except IndexError:
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
                if resp is not None and resp.status is not None:
                    if resp.status == 500:
                        self.retry = self.retry or True
                self.retry = self.retry or False

            _LOGGER.debug("write_bytes - post ended - {self.retry}")
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as ex:
            # live stream probabaly stopped, handle peacefully
            _LOGGER.debug(f"write_bytes {queue_name} timeout/cancelled NO RETRY exception {ex} - traceback: {traceback.format_exc()}")
            self.retry = self.retry or False
        except aiohttp.client_exceptions.ServerDisconnectedError as ex:
            # connection to go2rtc server is broken, try again``
            _LOGGER.debug(f"write_bytes {queue_name} server_disconnected RETRY exception {ex} - traceback: {traceback.format_exc()}")
            self.retry = self.retry or True
        except Exception as ex:  # pylint: disable=broad-except
            # other exceptions, log the error
            _LOGGER.debug(f"write_bytes {queue_name} general exception NO RETRY {ex} - traceback: {traceback.format_exc()}")
            self.retry = self.retry or False

        _LOGGER.debug(f"write_bytes {queue_name} - ended with {self.retry}")

    async def _create_stream_on_go2rtc(self):
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

    def _run(self, queue, name):
        asyncio.run(self.write_bytes(queue, name))

    async def start(self):
        """start streaming thread"""
        # send API command to go2rtc to create a new stream
        self.retry = None
        await self._create_stream_on_go2rtc()
        await asyncio.gather(
            #asyncio.to_thread(self._run, self.camera.audio_queue, "audio"),
            asyncio.to_thread(self._run, self.camera.video_queue, "video")
        )
