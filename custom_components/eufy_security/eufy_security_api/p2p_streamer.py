""" Module to handle go2rtc interactions """
from __future__ import annotations

import asyncio
import logging
import socket
import json
from time import sleep
import traceback
import os
from .const import STREAM_TIMEOUT_SECONDS, STREAM_SLEEP_SECONDS

_LOGGER: logging.Logger = logging.getLogger(__package__)

FFMPEG_COMMAND = [
    "-timeout", "1000",
    "-analyzeduration", "{duration}",
    "-f", "{video_codec}",
    "-i",
    "tcp://localhost:{port}?listen=1",
    "-vcodec", "copy"
]
FFMPEG_OPTIONS = (
    " -hls_init_time 0"
    " -hls_time 1"
    " -hls_segment_type mpegts"
    " -hls_playlist_type event "
    " -hls_list_size 0"
    " -preset ultrafast"
    " -tune zerolatency"
    " -g 15"
    " -sc_threshold 0"
    " -fflags genpts+nobuffer+flush_packets"
    " -loglevel debug"
)


class P2PStreamer:
    """Class to manage external stream provider and byte based ffmpeg streaming"""

    def __init__(self, camera) -> None:
        self.camera = camera
        self.port = None

    def get_command(self):
        command = FFMPEG_COMMAND.copy()
        video_codec = "hevc" if self.camera.codec == "h265" else self.camera.codec

        command[command.index("-analyzeduration") + 1] = command[command.index("-analyzeduration") + 1].replace("{duration}", str(self.camera.config.ffmpeg_analyze_duration))
        command[command.index("-f") + 1] = command[command.index("-f") + 1].replace("{video_codec}", video_codec)
        command[command.index("-i") + 1] = command[command.index("-i") + 1].replace("{port}", str(self.port))
        return command

    def get_options(self):
        options = FFMPEG_OPTIONS
        if self.camera.config.generate_ffmpeg_logs is True:
            options = FFMPEG_OPTIONS + " -report"
        return options

    def get_output(self):
        return f"-f rtsp -rtsp_transport tcp {self.camera.stream_url}"

    async def set_port(self) -> int:
        """find a free port"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("localhost", 0))
            self.port = sock.getsockname()[1]

        await asyncio.sleep(STREAM_SLEEP_SECONDS)

    async def start_ffmpeg(self) -> bool:
        if await self.camera.ffmpeg.open(cmd=self.get_command(), input_source=None, extra_cmd=self.get_options(), output=self.get_output(), stderr_pipe=True, stdout_pipe=True) is False:
            return False

        await asyncio.sleep(STREAM_SLEEP_SECONDS)
        return True

    async def write_bytes(self):
        writer = None
        try:
            _, writer = await asyncio.open_connection("localhost", self.port)
            asyncio.get_event_loop().create_task(self.check_live_stream(writer))
            while self.ffmpeg_available:
                try:
                    item = await asyncio.wait_for(self.camera.video_queue.get(), timeout=2.5)
                    writer.write(bytearray(item))
                    await writer.drain()
                except TimeoutError as te:
                    _LOGGER.debug(f"Timeout Exception %s - traceback: %s", te, traceback.format_exc())
                    break
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(f"General Exception %s - traceback: %s", ex, traceback.format_exc())
        finally:
            if writer is not None:
                writer.close()

        _LOGGER.debug("p2p 7")

        await self.stop()

    async def check_live_stream(self, writer):
        return
        errored = 0
        while errored < 3:
            result = await self.camera.imagempeg.get_image(self.camera.stream_url)
            if result is None:
                _LOGGER.debug(f"check_live_stream - result is None - {result} - {errored}")
                errored = errored + 1
            else:
                if len(result) == 0:
                    _LOGGER.debug(f"check_live_stream - result is empty - {result} - {errored}")
                    errored = errored + 1
                else:
                    _LOGGER.debug(f"check_live_stream - no error - {len(result)} - {errored}")
                    errored = 0
        _LOGGER.debug(f"check_live_stream - error and close {errored}")
        writer.close()


    async def start(self):
        """start ffmpeg process"""
        await self.set_port()

        if await self.start_ffmpeg() is False:
            return False

        asyncio.get_event_loop().create_task(self.write_bytes())
    async def stop(self):
        if self.camera.ffmpeg is not None:
            try:
                await self.camera.ffmpeg.close(timeout=1)
            except:
                pass

        await self.camera.check_and_stop_livestream()

    @property
    def ffmpeg_available(self) -> bool:
        """True if ffmpeg exists and running"""
        return self.camera.ffmpeg is not None and self.camera.ffmpeg.is_running is True