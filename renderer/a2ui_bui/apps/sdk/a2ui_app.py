# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stdlib-only backend SDK for A2UI + BUI apps (runs inside the sandbox).

    from a2ui_app import app

    @app.on("task_add")
    def task_add(ctx, data):
        ...
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Callable


def _esc(seg: str) -> str:
    return str(seg).replace("~", "~0").replace("/", "~1")


def _plain(v: Any) -> Any:
    if isinstance(v, TrackedDict):
        return {k: _plain(val) for k, val in dict.items(v)}
    if isinstance(v, TrackedList):
        return [_plain(x) for x in list.__iter__(v)]
    if isinstance(v, dict):
        return {k: _plain(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


class _PatchSink:
    def __init__(self) -> None:
        self.patches: list[tuple[str, Any]] = []
        self.ui_msgs: list[dict] = []

    def record(self, path: str, value: Any) -> None:
        self.patches.append((path or "/", _plain(value)))

    def drain_patches(self) -> list[dict]:
        if not self.patches:
            return []
        # Coalesce repeated writes to the same path within one yield/turn, preserving order of last write.
        seen: dict[str, int] = {}
        out: list[dict] = []
        for path, val in self.patches:
            if path in seen:
                out[seen[path]]["value"] = val
            else:
                seen[path] = len(out)
                out.append({"path": path, "value": val})
        self.patches.clear()
        return out

    def drain_ui(self) -> list[dict]:
        if not self.ui_msgs:
            return []
        out = list(self.ui_msgs)
        self.ui_msgs.clear()
        return out


def _wrap(v: Any, path: str, sink: _PatchSink) -> Any:
    if isinstance(v, TrackedDict) or isinstance(v, TrackedList):
        return v
    if isinstance(v, dict):
        return TrackedDict(v, path, sink)
    if isinstance(v, list):
        return TrackedList(v, path, sink)
    return v


class TrackedDict(dict):
    def __init__(self, initial: dict, path: str, sink: _PatchSink) -> None:
        super().__init__()
        self._path = path
        self._sink = sink
        for k, v in initial.items():
            super().__setitem__(k, _wrap(v, f"{path}/{_esc(k)}", sink))

    def __setitem__(self, key: str, value: Any) -> None:
        child_path = f"{self._path}/{_esc(key)}"
        wrapped = _wrap(value, child_path, self._sink)
        super().__setitem__(key, wrapped)
        self._sink.record(child_path, wrapped)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._sink.record(f"{self._path}/{_esc(key)}", None)

    def pop(self, key: str, *default):
        if key in self:
            val = _plain(super().pop(key))
            self._sink.record(f"{self._path}/{_esc(key)}", None)
            return val
        if default:
            return default[0]
        raise KeyError(key)

    def update(self, other=(), **kwargs) -> None:
        items = dict(other, **kwargs)
        for k, v in items.items():
            self[k] = v

    def setdefault(self, key: str, default: Any = None):
        if key not in self:
            self[key] = default
        return self[key]

    def clear(self) -> None:
        super().clear()
        self._sink.record(self._path, {})

    def to_plain(self) -> dict:
        return _plain(self)


class TrackedList(list):
    def __init__(self, initial: list, path: str, sink: _PatchSink) -> None:
        super().__init__()
        self._path = path
        self._sink = sink
        for i, v in enumerate(initial):
            super().append(_wrap(v, f"{path}/{i}", sink))

    def _rebind(self) -> None:
        for i, v in enumerate(self):
            p = f"{self._path}/{i}"
            if isinstance(v, (TrackedDict, TrackedList)):
                self._repath(v, p)

    @staticmethod
    def _repath(node: Any, path: str) -> None:
        if isinstance(node, TrackedDict):
            node._path = path
            for k, v in dict.items(node):
                TrackedList._repath(v, f"{path}/{_esc(k)}")
        elif isinstance(node, TrackedList):
            node._path = path
            for i, v in enumerate(list.__iter__(node)):
                TrackedList._repath(v, f"{path}/{i}")

    def __setitem__(self, idx, value) -> None:
        if isinstance(idx, slice):
            super().__setitem__(idx, [_wrap(v, self._path, self._sink) for v in value])
            self._rebind()
            self._sink.record(self._path, self)
            return
        i = idx if idx >= 0 else len(self) + idx
        child_path = f"{self._path}/{i}"
        wrapped = _wrap(value, child_path, self._sink)
        super().__setitem__(idx, wrapped)
        self._sink.record(child_path, wrapped)

    def __delitem__(self, idx) -> None:
        super().__delitem__(idx)
        self._rebind()
        self._sink.record(self._path, self)

    def append(self, value: Any) -> None:
        wrapped = _wrap(value, f"{self._path}/{len(self)}", self._sink)
        super().append(wrapped)
        self._sink.record(self._path, self)

    def extend(self, values) -> None:
        for v in values:
            super().append(_wrap(v, f"{self._path}/{len(self)}", self._sink))
        self._sink.record(self._path, self)

    def insert(self, idx: int, value: Any) -> None:
        super().insert(idx, _wrap(value, self._path, self._sink))
        self._rebind()
        self._sink.record(self._path, self)

    def pop(self, idx: int = -1):
        val = _plain(super().pop(idx))
        self._rebind()
        self._sink.record(self._path, self)
        return val

    def remove(self, value: Any) -> None:
        super().remove(value)
        self._rebind()
        self._sink.record(self._path, self)

    def clear(self) -> None:
        super().clear()
        self._sink.record(self._path, self)

    def sort(self, *, key=None, reverse: bool = False) -> None:
        super().sort(key=key, reverse=reverse)
        self._rebind()
        self._sink.record(self._path, self)


class _Storage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, rel: str) -> Path:
        p = (self.root / rel.lstrip("/")).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError(f"storage path escapes sandbox storage: {rel!r}")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def exists(self, rel: str) -> bool:
        try:
            return self.path(rel).exists()
        except PermissionError:
            return False

    def listdir(self, rel: str = "") -> list[str]:
        p = self.path(rel) if rel else self.root
        return sorted(x.name for x in p.iterdir()) if p.is_dir() else []

    def read_text(self, rel: str, default: str = "") -> str:
        p = self.path(rel)
        return p.read_text() if p.exists() else default

    def write_text(self, rel: str, text: str) -> None:
        self.path(rel).write_text(text)

    def read_json(self, rel: str, default: Any = None) -> Any:
        p = self.path(rel)
        return json.loads(p.read_text()) if p.exists() else default

    def write_json(self, rel: str, obj: Any) -> None:
        p = self.path(rel)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2))
        tmp.replace(p)


