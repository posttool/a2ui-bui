# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal PNG encoder (stdlib zlib only) for BUI rasters."""

from __future__ import annotations

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_rgb(w: int, h: int, rgb: bytes, level: int = 3) -> bytes:
    """``rgb``: w*h*3 bytes, row-major."""
    stride = w * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, level))
            + _chunk(b"IEND", b""))


def from_ppm(ppm: bytes, level: int = 3) -> tuple[int, int, bytes]:
    """Binary P6 (as ``buipy.Raster.ppm``) -> (w, h, png)."""
    # header: b"P6\n<w> <h>\n255\n"
    parts, pos = [], 0
    while len(parts) < 4:
        while ppm[pos:pos + 1].isspace():
            pos += 1
        if ppm[pos:pos + 1] == b"#":
            pos = ppm.index(b"\n", pos) + 1
            continue
        end = pos
        while not ppm[end:end + 1].isspace():
            end += 1
        parts.append(ppm[pos:end])
        pos = end
    pos += 1
    w, h = int(parts[1]), int(parts[2])
    return w, h, encode_rgb(w, h, ppm[pos:pos + w * h * 3], level)
