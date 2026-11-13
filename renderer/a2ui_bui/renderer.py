# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""The A2UI renderer: ``a2ui_core`` state in, real BUI components out.

    messages ──► MessageProcessor ──► SurfaceGroupModel
                                         │ on_surface_created
                                         ▼
                                  SurfaceView (one per surface)
                                    NodeResolver ──► ComponentNode tree
                                         │ adapters (catalog type → bui.components)
                                         ▼
                                  BUI widget tree ──► host (native window | headless)

Everything protocol-shaped (parsing, validation, data model, bindings,
templates, functions, actions) is the official A2UI framework. This module only
maps resolved nodes onto BUI widgets and keeps them in sync.
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any, Callable

import bui  # noqa: F401  (loads buipy)
import bui.components as C
import buipy
from a2ui.core import Catalog, MessageProcessor, NodeResolver
from a2ui.core.processing.message_processor import MessageProcessorOptions

from . import compat  # noqa: F401  (a2ui-core spec workarounds)
from . import adapters  # noqa: F401  (registers every adapter)
from . import props as P
from .adapters.base import REGISTRY, apply_common

log = logging.getLogger("a2ui_bui")
# a2ui_core warns on every binding to a not-yet-present data path, which is
# normal while a surface streams in; surface them via the error channel instead.
warnings.filterwarnings("ignore", message=".*Preflight DataBinding Warning.*")

REPO = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO / "bui" / "catalog.json"
PROTOCOL_VERSION = "1.0"


def load_catalog(path: Path | str = CATALOG_PATH):
    return Catalog.from_json(json.loads(Path(path).read_text()))


class _Record:
    __slots__ = ("node", "widget", "subs", "snap", "struct")

    def __init__(self, node, widget, subs, snap, struct):
        self.node, self.widget, self.subs, self.snap, self.struct = node, widget, subs, snap, struct


class SurfaceView:
    """One A2UI surface rendered as a BUI widget tree."""

    def __init__(self, renderer: "BuiRenderer", surface):
        self.renderer = renderer
        self.surface = surface
        self.id = surface.id
        self.records: dict[str, _Record] = {}      # node.id -> record
        self.root_widget = None
        self.on_root: Callable[[Any], None] | None = None
        self.resolver = NodeResolver(surface, catalog=renderer.catalog_for(surface))
        self._root_sub = self.resolver.on_root_replaced.subscribe(self._mount_root)
        if self.resolver.root is not None:
            self._mount_root(self.resolver.root)

    # -- tree ------------------------------------------------------------------------
    def widget_for(self, node):
        rec = self.records.get(node.id)
        return rec.widget if rec is not None else None

    def build(self, node):
        old = self.records.pop(node.id, None)
        if old is not None:
            for s in old.subs:
                s.unsubscribe()
        ad = REGISTRY.get(node.type)
        try:
            if node.is_placeholder:
                widget = C.Label("…")
            elif ad is None:
                widget = C.Label(f"[Unknown component: {node.type}]")
                self.renderer.report("UNKNOWN_COMPONENT", f"No BUI adapter for {node.type!r}", self.id)
            else:
                widget = ad.create(self, node)
        except Exception as e:  # keep the surface alive; show the failure in place
            log.exception("adapter %s failed", node.type)
            self.renderer.report("RENDER_ERROR", f"{node.type}#{node.component_id}: {e}", self.id)
            widget = C.Label(f"[{node.type} error: {e}]")
        subs = [node.on_updated.subscribe(lambda _p, n=node: self._update(n)),
                node.on_destroyed.subscribe(lambda _p=None, n=node: self._destroyed(n))]
        skip = (ad.live + ad.children) if ad else ()
        placeholder = node.is_placeholder or ad is None
        self.records[node.id] = _Record(node, widget, subs,
                                        None if placeholder else P.snapshot(node, skip),
                                        None if placeholder else P.structure(node, skip))
        widget._a2ui_node = node.id
        return widget

    def _mount_root(self, node):
        self.root_widget = self.build(node) if node is not None else None
        if self.on_root is not None:
            self.on_root(self.root_widget)
        self.renderer.changed()

    def _destroyed(self, node):
        rec = self.records.pop(node.id, None)
        if rec is not None:
            for s in rec.subs:
                s.unsubscribe()

    def _update(self, node):
        rec = self.records.get(node.id)
        if rec is None:
            return
        ad = REGISTRY.get(node.type)
        if ad is None or node.is_placeholder:
            self._replace(rec, self.build(node))
            return
        skip = ad.live + ad.children
        snap = P.snapshot(node, skip)
        if snap != rec.snap or P.structure(node, skip) != rec.struct:
            self._replace(rec, self.build(node))
            self.renderer.changed()
            return
        w = rec.widget
        try:
            for k in ad.live:
                v = P.unwrap(node.props.get(k))
                if ad.apply is not None and ad.apply(self, node, w, k, v):
                    continue
                if not apply_common(w, k, v):
                    self._replace(rec, self.build(node))
                    self.renderer.changed()
                    return
            for k in ad.children:
                from .adapters.base import sync_children
                holder = ad.container(w) if ad.container else w
                sync_children(self, holder, P.children(node, k))
        except Exception as e:
            log.exception("update %s failed", node.type)
            self.renderer.report("RENDER_ERROR", f"{node.type}#{node.component_id}: {e}", self.id)
            self._replace(rec, self.build(node))
        self.renderer.changed()

    def _replace(self, rec, new):
        old = rec.widget
        if old is new:
            return
        parent = old.parent
        if old is self.root_widget or parent is None:
            if old is self.root_widget:
                self.root_widget = new
                if self.on_root is not None:
                    self.on_root(new)
            return
        idx = list(parent.children).index(old)
        buipy.KitNode.remove(parent, old)
        buipy.KitNode.add(parent, new, idx)

    def dispose(self):
        self._root_sub.unsubscribe()
        for rec in self.records.values():
            for s in rec.subs:
                s.unsubscribe()
        self.records.clear()
        self.resolver.dispose() if hasattr(self.resolver, "dispose") else None