class _DB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        return self.conn.executescript(sql)

    def query(self, sql: str, params=()) -> list[dict]:
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def commit(self) -> None:
        if self._conn is not None and self._conn.in_transaction:
            self._conn.commit()


class _UI:
    def __init__(self, sink: _PatchSink) -> None:
        self._sink = sink

    def update(self, components: list[dict], surface_id: str = "main") -> None:
        self._sink.ui_msgs.append({
            "version": "1.0",
            "updateComponents": {"surfaceId": surface_id, "components": components},
        })

    def set(self, path: str, value: Any, surface_id: str = "main") -> None:
        self._sink.ui_msgs.append({
            "version": "1.0",
            "updateDataModel": {"surfaceId": surface_id, "path": path, "value": value},
        })

    def replace(self, messages: list[dict]) -> None:
        self._sink.ui_msgs.extend(messages)


class _AgentBridge:
    def __init__(self) -> None:
        self._rpc: Callable[[str, dict], Any] | None = None

    def _bind(self, fn: Callable[[str, dict], Any]) -> None:
        self._rpc = fn

    def ask(self, prompt: str, schema: dict | None = None) -> Any:
        if self._rpc is None:
            raise RuntimeError("app.agent.ask() is only available inside the app runtime")
        return self._rpc("agent_ask", {"prompt": str(prompt), "schema": schema})


class A2uiApp:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable] = {}
        self.ticks: list[tuple[float, Callable]] = []
        self._sink = _PatchSink()
        self._log_fn: Callable[[str], None] = lambda msg: None
        storage_root = Path(os.environ.get("A2UI_APP_STORAGE", "/app/storage"))
        self.storage = _Storage(storage_root)
        self.db = _DB(storage_root / "app.db")
        self.ui = _UI(self._sink)
        self.agent = _AgentBridge()

    def on(self, event_name: str):
        def deco(fn: Callable):
            self.handlers[event_name] = fn
            return fn
        return deco

    def every(self, seconds: float):
        def deco(fn: Callable):
            self.ticks.append((max(0.2, float(seconds)), fn))
            return fn
        return deco

    def log(self, message: Any) -> None:
        self._log_fn(str(message))


app = A2uiApp()
