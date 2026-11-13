# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""AppRuntime: connects a BuiRenderer surface to a sandboxed Python worker
and the ADK builder agent fallback.

Flow on every A2UI action:
  1. If `main.py` registers a handler for `action.name`, run it in the sandboxed
     worker. Each `yield` or completion streams `updateDataModel` / `updateComponents`
     messages into `dispatch_ui(msgs)` and persists `state.json`.
  2. If there is no handler, or the handler raises / crashes, hand the action
     (plus traceback) to `AppAgent.handle(...)`, which answers immediately and
     writes/tests/accepts the missing or fixed handler, then reloads the worker.
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .model import AppRecord
from .sandbox import SandboxPolicy, select_sandbox

log = logging.getLogger("a2ui_bui.runtime")

SDK_DIR = Path(__file__).resolve().parent / "sdk"
WORKER_SCRIPT = Path(__file__).resolve().parent / "worker.py"


def _set_pointer(root: dict, pointer: str, value: Any) -> None:
    if pointer in ("", "/"):
        if isinstance(value, dict):
            root.clear()
            root.update(value)
        return
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.lstrip("/").split("/") if p != ""]
    if not parts:
        return
    cur: Any = root
    for seg in parts[:-1]:
        if isinstance(cur, list) and seg.isdigit():
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            if seg not in cur or not isinstance(cur[seg], (dict, list)):
                cur[seg] = {}
            cur = cur[seg]
        else:
            return
    last = parts[-1]
    if isinstance(cur, list) and last.isdigit():
        idx = int(last)
        if 0 <= idx < len(cur):
            cur[idx] = value
    elif isinstance(cur, dict):
        if value is None:
            cur.pop(last, None)
        else:
            cur[last] = value


def _patch_to_msg(patch: dict, surface_id: str = "main") -> dict:
    return {
        "version": "1.0",
        "updateDataModel": {
            "surfaceId": surface_id,
            "path": patch.get("path") or "/",
            "value": patch.get("value"),
        },
    }


def _call_host_model(prompt: str, schema: dict | None = None) -> Any:
    """Host-mediated LLM call for `app.agent.ask()`. API keys stay in the host."""
    import os
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    # Reuse server.py's key & model lookup if available.
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import server as demo_server

    models = [m for m in demo_server.load_models() if demo_server.load_key(m["provider"])]
    if not models:
        raise RuntimeError("No model API key configured on the host for app.agent.ask()")
    m = models[0]
    kwargs: dict[str, Any] = {
        "model": m["id"],
        "api_key": demo_server.load_key(m["provider"]),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        **m.get("params", {}),
    }
    if schema:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["messages"] = [
            {"role": "system", "content": f"Respond with JSON matching schema: {json.dumps(schema)}"},
            {"role": "user", "content": prompt},
        ]
    resp = litellm.completion(**kwargs)
    text = resp.choices[0].message.content or ""
    if schema:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


