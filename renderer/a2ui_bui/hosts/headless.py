# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless host: render a surface into a BUI raster, report damaged tiles as
PNGs, and accept pointer/keyboard input. Used for screenshots, tests and the
web stream (server.py -> viewport.js).

Not thread-safe: drive one HeadlessHost from one thread.
"""

from __future__ import annotations

import heapq
import time
from typing import Callable

import bui
import bui.components as C
import buipy

from .. import png
from ..renderer import BuiRenderer, SurfaceView

MODS = {"shift": 1, "ctrl": 2, "alt": 4, "button1": 8}
_CURSOR_CSS = {None: "default", "ew": "ew-resize", "ns": "ns-resize", "text": "text",
               "crosshair": "crosshair", "hand": "pointer", "move": "move", "none": "none"}


class HeadlessHost:
    def __init__(self, renderer: BuiRenderer, size=(420, 640), *, surface_id: str | None = None,
                 on_cursor: Callable[[str], None] | None = None):
        self.renderer = renderer
        self.size = tuple(int(x) for x in size)
        self.surface_id = surface_id
        self.app = C.App("a2ui", self.size)   # Blender region padding around the surface
        renderer.ctx = self.app.ctx   # window KitContext for adapters (PieMenu.show, hotkeys)
        self.view: SurfaceView | None = None
        self._mounted = None
        self._timers: list[tuple[float, int, int]] = []
        self._seq = 0
        self._dirty = True
        self._clip = ""
        self.cursor = "default"
        self.on_cursor = on_cursor
        self.app.ctx.set_host(request=self._request, cursor=self._set_cursor, warp=lambda x, y: None,
                              clipboard_get=lambda: self._clip, clipboard_set=self._set_clip,
                              schedule=self._schedule)
        prev = renderer.on_surface
        renderer.on_surface = lambda v: (prev and prev(v), self._attach(v))
        prev_del = renderer.on_surface_deleted
        renderer.on_surface_deleted = lambda sid: (prev_del and prev_del(sid), self._detach(sid))
        prev_change = renderer.on_change
        renderer.on_change = lambda: (prev_change and prev_change(), self._request())
        for v in renderer.views.values():
            self._attach(v)

    # -- surfaces ------------------------------------------------------------------------
    def _attach(self, view: SurfaceView):
        if self.surface_id is not None and view.id != self.surface_id:
            return
        if self.view is not None and self.surface_id is None:
            return  # first surface wins unless pinned
        self.view = view
        view.on_root = self._mount
        self._mount(view.root_widget)

    def _detach(self, sid):
        if self.view is not None and self.view.id == sid:
            self.view = None
            self._mount(None)

    def _mount(self, widget):
        root = self.app.root
        if self._mounted is not None and self._mounted.parent is root:
            buipy.KitNode.remove(root, self._mounted)
        self._mounted = widget
        if widget is not None:
            buipy.KitNode.add(root, widget)
        self._request()

    # -- host callbacks -----------------------------------------------------------------
    def _request(self):
        self._dirty = True

    def _set_cursor(self, cid):
        name = C.core.CURSORS[cid] if isinstance(cid, int) and 0 <= cid < len(C.core.CURSORS) else None
        css = _CURSOR_CSS.get(name, "default")
        if css != self.cursor:
            self.cursor = css
            if self.on_cursor:
                self.on_cursor(css)

    def _set_clip(self, text):
        self._clip = text or ""

    def _schedule(self, ms, timer_id):
        self._seq += 1
        heapq.heappush(self._timers, (time.monotonic() + ms / 1000.0, self._seq, timer_id))

    def run_timers(self) -> bool:
        now, fired = time.monotonic(), False
        while self._timers and self._timers[0][0] <= now:
            _, _, tid = heapq.heappop(self._timers)
            self.app.ctx.timer(tid)
            fired = True
        if fired:
            self._dirty = True
        return fired

    def next_timer_in(self) -> float | None:
        return max(0.0, self._timers[0][0] - time.monotonic()) if self._timers else None

    # -- rendering ------------------------------------------------------------------------
    def resize(self, w: int, h: int):
        self.size = (max(1, int(w)), max(1, int(h)))
        self.app.size = self.size
        self._dirty = True

    def frame(self, full: bool = False) -> list[dict]:
        """Render; return damaged tiles ``[{x, y, w, h, png}]`` (empty if clean)."""
        if not (self._dirty or full):
            return []
        self._dirty = False
        w, h = self.size
        r = self.app.render_raster(w, h, full=full)
        rects = [(0, 0, w, h)] if full else list(r.damage() or [])
        tiles = []
        for (x, y, rw, rh) in _merge(rects, w, h):
            if rw <= 0 or rh <= 0:
                continue
            _, _, data = png.from_ppm(r.ppm(x, y, rw, rh), level=1)
            tiles.append({"x": x, "y": y, "w": rw, "h": rh, "png": data})
        return tiles

    def screenshot(self) -> bytes:
        w, h = self.size
        r = self.app.render_raster(w, h, full=True)
        self._dirty = False
        return png.from_ppm(r.ppm(0, 0, w, h), level=6)[2]

    def natural_size(self):
        return self.app.root.natural() if self._mounted is not None else (0, 0)

    # -- input -----------------------------------------------------------------------------
    @staticmethod
    def mods(m) -> int:
        if isinstance(m, int):
            return m
        if isinstance(m, dict):
            return sum(bit for k, bit in MODS.items() if m.get(k))
        return 0

    def press(self, x, y, mods=0, button=1):
        if button == 3:
            self.app.context_menu(x, y, self.mods(mods))
        else:
            self.app.press(x, y, self.mods(mods) | MODS["button1"])
        self._dirty = True

    def release(self, x, y, mods=0, button=1):
        if button != 3:
            self.app.release(x, y, self.mods(mods))
        self._dirty = True

    def motion(self, x, y, mods=0):
        self.app.motion(x, y, self.mods(mods))
        self._dirty = True

    def wheel(self, x, y, delta, mods=0):
        """``delta`` in notches (+ up), possibly fractional (browser trackpads).
        BUI takes whole notches (+1 / -1 like its Tk host), so fractions
        accumulate until they add up to one."""
        self._wheel_acc = getattr(self, "_wheel_acc", 0.0) + float(delta)
        steps = int(self._wheel_acc)          # truncates toward zero
        if steps == 0:
            return
        self._wheel_acc -= steps
        step = 1 if steps > 0 else -1
        for _ in range(min(abs(steps), 10)):  # cap a huge fling
            self.app.wheel(int(x), int(y), step, self.mods(mods))
        self._dirty = True

    def key(self, char, keysym, mods=0):
        self.app.key(char or "", keysym or "", 0, self.mods(mods))
        self._dirty = True

    def key_release(self, keysym, mods=0):
        kr = getattr(self.app.ctx, "key_release", None)
        if kr is not None:
            kr(keysym or "", self.mods(mods))

    def set_theme(self, name: str):
        bui.set_theme(name)
        self._dirty = True


def _merge(rects, w, h, max_tiles=24):
    """Clamp to the raster; collapse to one bounding box when there are many."""
    out = []
    for (x, y, rw, rh) in rects:
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(w, int(x + rw)), min(h, int(y + rh))
        if x1 > x0 and y1 > y0:
            out.append((x0, y0, x1 - x0, y1 - y0))
    if len(out) > max_tiles:
        x0 = min(r[0] for r in out); y0 = min(r[1] for r in out)
        x1 = max(r[0] + r[2] for r in out); y1 = max(r[1] + r[3] for r in out)
        out = [(x0, y0, x1 - x0, y1 - y0)]
    return out
