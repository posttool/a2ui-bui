# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Streamed host: BUI renders on the server, the browser shows the pixels.

One ``StreamHub`` owns a single render thread. All BUI calls (renderer,
widgets, rasters, theme, scale) happen on that thread, because BUI's kit keeps
process-wide state (theme, UI scale). Transport threads (server.py WebSocket
handlers) call ``hub.open()`` / ``session.post(cmd)`` and drain
``session.outbox``.

Client -> server commands (dicts):
  {"t":"open", "messages":[...], "width":900, "theme":"dark", "scale":1.25}   (via hub.open)
  {"t":"update", "messages":[...]}            more A2UI messages (streaming / agent answers)
  {"t":"reset", "messages":[...]}             start over with these messages
  {"t":"mouse", "k":"down|up|move|wheel", "x", "y", "b":1|3, "d":wheel delta, "mods":{shift,ctrl,alt}}
  {"t":"key", "char", "keysym", "mods", "up":bool}
  {"t":"width", "w":900}
  {"t":"theme", "name":"dark|light"}  {"t":"scale", "v":1.25}
Server -> client events:
  {"t":"size", "w", "h"}  {"t":"frame", "tiles":[{x,y,w,h,png(base64)}]}
  {"t":"cursor", "css"}   {"t":"action", "payload"}  {"t":"data", "data"}
  {"t":"error", "error":{code,message,surfaceId}}
