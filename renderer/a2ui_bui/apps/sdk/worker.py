# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sandboxed app backend worker (stdlib only, runs inside bwrap / seatbelt).

Reads JSON lines on stdin, writes JSON lines on stdout:
  host -> worker:
    {"op": "action", "name": "...", "context": {...}, "data": {...}}
    {"op": "tick", "index": 0, "data": {...}}
    {"op": "rpc_reply", "id": 1, "result": ..., "error": ...}
    {"op": "stop"}
  worker -> host:
    {"ready": true, "handlers": [...], "ticks": [sec, ...]}
    {"patch": [{"path": "...", "value": ...}]}
    {"ui": [a2ui_msg, ...]}
    {"log": "..."}
    {"rpc": "agent_ask", "id": 1, "prompt": "...", "schema": ...}
    {"done": true, "ms": 1.2}
    {"error": "traceback..."}
"""

from __future__ import annotations

import inspect
import itertools
import json
import os
import sys
import time
import traceback
from pathlib import Path

_RPC_IDS = itertools.count(1)


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _flush(app) -> None:
    patches = app._sink.drain_patches()
    if patches:
        _send({"patch": patches})
    ui = app._sink.drain_ui()
    if ui:
        _send({"ui": ui})


def _rpc(method: str, payload: dict):
    rid = next(_RPC_IDS)
    _send({"rpc": method, "id": rid, **payload})
    while True:
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("host closed pipe while waiting for rpc_reply")
        msg = json.loads(line)
        if msg.get("op") == "rpc_reply" and msg.get("id") == rid:
            if msg.get("error"):
                raise RuntimeError(msg["error"])
            return msg.get("result")
        if msg.get("op") == "stop":
            raise SystemExit(0)


def main() -> int:
    sdk_dir = str(Path(__file__).resolve().parent)
    backend_dir = os.environ.get("A2UI_APP_BACKEND", "/app/backend")
    for p in (sdk_dir, backend_dir):
        if p not in sys.path:
            sys.path.insert(0, p)

    from a2ui_app import TrackedDict, app

    app._log_fn = lambda m: _send({"log": m})
    app.agent._bind(_rpc)

    main_file = Path(backend_dir) / "main.py"
    if main_file.exists():
        try:
            import main as _user_main  # noqa: F401
        except Exception:
            _send({"error": traceback.format_exc(), "fatal": True})
            return 1

    _send({
        "ready": True,
        "handlers": sorted(app.handlers),
        "ticks": [sec for sec, _ in app.ticks],
    })

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            continue
        op = cmd.get("op")
        if op == "stop":
            break
        t0 = time.monotonic()
        try:
            data = TrackedDict(cmd.get("data") or {}, "", app._sink)
            if op == "action":
                name = cmd.get("name")
                fn = app.handlers.get(name)
                if fn is None:
                    _send({"error": f"no handler for {name!r}", "unhandled": True})
                    continue
                res = fn(cmd.get("context") or {}, data)
            elif op == "tick":
                idx = int(cmd.get("index", 0))
                if not (0 <= idx < len(app.ticks)):
                    _send({"done": True, "ms": 0.0})
                    continue
                _, fn = app.ticks[idx]
                res = fn(data)
            else:
                continue

            if inspect.isgenerator(res):
                for _ in res:
                    _flush(app)
            _flush(app)
            _send({"done": True, "ms": round((time.monotonic() - t0) * 1000, 2)})
        except Exception:
            _flush(app)
            _send({"error": traceback.format_exc()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
