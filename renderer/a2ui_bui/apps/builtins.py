# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Built-in reference apps seeded from showcases so Phase 1 apps work out of
the box without needing an API key."""

from __future__ import annotations

import json
from pathlib import Path

from .model import AppRecord, apps_dir, create_app

REPO = Path(__file__).resolve().parents[3]

_PROJECT_TRACKER_MAIN = '''from a2ui_app import app

def _init_db(data):
    app.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT 'you',
            due TEXT NOT NULL DEFAULT 'Soon',
            due_tone TEXT NOT NULL DEFAULT 'muted',
            priority TEXT NOT NULL DEFAULT 'Medium',
            done INTEGER NOT NULL DEFAULT 0
        );
    """)
    rows = app.db.query("SELECT id, title, owner, due, due_tone, priority, done FROM tasks ORDER BY id")
    if not rows:
        for t in data.get("tasks", []):
            app.db.execute(
                "INSERT INTO tasks(id, title, owner, due, due_tone, priority, done) VALUES (?,?,?,?,?,?,?)",
                (int(t["id"]), t["title"], t.get("owner", "maya"), t.get("due", "Today"),
                 t.get("due_tone", "muted"), t.get("priority", "Medium"), 1 if t.get("done") else 0),
            )
    else:
        data["tasks"] = [{**r, "done": bool(r["done"])} for r in rows]

def _recompute(data):
    tasks = data.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    data["progress"] = (done / total) if total else 0.0
    data["progress_text"] = f"{done} of {total} done"

@app.on("task_toggle")
def task_toggle(ctx, data):
    _init_db(data)
    tid = ctx.get("id")
    for t in data.get("tasks", []):
        if t.get("id") == tid:
            new_done = bool(ctx.get("done")) if "done" in ctx else (not t.get("done"))
            t["done"] = new_done
            app.db.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if new_done else 0, int(tid)))
            break
    _recompute(data)

@app.on("task_add")
def task_add(ctx, data):
    _init_db(data)
    title = (ctx.get("title") or data.get("draft") or "").strip()
    if not title:
        return
    tasks = data.get("tasks", [])
    next_id = max((int(t.get("id", 0)) for t in tasks), default=-1) + 1
    item = {
        "id": next_id,
        "title": title,
        "owner": "you",
        "due": "Today",
        "due_tone": "orange",
        "priority": "Medium",
        "done": False,
    }
    tasks.append(item)
    app.db.execute(
        "INSERT INTO tasks(id, title, owner, due, due_tone, priority, done) VALUES (?,?,?,?,?,?,0)",
        (next_id, title, "you", "Today", "orange", "Medium"),
    )
    data["draft"] = ""
    _recompute(data)

@app.on("task_filter")
def task_filter(ctx, data):
    _init_db(data)
    q = (ctx.get("q") if "q" in ctx else (data.get("filters") or {}).get("q") or "").strip().lower()
    rows = app.db.query("SELECT id, title, owner, due, due_tone, priority, done FROM tasks ORDER BY id")
    all_tasks = [{**r, "done": bool(r["done"])} for r in rows]
    if q:
        data["tasks"] = [t for t in all_tasks if q in t["title"].lower() or q in t["owner"].lower()]
    else:
        data["tasks"] = all_tasks
    _recompute(data)
'''

_PROJECT_TRACKER_TEST = '''import os, tempfile, unittest
from pathlib import Path
from a2ui_app import TrackedDict, _PatchSink, app
import main  # noqa: F401

class ProjectTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.storage.root = Path(self.tmp.name)
        app.db._conn = None
        app.db.path = Path(self.tmp.name) / "app.db"
        self.sink = _PatchSink()
        self.data = TrackedDict({
            "draft": "",
            "progress": 0.0,
            "progress_text": "0 of 1 done",
            "filters": {"q": ""},
            "tasks": [{"id": 0, "title": "First", "owner": "maya", "due": "Today",
                       "due_tone": "orange", "priority": "High", "done": False}],
        }, "", self.sink)

    def tearDown(self):
        if app.db._conn is not None:
            app.db._conn.close()
            app.db._conn = None
        self.tmp.cleanup()

    def test_add_toggle_filter(self):
        main.task_add({"title": "Second"}, self.data)
        self.assertEqual(len(self.data["tasks"]), 2)
        self.assertEqual(self.data["progress_text"], "0 of 2 done")
        main.task_toggle({"id": 1, "done": True}, self.data)
        self.assertEqual(self.data["progress"], 0.5)
        main.task_filter({"q": "sec"}, self.data)
        self.assertEqual(len(self.data["tasks"]), 1)
        main.task_filter({"q": ""}, self.data)
        self.assertEqual(len(self.data["tasks"]), 2)

