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
from .const import GO2RTC_API_PORT, GO2RTC_API_URL, STREAM_SLEEP_SECONDS, STREAM_TIMEOUT_SECONDS

_LOGGER: logging.Logger = logging.getLogger(__package__)

class P2PStreamer:
    """Class to manage external stream provider and byte based ffmpeg streaming"""

    def __init__(self, camera) -> None:
        self.camera = camera
        self.retry = None
        self.stream_created = asyncio.Event()
        self.stream_ready = False
        self.generation = 0

    def new_stream(self):
        """A start is about to create the go2rtc stream again; called before the camera reports streaming"""
        self.generation += 1
        self.stream_created.clear()
        self.stream_ready = False

    async def wait_until_ready(self):
        """Wait until go2rtc has this start's push with media; its RTSP server answers 404 before that"""
        if self.stream_ready is True:
            return
        url = GO2RTC_API_URL.format(self.camera.config.rtsp_server_address, GO2RTC_API_PORT)
        url = f"{url}s"
        parameters = {"src": str(self.camera.serial_no)}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=STREAM_SLEEP_SECONDS * 4)) as session:
            while self.stream_ready is False:
                # a reply only counts for the start it was asked for: a new start replaces the stream
                generation = self.generation
                # the PUT replaces the stream, so a producer seen after it belongs to this start
                await self.stream_created.wait()
                try:
                    async with session.get(url, params=parameters) as response:
                        stream = await response.json(content_type=None) if response.status == 200 else None
                    # the tcp placeholder source has no medias; the push has them once go2rtc has read its first bytes
                    if generation == self.generation and any(producer.get("medias") for producer in stream["producers"]):
                        self.stream_ready = True
                        return
                except Exception as ex:  # pylint: disable=broad-except
                    # go2rtc unreachable, or a reply without a producer list
                    _LOGGER.debug(f"wait_until_ready - {ex}")
                await asyncio.sleep(STREAM_SLEEP_SECONDS)

    async def chunk_generator(self, queue, queue_name):
        retry_count = 0
        max_retry_count = int(STREAM_TIMEOUT_SECONDS / 0.1)
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

        parameters = {"name": str(self.camera.serial_no), "src": "tcp://127.0.0.1:65535"}
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
        generation = self.generation
        self.retry = None
        await self._create_stream_on_go2rtc()
        # an older start's PUT finishing late does not count for a newer start
        if generation == self.generation:
            self.stream_created.set()
        await asyncio.gather(
            #asyncio.to_thread(self._run, self.camera.audio_queue, "audio"),
            asyncio.to_thread(self._run, self.camera.video_queue, "video")
        )
