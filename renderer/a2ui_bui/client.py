# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Consume server.py's live generation stream (POST /api/generate, SSE)."""

from __future__ import annotations

import json
import urllib.request


def stream_generation(base_url: str, prompt: str, emit, **extra) -> None:
    """Calls ``emit(message)`` for each A2UI message as it arrives."""
    body = json.dumps({"prompt": prompt, **extra}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                ev = json.loads(line[5:])
                if ev.get("type") == "message":
                    emit(ev["message"])
                elif ev.get("type") == "error":
                    emit(RuntimeError(ev.get("error")))
                elif ev.get("type") == "done":
                    return
    except Exception as e:
        emit(e)
