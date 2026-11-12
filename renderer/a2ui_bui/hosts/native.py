# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native host: the surface in a real BUI window (X11 / Win32 / Cocoa), drawn
by BUI's own renderer. Messages arriving on other threads (a live generation
stream) are handed over through a queue polled on the UI thread."""

from __future__ import annotations

import queue

import bui.components as C
import buipy

from ..renderer import BuiRenderer, SurfaceView


class NativeHost:
    def __init__(self, renderer: BuiRenderer, *, title="A2UI × BUI", size=(900, 720)):
        self.renderer = renderer
        self.app = C.App(title, size, padding=0, spacing=0)
        renderer.ctx = self.app.ctx
        self.view: SurfaceView | None = None
        self._mounted = None
        self._queue: "queue.Queue | None" = None
        prev = renderer.on_surface
        renderer.on_surface = lambda v: (prev and prev(v), self._attach(v))
        for v in renderer.views.values():
            self._attach(v)

    def _attach(self, view):
        if self.view is not None:
            return
        self.view = view
        view.on_root = self._mount
        self._mount(view.root_widget)

    def _mount(self, widget):
        root = self.app.root
        if self._mounted is not None and self._mounted.parent is root:
            buipy.KitNode.remove(root, self._mounted)
        self._mounted = widget
        if widget is not None:
            buipy.KitNode.add(root, widget)
        if self.app.window is not None:
            self.app.window.request()

    def feed_queue(self, q: "queue.Queue"):
        """Messages (or lists of messages) put on ``q`` from any thread are
        processed on the UI thread."""
        self._queue = q

    def _poll(self):
        try:
            while True:
                item = self._queue.get_nowait()
                if isinstance(item, BaseException):
                    print("stream error:", item)
                    continue
                self.renderer.process(item)
        except queue.Empty:
            pass
        self.app.window.after(30, self._poll)

    def run(self):
        from bui import host
        self.app.open()
        if self._queue is not None:
            self.app.window.after(30, self._poll)
        host.run()