class BuiRenderer:
    """Feed A2UI messages in; get BUI widget trees (one per surface) out.

    ``on_action(payload)`` receives client-to-server ``action`` messages,
    ``on_error(payload)`` renderer errors, ``on_surface(view)`` / ``on_surface_deleted(id)``
    surface lifecycle, ``on_change()`` "something needs a redraw"."""

    def __init__(self, catalog=None, *, on_action=None, on_error=None,
                 on_surface=None, on_surface_deleted=None, on_change=None):
        self.catalog = catalog or load_catalog()
        self.on_action = on_action
        self.on_error = on_error
        self.on_surface = on_surface
        self.on_surface_deleted = on_surface_deleted
        self.on_change = on_change
        self.views: dict[str, SurfaceView] = {}
        self._ctx = None
        self._binds: list[tuple[str, Callable]] = []
        self.storage_dir: Path | None = None
        self.actions: list[dict] = []
        self.errors: list[dict] = []
        self.processor = MessageProcessor(
            [self.catalog], action_handler=self._action,
            options=MessageProcessorOptions(error_handler=self._error))
        model = self.processor.model
        model.on_surface_created.subscribe(self._surface_created)
        model.on_surface_deleted.subscribe(self._surface_deleted)

    def catalog_for(self, surface):
        return self.catalog

    # -- host link ---------------------------------------------------------------------
    @property
    def ctx(self):
        """The host window's ``buipy.KitContext`` (popups, pie menus, hotkeys);
        None until a host attaches."""
        return self._ctx

    @ctx.setter
    def ctx(self, ctx):
        self._ctx = ctx
        if ctx is not None:
            for combo, fn in self._binds:
                ctx.bind(combo, fn)

    def bind(self, combo: str, fn: Callable) -> None:
        """Window hotkey; queued until a host attaches, replayed on every host."""
        self._binds.append((combo, fn))
        if self._ctx is not None:
            self._ctx.bind(combo, fn)

    # -- input ------------------------------------------------------------------------
    def process(self, messages) -> list[dict]:
        """Process A2UI messages (dicts, a JSON string, or JSON Lines).
        Returns the renderer error messages produced."""
        if isinstance(messages, (str, bytes)):
            messages = parse_jsonl(messages)
        if isinstance(messages, dict):
            messages = [messages]
        before = len(self.errors)
        for m in messages:
            m = normalize(m)
            try:
                self.processor.process_messages([m])
            except Exception as e:  # validation errors: report, keep going
                self._error({"code": "VALIDATION_FAILED", "message": str(e)[:2000],
                             "surfaceId": _surface_of(m)})
        return self.errors[before:]

    def data_model(self, surface_id: str):
        s = self.processor.model.get_surface(surface_id)
        if s is None:
            return None
        dm = s.data_model
        return dm.get("/") if hasattr(dm, "get") else None

    # -- callbacks ----------------------------------------------------------------------
    def _surface_created(self, surface):
        view = SurfaceView(self, surface)
        self.views[surface.id] = view
        if self.on_surface is not None:
            self.on_surface(view)

    def _surface_deleted(self, surface_id):
        sid = getattr(surface_id, "id", surface_id)
        view = self.views.pop(sid, None)
        if view is not None:
            view.dispose()
        if self.on_surface_deleted is not None:
            self.on_surface_deleted(sid)

    def _action(self, payload):
        # client-to-server message, as an A2UI v1.0 renderer sends it
        if isinstance(payload, dict) and "action" not in payload:
            payload = {"version": PROTOCOL_VERSION, "action": payload}
        self.actions.append(payload)
        if self.on_action is not None:
            self.on_action(payload)

    def _error(self, payload):
        self.errors.append(payload)
        log.warning("a2ui error: %s", payload)
        if self.on_error is not None:
            self.on_error(payload)

    def report(self, code, message, surface_id=None):
        self._error({"code": code, "message": message, "surfaceId": surface_id})

    def changed(self):
        if self.on_change is not None:
            self.on_change()


def normalize(m: dict) -> dict:
    """Accept the v1.0 RC wire tag ("v1.0") that older payloads carry."""
    if isinstance(m, dict) and m.get("version") in ("v1.0", "1.0.0"):
        m = {**m, "version": PROTOCOL_VERSION}
    return m


def parse_jsonl(text) -> list[dict]:
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _surface_of(m):
    if not isinstance(m, dict):
        return None
    for k in ("createSurface", "updateComponents", "updateDataModel", "deleteSurface"):
        if isinstance(m.get(k), dict):
            return m[k].get("surfaceId")
    return None
