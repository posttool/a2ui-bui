# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""ADK tools for the app builder agent, scoped strictly to one AppRecord."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from ...renderer import BuiRenderer, load_catalog
from ..model import AppRecord
from ..runtime import SDK_DIR, WORKER_SCRIPT, _patch_to_msg, _set_pointer
from ..sandbox import Sandbox, SandboxPolicy, select_sandbox

WRITABLE = {"backend/main.py", "backend/test_main.py"}
READABLE = WRITABLE | {"ui.jsonl", "state.json", "app.json"}


def _ensure_worker() -> None:
    target = SDK_DIR / "worker.py"
    if not target.exists() or target.stat().st_mtime < WORKER_SCRIPT.stat().st_mtime:
        target.write_text(WORKER_SCRIPT.read_text())


def run_app_tests(app: AppRecord, sandbox: Sandbox | None = None, policy: SandboxPolicy | None = None) -> dict:
    """Run backend/test_main.py inside the sandbox against a scratch storage dir."""
    if not app.test_py.exists():
        return {"ok": False, "error": "backend/test_main.py does not exist"}
    _ensure_worker()
    sb = sandbox or select_sandbox(app.meta().get("sandbox") or "auto")
    pol = policy or SandboxPolicy(cpu_seconds=15, mode=sb.name)
    py = "/usr/bin/python3" if sb.name == "bwrap" else sys.executable
    sdk_p = "/sdk" if sb.name == "bwrap" else str(SDK_DIR)
    app_p = "/app" if sb.name == "bwrap" else str(app.root)
    back_p = "/app/backend" if sb.name == "bwrap" else str(app.backend_dir)
    runner_code = (
        f"import sys, unittest; sys.path[:0] = [{sdk_p!r}, {back_p!r}, {app_p!r}]; "
        f"res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover({back_p!r}, pattern='test_*.py')); "
        "sys.exit(0 if res.wasSuccessful() else 1)"
    )
    with tempfile.TemporaryDirectory() as tmp_storage:
        proc = sb.run(
            [py, "-I", "-c", runner_code],
            sdk_dir=SDK_DIR,
            backend_dir=app.backend_dir,
            storage_dir=Path(tmp_storage),
            policy=pol,
            timeout=20.0,
        )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "output": out[-4000:]}


def try_app_action(
    app: AppRecord,
    name: str,
    context: dict | None = None,
    state: dict | None = None,
    sandbox: Sandbox | None = None,
    policy: SandboxPolicy | None = None,
) -> dict:
    """Run one action in a scratch sandbox against a copy of state.json / storage."""
    if not app.has_backend():
        return {"ok": False, "error": "backend/main.py is empty"}
    _ensure_worker()
    sb = sandbox or select_sandbox(app.meta().get("sandbox") or "auto")
    pol = policy or SandboxPolicy(cpu_seconds=15, mode=sb.name)
    py = "/usr/bin/python3" if sb.name == "bwrap" else sys.executable
    data = json.loads(json.dumps(state if state is not None else app.load_state()))
    with tempfile.TemporaryDirectory() as tmp_storage:
        sp = Path(tmp_storage)
        if app.storage_dir.exists():
            for item in app.storage_dir.iterdir():
                dest = sp / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        worker_arg = "/sdk/worker.py" if sb.name == "bwrap" else str(SDK_DIR / "worker.py")
        p = sb.spawn([py, "-I", worker_arg], sdk_dir=SDK_DIR, backend_dir=app.backend_dir,
                     storage_dir=sp, policy=pol)
        try:
            hello_line = p.stdout.readline()
            if not hello_line:
                return {"ok": False, "error": f"worker failed to start: {p.stderr.read()}"}
            hello = json.loads(hello_line)
            if hello.get("error"):
                return {"ok": False, "error": hello["error"]}
            if name not in (hello.get("handlers") or []):
                return {"ok": False, "error": f"no handler registered for {name!r}; registered: {hello.get('handlers')}"}
            cmd = {"op": "action", "name": name, "context": context or {}, "data": data}
            p.stdin.write(json.dumps(cmd) + "\n")
            p.stdin.flush()
            patches, ui_msgs = [], []
            while True:
                ln = p.stdout.readline()
                if not ln:
                    return {"ok": False, "error": f"worker exited: {p.stderr.read()}"}
                msg = json.loads(ln)
                if "patch" in msg:
                    patches.extend(msg["patch"])
                    for pt in msg["patch"]:
                        _set_pointer(data, pt.get("path") or "/", pt.get("value"))
                elif "ui" in msg:
                    ui_msgs.extend(msg["ui"])
                elif msg.get("rpc") == "agent_ask":
                    p.stdin.write(json.dumps({"op": "rpc_reply", "id": msg["id"], "result": "[dry-run response]"}) + "\n")
                    p.stdin.flush()
                elif msg.get("done"):
                    break
                elif "error" in msg:
                    return {"ok": False, "error": msg["error"]}
        finally:
            try:
                if p.stdin:
                    p.stdin.write('{"op":"stop"}\n')
                    p.stdin.flush()
                p.wait(timeout=2)
            except Exception:
                p.kill()
    return {"ok": True, "patches": patches, "ui": ui_msgs, "handlers": hello.get("handlers")}


def validate_a2ui_messages(messages: list[dict]) -> list[str]:
    """Validate proposed A2UI messages against the BUI catalog using a2ui_core."""
    r = BuiRenderer(catalog=load_catalog())
    errs = r.process(messages)
    return [f"{e.get('code')}: {e.get('message')}" for e in errs]


