# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal RFC 6455 WebSocket endpoint (stdlib) bridging a browser viewport to
a ``StreamHub`` session. Used by server.py:

    from a2ui_bui.hosts.ws import handle_websocket, HUB
    if path.startswith("/ws/surface"): return handle_websocket(self)   # BaseHTTPRequestHandler
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import socket
import struct
import threading

from .stream import StreamHub

log = logging.getLogger("a2ui_bui.ws")
GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_hub: StreamHub | None = None
_hub_lock = threading.Lock()


def hub() -> StreamHub:
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = StreamHub()
        return _hub


def _send_frame(wfile, lock, payload: bytes, opcode: int = 0x1) -> None:
    n = len(payload)
    if n < 126:
        head = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 65536:
        head = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    with lock:
        wfile.write(head + payload)
        wfile.flush()


def _read_exact(rfile, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = rfile.read(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def _read_message(rfile):
    """-> (opcode, payload) for one complete (possibly fragmented) message."""
    data, first_op = b"", None
    while True:
        b1, b2 = _read_exact(rfile, 2)
        fin, op = b1 & 0x80, b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", _read_exact(rfile, 2))[0]
        elif n == 127:
            n = struct.unpack("!Q", _read_exact(rfile, 8))[0]
        mask = _read_exact(rfile, 4) if b2 & 0x80 else b"\0\0\0\0"
        payload = bytearray(_read_exact(rfile, n))
        for i in range(n):
            payload[i] ^= mask[i & 3]
        if op >= 0x8:            # control frames may interleave
            return op, bytes(payload)
        if first_op is None:
            first_op = op
        data += bytes(payload)
        if fin:
            return first_op, data


def handle_websocket(handler) -> None:
    """Upgrade ``handler`` (http.server.BaseHTTPRequestHandler) and serve a
    session until the browser disconnects. Blocks the handler thread."""
    key = handler.headers.get("Sec-WebSocket-Key")
    if not key or "websocket" not in (handler.headers.get("Upgrade") or "").lower():
        handler.send_error(400, "expected a WebSocket upgrade")
        return
    accept = base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()
    handler.send_response(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    handler.end_headers()
    handler.wfile.flush()
    handler.close_connection = True
    try:
        handler.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass

    rfile, wfile, lock = handler.rfile, handler.wfile, threading.Lock()
    session = None

    def writer():
        while True:
            ev = session.outbox.get()
            if ev is None:
                return
            try:
                _send_frame(wfile, lock, json.dumps(ev, separators=(",", ":")).encode())
            except (OSError, ValueError):
                session.close()
                return

    try:
        while True:
            op, payload = _read_message(rfile)
            if op == 0x8:
                break
            if op == 0x9:
                _send_frame(wfile, lock, payload, 0xA)
                continue
            if op not in (0x1, 0x2):
                continue
            try:
                cmd = json.loads(payload)
            except ValueError:
                continue
            if session is None:
                if cmd.get("t") != "open":
                    continue
                session = hub().open(cmd)
                threading.Thread(target=writer, name=f"ws-out-{session.id}", daemon=True).start()
            else:
                session.post(cmd)
    except (ConnectionError, OSError):
        pass
    finally:
        if session is not None:
            session.close()
        try:
            _send_frame(wfile, lock, b"", 0x8)
        except Exception:
            pass