"""

from __future__ import annotations

import base64
import itertools
import logging
import queue
import threading
import time

log = logging.getLogger("a2ui_bui.stream")

MIN_H, MAX_H = 120, 4000
FPS = 60


class Session:
    _ids = itertools.count(1)

    def __init__(self, hub: "StreamHub", opts: dict):
        self.id = next(self._ids)
        self.hub = hub
        self.opts = opts
        self.app_id: str | None = opts.get("app_id")
        self.outbox: "queue.Queue[dict | None]" = queue.Queue()
        self.closed = False
        # render-thread state
        self.renderer = None
        self.host = None
        self.theme = opts.get("theme") or "dark"
        self.scale = float(opts.get("scale") or 1.0)
        self.width = int(opts.get("width") or 900)
        self.height = 0
        self._data_dirty = True
        self._last_data = 0.0

    # transport side ------------------------------------------------------------------------
    def post(self, cmd: dict) -> None:
        if not self.closed:
            self.hub._cmds.put((self, cmd))

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.hub._cmds.put((self, {"t": "_close"}))
            self.outbox.put(None)

    def send(self, ev: dict) -> None:
        if not self.closed:
            self.outbox.put(ev)


class StreamHub:
    def __init__(self, sandbox_mode: str = "auto"):
        self._cmds: "queue.Queue[tuple[Session, dict]]" = queue.Queue()
        self.sessions: dict[int, Session] = {}
        self.runtimes: dict[str, object] = {}
        self._rt_lock = threading.Lock()
        self.sandbox_mode = sandbox_mode
        self._thread = threading.Thread(target=self._run, name="bui-render", daemon=True)
        self._globals = (None, None)  # (theme, scale) currently applied to the kit
        self._thread.start()

    def get_runtime(self, app_id: str):
        """Return (and start if needed) the single AppRuntime for ``app_id``."""
        with self._rt_lock:
            rt = self.runtimes.get(app_id)
            if rt is not None:
                return rt
            from ..apps import get_app
            from ..apps.runtime import AppRuntime

            rec = get_app(app_id)

            def dispatch_ui(msgs: list[dict]):
                for sess in list(self.sessions.values()):
                    if sess.app_id == app_id and not sess.closed:
                        sess.post({"t": "update", "messages": msgs})

            def get_data(sid: str = "main"):
                # Read from an attached session's renderer if present, else disk.
                for sess in list(self.sessions.values()):
                    if sess.app_id == app_id and sess.renderer is not None:
                        d = sess.renderer.data_model(sid)
                        if d is not None:
                            return d
                return rec.load_state()

            def on_event(ev: dict):
                for sess in list(self.sessions.values()):
                    if sess.app_id == app_id and not sess.closed:
                        sess.send({"t": "backend", "event": ev})

            rt = AppRuntime(
                rec,
                dispatch_ui=dispatch_ui,
                get_data=get_data,
                on_event=on_event,
                sandbox_mode=self.sandbox_mode,
            )
            rt.start()
            self.runtimes[app_id] = rt
            return rt

    def open(self, opts: dict) -> Session:
        s = Session(self, opts)
        self._cmds.put((s, {"t": "_open"}))
        return s

    # render thread -------------------------------------------------------------------------
    def _run(self):
        import bui  # noqa: F401 — BUI is only ever touched from this thread
        while True:
            timeout = 1.0 / FPS if self.sessions else 0.5
            try:
                s, cmd = self._cmds.get(timeout=timeout)
                batch = [(s, cmd)]
                while True:
                    try:
                        batch.append(self._cmds.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                batch = []
            for s, cmd in batch:
                try:
                    self._handle(s, cmd)
                except Exception as e:
                    log.exception("command %s failed", cmd.get("t"))
                    s.send({"t": "error", "error": {"code": "RENDERER_EXCEPTION", "message": str(e)}})
            for s in list(self.sessions.values()):
                try:
                    self._pump(s)
                except Exception as e:
                    log.exception("frame failed")
                    s.send({"t": "error", "error": {"code": "RENDERER_EXCEPTION", "message": str(e)}})

    def _apply_globals(self, s: Session, force=False) -> bool:
        """Switch the kit's global theme/scale to this session's; True if changed."""
        import bui
        import buipy
        if self._globals == (s.theme, s.scale) and not force:
            return False
        bui.set_theme(s.theme)
        buipy.kit_set_scale(float(s.scale))
        self._globals = (s.theme, s.scale)
        return True

    def _start(self, s: Session, messages):
        from ..renderer import BuiRenderer
        from .headless import HeadlessHost
        if s.host is not None:
            s.renderer.processor.dispose() if hasattr(s.renderer.processor, "dispose") else None
        runtime = self.get_runtime(s.app_id) if s.app_id else None

        def on_act(p):
            s.send({"t": "action", "payload": p})
            s._data_dirty = True
            if runtime is not None:
                runtime.submit_action(p)

        s.renderer = BuiRenderer(
            on_action=on_act,
            on_error=lambda e: s.send({"t": "error", "error": e}),
            on_change=lambda: setattr(s, "_data_dirty", True))
        if runtime is not None:
            s.renderer.storage_dir = runtime.app.storage_dir
        s.host = HeadlessHost(s.renderer, (s.width, MAX_H),
                              on_cursor=lambda css: s.send({"t": "cursor", "css": css}))
        s.height = 0
        if messages:
            s.renderer.process(messages)
        if runtime is not None:
            s.send({"t": "backend", "event": {"t": "handlers", "handlers": runtime.handlers,
                                              "sandbox": runtime.sandbox.name}})

    def _handle(self, s: Session, cmd: dict):
        t = cmd.get("t")
        if t == "_open":
            self.sessions[s.id] = s
            self._apply_globals(s)
            msgs = s.opts.get("messages") or []
            if s.app_id and not msgs:
                from ..apps import get_app
                msgs = get_app(s.app_id).messages_with_state()
            self._start(s, msgs)
            return
        if t == "_close":
            self.sessions.pop(s.id, None)
            s.host = s.renderer = None
            return
        if s.host is None:
            return
        h = s.host
        if self._apply_globals(s):
            h._dirty = True     # another session changed the kit globals: redraw fully
            s.height = 0
        if t == "update":
            s.renderer.process(cmd.get("messages") or [])
        elif t == "reset":
            self._start(s, cmd.get("messages") or [])
        elif t == "mouse":
            x, y, k = int(cmd.get("x", 0)), int(cmd.get("y", 0)), cmd.get("k")
            mods = cmd.get("mods") or {}
            b = int(cmd.get("b") or 1)
            if k == "down":
                h.press(x, y, mods, b)
            elif k == "up":
                h.release(x, y, mods, b)
            elif k == "move":
                h.motion(x, y, mods | ({"button1": True} if cmd.get("held") else {}))
            elif k == "wheel":
                h.wheel(x, y, float(cmd.get("d") or 0), mods)
        elif t == "key":
            if cmd.get("up"):
                h.key_release(cmd.get("keysym"), cmd.get("mods") or {})
            else:
                h.key(cmd.get("char") or "", cmd.get("keysym") or "", cmd.get("mods") or {})
        elif t == "width":
            s.width = max(200, int(cmd.get("w") or s.width))
            s.height = 0
            h._dirty = True
        elif t == "theme":
            s.theme = "light" if cmd.get("name") == "light" else "dark"
            self._apply_globals(s, force=True)
            s.height = 0
            h._dirty = True
        elif t == "scale":
            s.scale = max(0.5, min(3.0, float(cmd.get("v") or 1.0)))
            self._apply_globals(s, force=True)
            s.height = 0
            h._dirty = True
        elif t == "data":
            s._data_dirty = True

    def _pump(self, s: Session):
        h = s.host
        if h is None:
            return
        self._apply_globals(s)
        h.run_timers()
        if not h._dirty:
            self._push_data(s)
            return
        # Height follows the content (like the web window did); natural() is
        # layout only, so this costs nothing when the height is unchanged.
        nh = max(MIN_H, min(MAX_H, int(h.natural_size()[1]) + 2))
        if nh != s.height or h.size[0] != s.width:
            s.height = nh
            h.resize(s.width, nh)
            s.send({"t": "size", "w": s.width, "h": nh})
            tiles = h.frame(full=True)
        else:
            tiles = h.frame()
        if tiles:
            s.send({"t": "frame", "tiles": [
                {"x": t["x"], "y": t["y"], "w": t["w"], "h": t["h"],
                 "png": base64.b64encode(t["png"]).decode("ascii")} for t in tiles]})
        self._push_data(s)

    def _push_data(self, s: Session):
        now = time.monotonic()
        if s._data_dirty and now - s._last_data > 0.2 and s.renderer is not None:
            s._data_dirty = False
            s._last_data = now
            data = {sid: s.renderer.data_model(sid) for sid in s.renderer.views}
            if len(data) == 1:
                data = next(iter(data.values()))
            s.send({"t": "data", "data": data})