def make_tools(
    app: AppRecord,
    *,
    sandbox: Sandbox,
    policy: SandboxPolicy,
    surface_id: str = "main",
    dispatch_ui: Callable[[list[dict]], None] | None = None,
    state_box: dict | None = None,
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[Callable], dict[str, Any]]:
    """Build the ADK tool callables and a mutable result tracker."""
    tracker: dict[str, Any] = {
        "written": set(),
        "tests_passed": False,
        "summary": "",
        "finished": False,
        "ui_sent": False,
    }

    def _status(msg: str) -> None:
        if on_status:
            on_status(msg)

    def list_actions() -> dict:
        """Return all declared A2UI action events from ui.jsonl (name, component, context)."""
        actions = app.declared_actions()
        names = [a.get("name", "") for a in actions if a.get("name")]
        preview = ", ".join(names[:6]) + ("…" if len(names) > 6 else "")
        _status(f"Inspected UI: {len(actions)} action(s)" + (f" ({preview})" if preview else ""))
        return {"actions": actions}

    def read_file(path: str) -> dict:
        """Read an app file. Allowed paths: backend/main.py, backend/test_main.py, ui.jsonl, state.json, app.json."""
        norm = path.lstrip("/")
        if norm not in READABLE:
            return {"error": f"path not allowed: {path!r}; allowed: {sorted(READABLE)}"}
        p = app.root / norm
        if not p.exists():
            _status(f"Checked {norm} (not created yet)")
            return {"exists": False, "content": ""}
        text = p.read_text()
        _status(f"Read {norm} ({len(text.splitlines())} lines)")
        return {"exists": True, "content": text}

    def write_file(path: str, content: str) -> dict:
        """Write backend/main.py or backend/test_main.py."""
        norm = path.lstrip("/")
        if norm not in WRITABLE:
            return {"error": f"write not allowed: {path!r}; allowed: {sorted(WRITABLE)}"}
        p = app.root / norm
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        tracker["written"].add(norm)
        tracker["tests_passed"] = False
        _status(f"Wrote {norm} ({len(content.splitlines())} lines, {len(content)} bytes)")
        return {"ok": True, "path": norm, "bytes": len(content)}

    def run_tests() -> dict:
        """Run unittest on backend/test_main.py inside the sandbox."""
        import re
        _status("Running backend tests in sandbox…")
        res = run_app_tests(app, sandbox=sandbox, policy=policy)
        tracker["tests_passed"] = bool(res.get("ok"))
        out = res.get("output") or res.get("error") or ""
        m = re.search(r"Ran (\d+) test", out)
        count_txt = f"{m.group(1)} test(s)" if m else "suite"
        if tracker["tests_passed"]:
            _status(f"Tests passed ({count_txt})")
        else:
            last_line = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "failed")
            _status(f"Tests failed ({count_txt}): {last_line[:80]}")
        return res

    def try_action(name: str, context_json: str = "{}") -> dict:
        """Dry-run handler `name` in a scratch sandbox against a copy of state.json.
        `context_json` is a JSON object string for the action context."""
        _status(f"Dry-running handler {name}…")
        try:
            ctx = json.loads(context_json) if context_json else {}
        except json.JSONDecodeError as e:
            _status(f"Dry-run {name}: invalid context JSON")
            return {"ok": False, "error": f"invalid context_json: {e}"}
        res = try_app_action(app, name, ctx, state=state_box, sandbox=sandbox, policy=policy)
        if res.get("ok") and res.get("ui"):
            errs = validate_a2ui_messages(res["ui"])
            if errs:
                _status(f"Dry-run {name}: emitted UI failed validation")
                return {"ok": False, "error": f"emitted UI failed validation: {errs}"}
        if res.get("ok"):
            n_patches = len(res.get("patches") or [])
            n_ui = len(res.get("ui") or [])
            _status(f"Dry-run {name}: OK ({n_patches} patch(es), {n_ui} UI msg(s))")
        else:
            _status(f"Dry-run {name}: failed ({str(res.get('error') or '')[:60]})")
        return res

    def set_data(path: str, value_json: str) -> dict:
        """Immediately update a JSON Pointer path in the live UI data model (e.g. '/status').
        `value_json` is a JSON-encoded value."""
        try:
            val = json.loads(value_json)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"invalid value_json: {e}"}
        msg = _patch_to_msg({"path": path, "value": val}, surface_id)
        if state_box is not None:
            _set_pointer(state_box, path, val)
            app.save_state(state_box)
        if dispatch_ui:
            dispatch_ui([msg])
        tracker["ui_sent"] = True
        return {"ok": True}

    def update_ui(messages_json: str) -> dict:
        """Validate and immediately dispatch A2UI v1.0 messages (JSON array string) to the live UI."""
        try:
            msgs = json.loads(messages_json)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"invalid messages_json: {e}"}
        if not isinstance(msgs, list):
            return {"ok": False, "error": "messages_json must be a JSON array"}
        errs = validate_a2ui_messages(msgs)
        if errs:
            return {"ok": False, "error": f"validation failed: {errs[:10]}"}
        if dispatch_ui:
            dispatch_ui(msgs)
        tracker["ui_sent"] = True
        return {"ok": True, "count": len(msgs)}

    def finish(summary: str) -> dict:
        """Call when backend/main.py and backend/test_main.py are complete and run_tests() passed."""
        tracker["summary"] = summary
        tracker["finished"] = True
        _status(f"Finalizing: {summary[:80]}")
        return {"ok": True}

    tools = [list_actions, read_file, write_file, run_tests, try_action, set_data, update_ui, finish]
    return tools, tracker
