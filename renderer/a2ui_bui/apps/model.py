# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""App folder model:

    apps/<app-id>/
      app.json          # id, title, width, prompt, model, created_at, updated_at, sandbox, max_runtime_calls
      ui.jsonl          # A2UI 1.0 messages (one JSON object per line)
      state.json        # persisted live data model (root dict for main surface)
      backend/
        main.py         # agent-written handlers
        test_main.py    # agent-written tests
      storage/          # app's own writable files + app.db (sqlite)
      history/          # v0001_main.py, v0001_test.py, v0001_meta.json ...
      log.jsonl         # action / handler / agent / version events
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def apps_dir() -> Path:
    env = os.environ.get("A2UI_BUI_APPS", "").strip()
    base = Path(env).expanduser() if env else Path.home() / ".local" / "share" / "a2ui_bui" / "apps"
    base.mkdir(parents=True, exist_ok=True)
    return base


def slugify(text: str, fallback: str = "app") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40]
    return s or fallback


def _initial_data_from_messages(messages: list[dict]) -> dict:
    data: dict[str, Any] = {}
    for m in messages:
        ud = m.get("updateDataModel")
        if not isinstance(ud, dict):
            continue
        path = (ud.get("path") or "/").strip()
        val = ud.get("value")
        if path in ("", "/"):
            if isinstance(val, dict):
                data = _deep_copy(val)
        else:
            _set_pointer(data, path, _deep_copy(val))
    return data


def _deep_copy(x: Any) -> Any:
    return json.loads(json.dumps(x))


def _set_pointer(root: dict, pointer: str, value: Any) -> None:
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
        cur[last] = value


@dataclass
class AppRecord:
    root: Path

    @property
    def id(self) -> str:
        return self.root.name

    @property
    def meta_path(self) -> Path:
        return self.root / "app.json"

    @property
    def ui_path(self) -> Path:
        return self.root / "ui.jsonl"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def backend_dir(self) -> Path:
        return self.root / "backend"

    @property
    def main_py(self) -> Path:
        return self.backend_dir / "main.py"

    @property
    def test_py(self) -> Path:
        return self.backend_dir / "test_main.py"

    @property
    def storage_dir(self) -> Path:
        return self.root / "storage"

    @property
    def history_dir(self) -> Path:
        return self.root / "history"

    @property
    def log_path(self) -> Path:
        return self.root / "log.jsonl"

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.backend_dir.mkdir(exist_ok=True)
        self.storage_dir.mkdir(exist_ok=True)
        self.history_dir.mkdir(exist_ok=True)

    def meta(self) -> dict:
        if self.meta_path.exists():
            return json.loads(self.meta_path.read_text())
        return {"id": self.id, "title": self.id, "width": 900}

    def save_meta(self, meta: dict) -> None:
        meta = {**meta, "id": self.id, "updated_at": time.time()}
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    def messages(self) -> list[dict]:
        if not self.ui_path.exists():
            return []
        return [json.loads(ln) for ln in self.ui_path.read_text().splitlines() if ln.strip()]

    def save_messages(self, messages: list[dict]) -> None:
        self.ui_path.write_text("".join(json.dumps(m, separators=(",", ":")) + "\n" for m in messages))

    def load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                pass
        return _initial_data_from_messages(self.messages())

    def save_state(self, data: dict) -> None:
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.state_path)

    def messages_with_state(self) -> list[dict]:
        """Return ui.jsonl with the initial root updateDataModel replaced by
        the persisted state.json so reopening the app restores all edits."""
        msgs = self.messages()
        state = self.load_state()
        if not state:
            return msgs
        out, replaced = [], False
        for m in msgs:
            ud = m.get("updateDataModel")
            if isinstance(ud, dict) and (ud.get("path") or "/") in ("", "/") and not replaced:
                out.append({**m, "updateDataModel": {**ud, "value": state}})
                replaced = True
            elif isinstance(ud, dict) and not replaced:
                out.append(m)
            else:
                out.append(m)
        if not replaced and out:
            # Insert right after createSurface if there was no root updateDataModel.
            idx = next((i + 1 for i, m in enumerate(out) if "createSurface" in m), 0)
            sid = next((m["createSurface"].get("surfaceId", "main") for m in out if "createSurface" in m), "main")
            out.insert(idx, {"version": "1.0", "updateDataModel": {"surfaceId": sid, "value": state}})
        return out

    def declared_actions(self) -> list[dict]:
        """Extract all declared A2UI action events from ui.jsonl."""
        seen: list[dict] = []
        for m in self.messages():
            uc = m.get("updateComponents")
            if not isinstance(uc, dict):
                continue
            for comp in uc.get("components", []):
                if not isinstance(comp, dict):
                    continue
                act = comp.get("action")
                if not isinstance(act, dict):
                    continue
                ev = act.get("event")
                if isinstance(ev, dict) and ev.get("name"):
                    seen.append({
                        "name": ev["name"],
                        "componentId": comp.get("id"),
                        "component": comp.get("component"),
                        "context": ev.get("context") or {},
                    })
        return seen

    def append_log(self, entry: dict) -> None:
        entry = {"ts": time.time(), **entry}
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def read_log(self, limit: int = 100) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = [ln for ln in self.log_path.read_text().splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]]

    # -- backend versioning ---------------------------------------------------
    def versions(self) -> list[dict]:
        if not self.history_dir.exists():
            return []
        out = []
        for p in sorted(self.history_dir.glob("v*_meta.json")):
            out.append(json.loads(p.read_text()))
        return out

    def save_version(self, summary: str, *, source: str = "agent") -> dict:
        self.ensure_dirs()
        existing = sorted(self.history_dir.glob("v*_meta.json"))
        n = len(existing) + 1
        tag = f"v{n:04d}"
        if self.main_py.exists():
            (self.history_dir / f"{tag}_main.py").write_text(self.main_py.read_text())
        if self.test_py.exists():
            (self.history_dir / f"{tag}_test.py").write_text(self.test_py.read_text())
        info = {"version": n, "tag": tag, "ts": time.time(), "source": source, "summary": summary}
        (self.history_dir / f"{tag}_meta.json").write_text(json.dumps(info, indent=2) + "\n")
        meta = self.meta()
        meta["backend_version"] = n
        self.save_meta(meta)
        self.append_log({"kind": "version", **info})
        return info

    def rollback(self, version: int | None = None) -> dict | None:
        vs = self.versions()
        if not vs:
            return None
        target = None
        if version is None:
            # Roll back to previous version if possible, else latest.
            target = vs[-2] if len(vs) >= 2 else vs[-1]
        else:
            target = next((v for v in vs if v["version"] == version), None)
        if target is None:
            return None
        tag = target["tag"]
        mp = self.history_dir / f"{tag}_main.py"
        tp = self.history_dir / f"{tag}_test.py"
        if mp.exists():
            self.main_py.write_text(mp.read_text())
        if tp.exists():
            self.test_py.write_text(tp.read_text())
        self.append_log({"kind": "rollback", "to_version": target["version"]})
        return target

    def has_backend(self) -> bool:
        return self.main_py.exists() and self.main_py.read_text().strip() != ""


