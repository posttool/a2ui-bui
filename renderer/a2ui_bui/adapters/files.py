# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Files: FileBrowser, on BUI's ``bui.components.FileBrowser`` (Blender's File
Browser: bookmarks, path bar, sortable Name / Date Modified / Size list,
execute bar).

The catalog's FileBrowser shows a listing the agent supplies (``entries`` for
``path``); BUI's browser reads a real folder. So the adapter mirrors the
listing into a private sandbox folder (folders, and empty sparse files with the
given sizes and dates) and points the browser there. Nothing outside the
sandbox is written, and the user's own bookmarks file is never read.

Mapping (``bui/spec.js``):

* ``path`` (two-way) <-> the sandbox folder; ``entries`` -> its contents.
* opening a folder writes ``path`` and fires ``{"op": "open", "name"}``; going
  up (BackSpace, the parent button, "..") fires ``{"op": "parent"}``.
* choosing a file (double-click, Return, the execute button) writes
  ``selected`` and fires ``{"op": "select", "name"}``; ``selected`` from the
  model fills the file-name field.

Known gaps (BUI's browser): ``view: "thumbnails"`` shows the list (the kit has
no thumbnail display); entry ``icon`` / ``color`` are ignored (the kit picks
icons from the extension, as Blender does); the path bar shows the sandbox
folder, and the Volumes / System panels list this machine's places (leaving the
sandbox snaps back to ``path``).
"""

from __future__ import annotations

import atexit
import datetime as _dt
import os
import re
import shutil
import tempfile

import bui.components as C

from .. import props as P
from .base import adapter, apply_common, common_kw

_SANDBOX: str | None = None


def _sandbox() -> str:
    global _SANDBOX
    if _SANDBOX is None:
        _SANDBOX = tempfile.mkdtemp(prefix="a2ui-files-")
        os.makedirs(os.path.join(_SANDBOX, "fs"))
        atexit.register(shutil.rmtree, _SANDBOX, True)
    return _SANDBOX


def _fs_root() -> str:
    return os.path.join(_sandbox(), "fs")


def _parts(path: str) -> list[str]:
    """Catalog path -> safe path components (no "", ".", "..")."""
    return [p for p in str(path or "").replace("\\", "/").split("/")
            if p and p not in (".", "..") and "\0" not in p]


def _local(path: str) -> str:
    return os.path.join(_fs_root(), *_parts(path))


def _catalog_path(local_dir: str, like: str) -> str | None:
    """Sandbox folder -> catalog path (keeps ``like``'s trailing slash); None
    when the folder is outside the sandbox."""
    root = os.path.realpath(_fs_root())
    d = os.path.realpath(local_dir.rstrip(os.sep) or os.sep)
    if d != root and not d.startswith(root + os.sep):
        return None
    rel = os.path.relpath(d, root)
    out = "/" if rel == "." else "/" + rel.replace(os.sep, "/")
    if like.endswith("/") and not out.endswith("/"):
        out += "/"
    return out


_UNITS = {"": 1, "b": 1, "k": 1e3, "kb": 1e3, "kib": 1024, "m": 1e6, "mb": 1e6, "mib": 1024 ** 2,
          "g": 1e9, "gb": 1e9, "gib": 1024 ** 3, "t": 1e12, "tb": 1e12, "tib": 1024 ** 4}


def _size(v) -> int:
    """Bytes from a number or a "48.2 MiB" / "2 KiB" / "300 B" string."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return max(0, int(v))
    m = re.match(r"\s*([\d.]+)\s*([a-zA-Z]*)", str(v or ""))
    if not m:
        return 0
    try:
        return int(float(m.group(1)) * _UNITS.get(m.group(2).lower(), 1))
    except ValueError:
        return 0


_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _mtime(v) -> float:
    """Seconds since the epoch from a number, an ISO date, or Blender-style
    "Today 09:12" / "Yesterday" / "Mon 18:03" (the last such day)."""
    now = _dt.datetime.now()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v or "").strip()
    if not s:
        return now.timestamp()
    try:
        return _dt.datetime.fromisoformat(s).timestamp()
    except ValueError:
        pass
    m = re.match(r"(?i)(today|yesterday|mon|tue|wed|thu|fri|sat|sun)\w*\s*(?:(\d{1,2}):(\d{2}))?", s)
    if not m:
        return now.timestamp()
    word = m.group(1).lower()
    back = 0 if word == "today" else 1 if word == "yesterday" else \
        ((now.weekday() - _DAYS.index(word[:3])) % 7 or 7)
    day = now - _dt.timedelta(days=back)
    hh, mm = (int(m.group(2)), int(m.group(3))) if m.group(2) else (12, 0)
    return day.replace(hour=min(hh, 23), minute=min(mm, 59), second=0, microsecond=0).timestamp()