if __name__ == "__main__":
    unittest.main()
'''

_RENDER_FARM_MAIN = '''import time
from a2ui_app import app

@app.on("queue_pause")
def queue_pause(ctx, data):
    data["paused"] = bool(ctx.get("paused")) if "paused" in ctx else (not data.get("paused"))

@app.on("job_pause")
def job_pause(ctx, data):
    jid = ctx.get("job")
    for j in data.get("jobs", []):
        if j.get("id") == jid:
            j["status"] = "Paused" if j.get("status") != "Paused" else "Rendering"
            break

@app.on("job_cancel")
def job_cancel(ctx, data):
    jid = ctx.get("job")
    jobs = [j for j in data.get("jobs", []) if j.get("id") != jid]
    data["jobs"] = jobs
    data["summary"] = f"{len(jobs)} jobs · {len(data.get('workers', []))} workers"

@app.on("job_submit")
def job_submit(ctx, data):
    jobs = data.get("jobs", [])
    jid = f"j{820 + len(jobs)}"
    job = {"id": jid, "name": f"shot_{len(jobs)+1:03d}_beauty", "icon": "RENDER_ANIMATION",
           "progress": 0.0, "node": "a100-02", "status": "Queued"}
    jobs.append(job)
    data["summary"] = f"{len(jobs)} jobs · {len(data.get('workers', []))} workers"
    for step in range(1, 6):
        time.sleep(0.02)
        job["progress"] = step / 5.0
        job["status"] = f"{step * 20}%" if step < 5 else "Done"
        yield

@app.on("job_inspect")
def job_inspect(ctx, data):
    idx = ctx.get("index")
    data["history_sel"] = idx

@app.on("browse_blend")
def browse_blend(ctx, data):
    if ctx.get("value"):
        data["blend_path"] = ctx["value"]

@app.on("preview_ended")
def preview_ended(ctx, data):
    pass

@app.every(4)
def step_queue(data):
    if data.get("paused"):
        return
    for j in data.get("jobs", []):
        if j.get("status") not in ("Paused", "Done") and (j.get("progress") or 0) < 1.0:
            p = min(1.0, round((j.get("progress") or 0.0) + 0.05, 2))
            j["progress"] = p
            j["status"] = "Done" if p >= 1.0 else f"{int(p * 100)}%"
'''

_RENDER_FARM_TEST = '''import unittest
from a2ui_app import TrackedDict, _PatchSink
import main

class RenderFarmTests(unittest.TestCase):
    def setUp(self):
        self.data = TrackedDict({
            "paused": False,
            "summary": "1 jobs · 1 workers",
            "workers": [{"id": "a100-01"}],
            "jobs": [{"id": "j812", "name": "sh040", "progress": 0.5, "status": "Rendering"}],
        }, "", _PatchSink())

    def test_pause_submit_cancel(self):
        main.queue_pause({"paused": True}, self.data)
        self.assertTrue(self.data["paused"])
        list(main.job_submit({}, self.data))
        self.assertEqual(len(self.data["jobs"]), 2)
        self.assertEqual(self.data["jobs"][-1]["status"], "Done")
        main.job_cancel({"job": "j812"}, self.data)
        self.assertEqual(len(self.data["jobs"]), 1)

if __name__ == "__main__":
    unittest.main()
'''

SPECS = {
    "project-tracker": (_PROJECT_TRACKER_MAIN, _PROJECT_TRACKER_TEST, "Task tracker with SQLite persistence"),
    "render-farm": (_RENDER_FARM_MAIN, _RENDER_FARM_TEST, "Render queue with streaming job submission and background tick"),
}


def seed_builtin_apps(base_dir: Path | None = None) -> list[AppRecord]:
    base = base_dir or apps_dir()
    out: list[AppRecord] = []
    for sid, (main_src, test_src, summary) in SPECS.items():
        sc_path = REPO / "showcases" / f"{sid}.json"
        if not sc_path.exists():
            continue
        app_dir = base / sid
        if (app_dir / "app.json").exists():
            out.append(AppRecord(app_dir))
            continue
        sc = json.loads(sc_path.read_text())
        rec = create_app(
            title=sc.get("name", sid),
            messages=sc["messages"],
            width=int(sc.get("width") or 900),
            prompt=sc.get("description", ""),
            model="builtin",
            app_id=sid,
            base_dir=base,
        )
        rec.main_py.write_text(main_src.lstrip())
        rec.test_py.write_text(test_src.lstrip())
        rec.save_version(summary, source="builtin")
        out.append(rec)
    return out