def create_app(
    *,
    title: str,
    messages: list[dict],
    width: int = 900,
    prompt: str = "",
    model: str = "",
    app_id: str | None = None,
    base_dir: Path | None = None,
    max_runtime_calls: int = 25,
) -> AppRecord:
    base = base_dir or apps_dir()
    base.mkdir(parents=True, exist_ok=True)
    slug = slugify(app_id or title or prompt)
    cand = base / slug
    if app_id is None and cand.exists():
        i = 2
        while (base / f"{slug}-{i}").exists():
            i += 1
        cand = base / f"{slug}-{i}"
    rec = AppRecord(cand)
    rec.ensure_dirs()
    now = time.time()
    rec.save_messages(messages)
    rec.save_state(_initial_data_from_messages(messages))
    rec.save_meta({
        "id": rec.id,
        "title": title or rec.id,
        "width": int(width or 900),
        "prompt": prompt,
        "model": model,
        "created_at": now,
        "updated_at": now,
        "sandbox": "auto",
        "max_runtime_calls": int(max_runtime_calls),
        "runtime_calls_used": 0,
        "backend_version": 0,
    })
    return rec


def get_app(app_id: str, base_dir: Path | None = None) -> AppRecord:
    p = Path(app_id)
    if p.is_dir() and (p / "app.json").exists():
        return AppRecord(p)
    rec = AppRecord((base_dir or apps_dir()) / app_id)
    if not rec.root.is_dir() or not rec.meta_path.exists():
        raise FileNotFoundError(f"no app named {app_id!r}")
    return rec


def list_apps(base_dir: Path | None = None) -> list[dict]:
    base = base_dir or apps_dir()
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "app.json").exists():
            rec = AppRecord(d)
            m = rec.meta()
            m["has_backend"] = rec.has_backend()
            m["actions_count"] = len({a["name"] for a in rec.declared_actions()})
            out.append(m)
    out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
    return out


def delete_app(app_id: str, base_dir: Path | None = None) -> bool:
    rec = AppRecord((base_dir or apps_dir()) / app_id)
    if not rec.root.is_dir():
        return False
    shutil.rmtree(rec.root)
    return True
