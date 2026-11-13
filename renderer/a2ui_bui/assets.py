# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve A2UI asset URLs (``assets/x.png``, ``/assets/x.png``, ``file://``)
to local files BUI can decode. Remote URLs are fetched once into a cache."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = [REPO]
CACHE = Path(os.environ.get("A2UI_BUI_CACHE", Path.home() / ".cache" / "a2ui_bui"))


def resolve(src: str | None, extra_roots: list[Path] | tuple[Path, ...] = ()) -> str | None:
    if not src:
        return None
    s = str(src)
    if s.startswith("storage://"):
        rel = s[len("storage://"):].lstrip("/")
        for root in extra_roots:
            if root:
                p = Path(root) / rel
                if p.exists():
                    return str(p)
        return None
    if s.startswith("file://"):
        p = Path(s[7:])
        return str(p) if p.exists() else None
    if s.startswith(("http://", "https://")):
        return _fetch(s)
    if s.startswith("data:"):
        return None
    rel = s.lstrip("/")
    for root in [*extra_roots, *ROOTS]:
        if root:
            p = Path(root) / rel
            if p.exists():
                return str(p)
    p = Path(s)
    return str(p) if p.is_absolute() and p.exists() else None


def _fetch(url: str) -> str | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1][:6] or ".bin"
    dest = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ext)
    if not dest.exists():
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                dest.write_bytes(r.read())
        except Exception:
            return None
    return str(dest)