def _mirror(path: str, entries) -> str:
    """Make the sandbox folder for ``path`` hold exactly ``entries``."""
    local = _local(path)
    os.makedirs(local, exist_ok=True)
    wanted = {}
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name", ""))
        if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
            continue
        wanted[name] = e
    for name in os.listdir(local):
        if name not in wanted:
            p = os.path.join(local, name)
            shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    for name, e in wanted.items():
        p = os.path.join(local, name)
        is_dir = str(e.get("type", "file")) == "dir"
        if is_dir != os.path.isdir(p) and os.path.lexists(p):
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        if is_dir:
            os.makedirs(p, exist_ok=True)
        else:
            with open(p, "wb") as fh:
                fh.truncate(_size(e.get("size")))  # sparse: no disk use
        t = _mtime(e.get("modified"))
        os.utime(p, (t, t))
    return local


class _Bridge:
    """Browser events -> data model writes and actions; ``quiet`` while the
    adapter itself moves the browser."""

    def __init__(self, view, node, fb):
        self.fb, self.quiet = fb, False
        self._node, self.path = node, P.get_str(node, "path")
        fb.on_change, fb.on_submit = self.folder_changed, self.submitted

    def show(self, node) -> None:
        """Mirror the node's listing and move the browser there (no actions)."""
        self._node = node
        self.path = P.get_str(node, "path")
        local = _mirror(self.path, P.get(node, "entries", []))
        self.quiet = True
        try:
            if os.path.realpath(self.fb.directory.rstrip(os.sep) or os.sep) != os.path.realpath(local):
                self.fb.directory = local
            else:
                self.fb.refresh()
            sel = P.get_str(node, "selected")
            if sel and sel != self.fb.file:
                self.fb.file = sel
        finally:
            self.quiet = False

    def folder_changed(self, directory: str) -> None:
        if self.quiet:
            return
        node = self._node
        new = _catalog_path(directory, self.path)
        if new is None:  # left the sandbox (a Volumes / System place): back to path
            self.show(node)
            return
        old_parts, new_parts = _parts(self.path), _parts(new)
        if len(new_parts) < len(old_parts) and old_parts[:len(new_parts)] == new_parts:
            ctx = {"op": "parent"}
        else:
            ctx = {"op": "open", "name": new_parts[-1] if new_parts else ""}
        self.path = new
        P.write(node, "path", new)
        P.fire(node, ctx)

    def submitted(self, paths: list) -> None:
        self.fb.set("state", 0)  # embedded: keep browsing after an answer
        if self.quiet or not paths:
            return
        node = self._node
        name = os.path.basename(paths[0].rstrip(os.sep))
        P.write(node, "selected", name)
        P.fire(node, {"op": "select", "name": name})


def _apply(view, node, fb, key, value) -> bool:
    if key in ("path", "entries", "selected"):
        bridge = getattr(fb, "_a2ui_bridge", None)
        if bridge is None:
            return False
        if key == "selected":
            bridge._node = node
            if value and str(value) != fb.file:
                bridge.quiet = True
                try:
                    fb.file = str(value)
                finally:
                    bridge.quiet = False
            return True
        bridge.show(node)
        return True
    return apply_common(fb, key, value)


@adapter("FileBrowser", live=("path", "entries", "selected"), apply=_apply)
def file_browser(view, node):
    fb = C.FileBrowser(_local(P.get_str(node, "path")), **common_kw(node))
    fb.set("bookmarks_file", os.path.join(_sandbox(), "bookmarks.txt"))
    bridge = _Bridge(view, node, fb)
    fb._a2ui_bridge = bridge
    bridge.show(node)
    return fb
