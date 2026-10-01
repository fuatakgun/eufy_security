"""Repair event images delivered in eufy's v2_eufysecurity thumbnail format.

Since ~05/2026 eufy delivers event thumbnails (cloud pic_url as well as images
stored on the HomeBase) as "v2_eufysecurity" blobs. eufy-security-client 4.1.x
rebuilds them by splicing a fixed 288x176 4:2:0 header with quality-85
quantization tables in front of the (plaintext) scan data. The actual scan data is
usually 640x360 and much more heavily compressed, so the result is a grey,
striped image (see issue #1471).

This module
  1. recovers the real geometry by counting the Huffman-coded blocks in the scan
     and matching the MCU count against known eufy resolutions, and
  2. estimates the compression level: the lowest standard libjpeg quality whose
     decode does not clip a noticeable share of pixels.

Images without the library's spliced quality-85 header (i.e. regular JPEGs) are
returned unchanged, as is anything that cannot be repaired.
"""

from __future__ import annotations

import io
import logging

_LOGGER = logging.getLogger(__name__)

_STD_L = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
_STD_C = [17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99, 24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99] + [99] * 32
_ZZ = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]

# MCU count (4:2:0, 16x16 MCUs) -> (width, height); size ladder taken from
# eufy-security-client's decodeImageV2 (no two sizes share an MCU count)
_GEOMETRIES = {
    (w + 15) // 16 * ((h + 15) // 16): (w, h)
    for w, h in [
        (160, 90), (240, 135), (256, 144), (288, 176), (320, 180), (384, 216), (400, 225), (480, 270),
        (512, 288), (576, 324), (640, 360), (704, 396), (768, 432), (848, 480), (960, 540), (1024, 576),
        (1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (176, 144), (320, 240), (352, 288),
        (480, 360), (640, 480), (800, 600), (1024, 768), (1280, 960),
    ]
}
# Header that eufy-security-client splices in front of v2 scan data: 288x176, quality 85
_SPLICE_SIZE = (176).to_bytes(2, "big") + (288).to_bytes(2, "big")
_QUALITIES = [50, 45, 40, 35, 30, 25, 20, 15, 10]
_MAX_CLIP = 0.003

_cache: dict[int, bytes] = {}


def _qtable(base: list[int], quality: int) -> bytes:
    scale = 5000 // quality if quality < 50 else 200 - 2 * quality
    return bytes(min(255, max(1, (base[_ZZ[i]] * scale + 50) // 100)) for i in range(64))


def _segments(data: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    segs, i = [], 2
    while True:
        marker = data[i + 1]
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        segs.append((marker, data[i : i + 2 + length]))
        i += 2 + length
        if marker == 0xDA:
            return segs, data[i:]


def _huffman(seg: bytes) -> dict[int, dict[tuple[int, int], int]]:
    tables, p = {}, 4
    while p < len(seg):
        tc_th, counts = seg[p], seg[p + 1 : p + 17]
        values = seg[p + 17 : p + 17 + sum(counts)]
        p += 17 + sum(counts)
        code, k, table = 0, 0, {}
        for length in range(16):
            for _ in range(counts[length]):
                table[(length + 1, code)] = values[k]
                k += 1
                code += 1
            code <<= 1
        tables[tc_th] = table
    return tables


def _bits(scan: bytes):
    i = 0
    while i < len(scan):
        byte = scan[i]
        if byte == 0xFF:
            nxt = scan[i + 1] if i + 1 < len(scan) else 0xD9
            if nxt == 0x00:
                i += 1
            elif 0xD0 <= nxt <= 0xD7:
                i += 2
                continue
            else:
                return
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1
        i += 1


def _count_blocks(tables, scan: bytes) -> int:
    """Count the 8x8 blocks in the scan (4:2:0 order: Y Y Y Y Cb Cr)."""
    pattern = (0, 0, 0, 0, 1, 2)
    bits = _bits(scan)

    def decode(table):
        code = 0
        for length in range(1, 17):
            code = (code << 1) | next(bits)
            if (length, code) in table:
                return table[(length, code)]
        raise ValueError

    blocks = 0
    try:
        while True:
            chroma = pattern[blocks % 6] != 0
            dc, ac = tables[0x01 if chroma else 0x00], tables[0x11 if chroma else 0x10]
            for _ in range(decode(dc)):
                next(bits)
            k = 1
            while k < 64:
                rs = decode(ac)
                run, size = rs >> 4, rs & 15
                if size == 0:
                    if run == 15:
                        k += 16
                        continue
                    break
                k += run + 1
                for _ in range(size):
                    next(bits)
            blocks += 1
    except (StopIteration, ValueError):
        return blocks


def _rebuild(segs, scan: bytes, size: tuple[int, int], quality: int) -> bytes:
    out = bytearray(b"\xff\xd8")
    for marker, seg in segs:
        if marker == 0xDB:
            seg = seg[:5] + _qtable(_STD_L if (seg[4] & 15) == 0 else _STD_C, quality)
        elif marker == 0xC0:
            seg = bytearray(seg)
            seg[5:7] = size[1].to_bytes(2, "big")
            seg[7:9] = size[0].to_bytes(2, "big")
        out += seg
    return bytes(out + scan)


def fix_image(data: bytes) -> bytes:
    """Return the repaired JPEG, or the input unchanged if there is nothing to repair."""
    data = bytes(data)
    key = hash(data)
    if key in _cache:
        return _cache[key]
    try:
        segs, scan = _segments(data)
        dqt = next(seg for marker, seg in segs if marker == 0xDB)
        sof = next(seg for marker, seg in segs if marker == 0xC0)
        if dqt[5:69] != _qtable(_STD_L, 85) or sof[5:9] != _SPLICE_SIZE:
            return data  # not a v2 image spliced by eufy-security-client

        tables = {}
        for marker, seg in segs:
            if marker == 0xC4:
                tables.update(_huffman(seg))
        blocks = _count_blocks(tables, scan)
        size = _GEOMETRIES.get(blocks // 6) if blocks % 6 == 0 else None
        if size is None:
            _LOGGER.debug("v2 image: unknown geometry (%s blocks), left unchanged", blocks)
            return data

        import numpy as np  # noqa: PLC0415 - only needed in the executor
        from PIL import Image  # noqa: PLC0415

        result = _rebuild(segs, scan, size, _QUALITIES[0])
        for quality in _QUALITIES:
            candidate = _rebuild(segs, scan, size, quality)
            gray = np.asarray(Image.open(io.BytesIO(candidate)).convert("L"))
            if ((gray <= 1) | (gray >= 254)).mean() > _MAX_CLIP:
                break
            result = candidate
        _LOGGER.debug("v2 image repaired: %sx%s", *size)
    except Exception:  # noqa: BLE001 - better the original image than none
        _LOGGER.debug("v2 image could not be repaired", exc_info=True)
        result = data

    if len(_cache) > 32:
        _cache.clear()
    _cache[key] = result
    return result