class AppRuntime:
    def __init__(
        self,
        app: AppRecord,
        *,
        dispatch_ui: Callable[[list[dict]], None] | None = None,
        get_data: Callable[[str], dict | None] | None = None,
        on_event: Callable[[dict], None] | None = None,
        sandbox_mode: str | None = None,
        agent_factory: Callable[[], Any] | None = None,
        llm_ask: Callable[[str, dict | None], Any] | None = None,
    ) -> None:
        self.app = app
        self.dispatch_ui = dispatch_ui or (lambda msgs: None)
        self.get_data = get_data or (lambda sid="main": self.app.load_state())
        self.on_event = on_event or (lambda ev: None)
        meta = app.meta()
        self.sandbox_mode = sandbox_mode or meta.get("sandbox") or "auto"
        self.sandbox = select_sandbox(self.sandbox_mode)
        self.policy = SandboxPolicy(mode=self.sandbox_mode)
        self._agent_factory = agent_factory
        self._agent = None
        self._llm_ask = llm_ask or _call_host_model

        self._proc = None
        self._handlers: set[str] = set()
        self._ticks: list[float] = []
        self._lock = threading.Lock()
        self._queue: "queue.Queue[tuple[str, Any, threading.Event | None]]" = queue.Queue()
        self._stopped = False
        self._thread = threading.Thread(target=self._loop, name=f"app-{app.id}", daemon=True)
        self._tick_thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread.start()
        if self.app.has_backend():
            self.reload_worker()

    def stop(self) -> None:
        self._stopped = True
        self._queue.put(("stop", None, None))
        with self._lock:
            self._stop_proc()

    def reload_worker(self) -> list[str]:
        """Start or restart the sandboxed worker process and return registered handlers."""
        ev = threading.Event()
        box: dict[str, Any] = {}
        self._queue.put(("reload", box, ev))
        ev.wait(timeout=15)
        if "error" in box:
            raise RuntimeError(box["error"])
        return box.get("handlers", [])

    def submit_action(self, payload: dict) -> None:
        """Queue an A2UI action payload (from BuiRenderer.on_action)."""
        self._queue.put(("action", payload, None))

    def handle_action_sync(self, payload: dict, timeout: float = 60.0) -> dict:
        """Run one action synchronously (for tests / CLI)."""
        ev = threading.Event()
        box: dict[str, Any] = {}
        self._queue.put(("action_sync", (payload, box), ev))
        if not ev.wait(timeout=timeout):
            raise TimeoutError("action timed out")
        return box

    @property
    def handlers(self) -> list[str]:
        return sorted(self._handlers)

    # -- worker process lifecycle ---------------------------------------------
    def _ensure_worker_script(self) -> Path:
        # Copy worker.py into sdk_dir if needed? Actually worker.py lives in apps/,
        # while sdk_dir is apps/sdk/. Pass worker.py inside sdk_dir or mount it.
        target = SDK_DIR / "worker.py"
        if not target.exists() or target.stat().st_mtime < WORKER_SCRIPT.stat().st_mtime:
            target.write_text(WORKER_SCRIPT.read_text())
        return target

    def _start_proc(self) -> None:
        self._stop_proc()
        if not self.app.has_backend():
            self._handlers = set()
            self._ticks = []
            return
        self._ensure_worker_script()
        self.app.ensure_dirs()
        py = "/usr/bin/python3" if self.sandbox.name == "bwrap" else sys.executable
        self._proc = self.sandbox.spawn(
            [py, "-I", "/sdk/worker.py" if self.sandbox.name == "bwrap" else str(SDK_DIR / "worker.py")],
            sdk_dir=SDK_DIR,
            backend_dir=self.app.backend_dir,
            storage_dir=self.app.storage_dir,
            policy=self.policy,
        )
        line = self._proc.stdout.readline()
        if not line:
            err = self._proc.stderr.read()
            self._stop_proc()
            raise RuntimeError(f"worker failed to start: {err.strip()}")
        hello = json.loads(line)
        if hello.get("error"):
            self._stop_proc()
            raise RuntimeError(hello["error"])
        self._handlers = set(hello.get("handlers") or [])
        self._ticks = list(hello.get("ticks") or [])
        self.on_event({"t": "handlers", "handlers": sorted(self._handlers), "sandbox": self.sandbox.name})
        if self._ticks and self._tick_thread is None:
            self._tick_thread = threading.Thread(target=self._tick_loop, name=f"ticks-{self.app.id}", daemon=True)
            self._tick_thread.start()

    def _stop_proc(self) -> None:
        p = self._proc
        self._proc = None
        if p is not None:
            try:
                if p.stdin:
                    p.stdin.write('{"op":"stop"}\n')
                    p.stdin.flush()
            except Exception:
                pass
            for stream in (p.stdin, p.stdout, p.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
            try:
                p.wait(timeout=1.5)
            except Exception:
                p.kill()
                p.wait(timeout=1.0)

    def _tick_loop(self) -> None:
        next_due = [time.monotonic() + sec for sec in self._ticks]
        while not self._stopped:
            time.sleep(0.25)
            if not self._ticks or self._stopped:
                continue
            now = time.monotonic()
            for i, sec in enumerate(list(self._ticks)):
                if i < len(next_due) and now >= next_due[i]:
                    next_due[i] = now + max(0.5, sec)
                    self._queue.put(("tick", i, None))
            while len(next_due) < len(self._ticks):
                next_due.append(now + self._ticks[len(next_due)])

    # -- main serial loop -----------------------------------------------------
    def _loop(self) -> None:
        while not self._stopped:
            kind, arg, done_ev = self._queue.get()
            if kind == "stop":
                break
            try:
                if kind == "reload":
                    try:
                        self._start_proc()
                        arg["handlers"] = sorted(self._handlers)
                    except Exception as e:
                        arg["error"] = str(e)
                    finally:
                        if done_ev:
                            done_ev.set()
                elif kind == "tick":
                    self._run_tick(int(arg))
                elif kind == "action":
                    self._run_action(arg)
                elif kind == "action_sync":
                    payload, box = arg
                    box.update(self._run_action(payload))
                    if done_ev:
                        done_ev.set()
            except Exception as e:
                log.exception("runtime loop error")
                if done_ev:
                    done_ev.set()
                self.on_event({"t": "error", "error": {"code": "RUNTIME_ERROR", "message": str(e)}})

    def _run_tick(self, idx: int) -> None:
        if self._proc is None or idx >= len(self._ticks):
            return
        data = self.get_data("main")
        if data is None:
            data = self.app.load_state()
        self._exec_worker({"op": "tick", "index": idx, "data": data}, data, "main")

    def _run_action(self, payload: dict) -> dict:
        action = payload.get("action", payload) if isinstance(payload, dict) else {}
        name = action.get("name") or ""
        context = action.get("context") or {}
        surface_id = action.get("surfaceId") or "main"
        data = self.get_data(surface_id)
        if data is None:
            data = self.app.load_state()
        else:
            data = json.loads(json.dumps(data))

        if self._proc is None and self.app.has_backend():
            try:
                self._start_proc()
            except Exception as e:
                return self._fallback_agent(action, data, surface_id, error=str(e))

        if name in self._handlers and self._proc is not None:
            res = self._exec_worker({"op": "action", "name": name, "context": context, "data": data}, data, surface_id)
            if res.get("ok"):
                entry = {"kind": "action", "name": name, "source": "code", "ms": res["ms"]}
                self.app.append_log(entry)
                self.on_event({"t": "action_handled", **entry})
                return {"source": "code", "ms": res["ms"], "ok": True}
            # Handler failed or crashed -> fall back to agent with the error.
            err = res.get("error") or "handler failed"
            self.app.append_log({"kind": "handler_error", "name": name, "error": err[:1000]})
            return self._fallback_agent(action, data, surface_id, error=err)

        return self._fallback_agent(action, data, surface_id, error=None)

    def _exec_worker(self, cmd: dict, data: dict, surface_id: str) -> dict:
        p = self._proc
        if p is None or p.stdin is None or p.stdout is None:
            return {"ok": False, "error": "worker not running"}
        try:
            p.stdin.write(json.dumps(cmd, separators=(",", ":")) + "\n")
            p.stdin.flush()
        except OSError as e:
            self._stop_proc()
            return {"ok": False, "error": f"worker pipe error: {e}"}

        while True:
            line = p.stdout.readline()
            if not line:
                err = p.stderr.read() if p.stderr else ""
                self._stop_proc()
                return {"ok": False, "error": f"worker exited unexpectedly: {err.strip()}"}
            msg = json.loads(line)
            if "patch" in msg:
                ui_msgs = [_patch_to_msg(pt, surface_id) for pt in msg["patch"]]
                for pt in msg["patch"]:
                    _set_pointer(data, pt.get("path") or "/", pt.get("value"))
                self.dispatch_ui(ui_msgs)
                self.app.save_state(data)
            elif "ui" in msg:
                self.dispatch_ui(msg["ui"])
            elif "log" in msg:
                self.app.append_log({"kind": "log", "text": msg["log"]})
                self.on_event({"t": "backend_log", "text": msg["log"]})
            elif msg.get("rpc") == "agent_ask":
                rid = msg["id"]
                try:
                    ans = self._handle_agent_ask(msg.get("prompt", ""), msg.get("schema"))
                    reply = {"op": "rpc_reply", "id": rid, "result": ans}
                except Exception as e:
                    reply = {"op": "rpc_reply", "id": rid, "error": str(e)}
                p.stdin.write(json.dumps(reply, separators=(",", ":")) + "\n")
                p.stdin.flush()
            elif msg.get("done"):
                self.app.save_state(data)
                return {"ok": True, "ms": msg.get("ms", 0)}
            elif "error" in msg:
                return {"ok": False, "error": msg["error"]}

    def _handle_agent_ask(self, prompt: str, schema: dict | None) -> Any:
        meta = self.app.meta()
        used = int(meta.get("runtime_calls_used", 0))
        limit = int(meta.get("max_runtime_calls", 25))
        if used >= limit:
            raise RuntimeError(f"app runtime LLM budget exhausted ({used}/{limit} calls)")
        meta["runtime_calls_used"] = used + 1
        self.app.save_meta(meta)
        self.app.append_log({"kind": "runtime_llm", "call": used + 1, "limit": limit, "prompt": prompt[:120]})
        return self._llm_ask(prompt, schema)

    def _get_agent(self):
        if self._agent is None:
            if self._agent_factory is not None:
                self._agent = self._agent_factory()
            else:
                from .agent import AppAgent
                self._agent = AppAgent()
        return self._agent

    def _fallback_agent(self, action: dict, data: dict, surface_id: str, error: str | None) -> dict:
        name = action.get("name") or ""
        t0 = time.monotonic()
        self.on_event({"t": "agent_status", "text": f"Agent handling {name}…"})
        try:
            agent = self._get_agent()
            res = agent.handle(
                self.app, action, data, surface_id=surface_id, error=error,
                dispatch_ui=self.dispatch_ui, sandbox=self.sandbox, policy=self.policy,
                on_status=lambda s: self.on_event({"t": "agent_status", "text": s}),
            )
            if res.get("code_updated"):
                try:
                    self._start_proc()
                except Exception as e:
                    log.warning("worker reload after agent edit failed: %s", e)
            ms = round((time.monotonic() - t0) * 1000, 1)
            entry = {"kind": "action", "name": name, "source": "agent", "ms": ms,
                     "summary": res.get("summary", "")}
            self.app.append_log(entry)
            self.on_event({"t": "action_handled", **entry})
            self.on_event({"t": "agent_status", "text": ""})
            return {"source": "agent", "ms": ms, "ok": True, **res}
        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000, 1)
            self.on_event({"t": "agent_status", "text": f"Agent failed: {e}"})
            self.app.append_log({"kind": "agent_error", "name": name, "error": str(e)[:500]})
            return {"source": "agent", "ms": ms, "ok": False, "error": str(e)}
