# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Built-in reference apps seeded from showcases so Phase 1 apps work out of
the box without needing an API key."""

from __future__ import annotations

import json
import sys
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
            j["status"] = "Paused" if j["status"] != "Paused" else "Rendering"
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

_SYNTH_PATCH_MAIN = '''import io
import math
import struct
import wave
from a2ui_app import app

_SAMPLE_RATE = 22050

_NOTE_FREQ = {
    "C2": 65.41, "D2": 73.42, "EB2": 77.78, "E2": 82.41, "F2": 87.31,
    "G2": 98.00, "A2": 110.00, "BB2": 116.54, "B2": 123.47,
    "C3": 130.81, "D3": 146.83, "EB3": 155.56, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "BB3": 233.08, "B3": 246.94, "C4": 261.63,
}

_PRESETS = [
    {
        "name": "Acid Bass",
        "osc": {"wave": "saw", "detune": 12.0, "pw": 0.35, "level": 0.8},
        "filter": {"type": "lp24", "cutoff": 1200.0, "res": 0.62, "env": 0.55},
        "env": {"a": 0.01, "d": 0.35, "s": 0.3, "r": 0.25},
        "bpm": 128.0,
    },
    {
        "name": "Sub Pad",
        "osc": {"wave": "tri", "detune": 6.0, "pw": 0.5, "level": 0.85},
        "filter": {"type": "lp24", "cutoff": 650.0, "res": 0.25, "env": 0.3},
        "env": {"a": 0.08, "d": 0.45, "s": 0.7, "r": 0.5},
        "bpm": 96.0,
    },
    {
        "name": "Pluck Lead",
        "osc": {"wave": "square", "detune": 16.0, "pw": 0.28, "level": 0.78},
        "filter": {"type": "lp24", "cutoff": 2600.0, "res": 0.45, "env": 0.75},
        "env": {"a": 0.005, "d": 0.22, "s": 0.15, "r": 0.18},
        "bpm": 136.0,
    },
]


def _osc_sample(wave_kind, phase, pw):
    p = phase % 1.0
    if wave_kind == "square":
        return 1.0 if p < max(0.05, min(0.95, pw)) else -1.0
    if wave_kind == "tri":
        return 4.0 * abs(p - 0.5) - 1.0
    if wave_kind == "sine":
        return math.sin(2.0 * math.pi * p)
    return 2.0 * p - 1.0


def _render_note(freq, dur, osc, flt, env):
    n = max(1, int(_SAMPLE_RATE * dur))
    wave_kind = str(osc.get("wave") or "saw").lower()
    detune_cents = float(osc.get("detune") or 0.0)
    detune_ratio = 2.0 ** (detune_cents / 1200.0)
    pw = float(osc.get("pw") or 0.5)
    level = max(0.05, min(1.0, float(osc.get("level") or 0.8)))

    cutoff = max(80.0, min(8000.0, float(flt.get("cutoff") or 1200.0)))
    res = max(0.0, min(0.95, float(flt.get("res") or 0.4)))
    env_amt = float(flt.get("env") or 0.5)

    a = max(0.003, float(env.get("a") or 0.01))
    d = max(0.03, float(env.get("d") or 0.3))
    s = max(0.0, min(1.0, float(env.get("s") or 0.35)))
    r = max(0.02, float(env.get("r") or 0.2))

    y1 = 0.0
    y2 = 0.0
    fb = min(3.5, res * 3.2)
    ph1 = 0.0
    ph2 = 0.0
    dt = 1.0 / _SAMPLE_RATE
    out = []
    rel_start = max(0.0, dur - r)
    for i in range(n):
        t = i * dt
        if t < a:
            amp = t / a
        elif t < a + d:
            amp = 1.0 - (1.0 - s) * ((t - a) / d)
        elif t < rel_start:
            amp = s
        else:
            amp = s * max(0.0, 1.0 - (t - rel_start) / r)

        ph1 += freq * dt
        ph2 += (freq * detune_ratio) * dt
        raw = 0.55 * _osc_sample(wave_kind, ph1, pw) + 0.45 * _osc_sample(wave_kind, ph2, pw)

        fc = min(9000.0, cutoff * (0.55 + 1.8 * env_amt * amp))
        alpha = min(0.92, (2.0 * math.pi * fc) / (_SAMPLE_RATE + 2.0 * math.pi * fc))
        x = raw - fb * y2
        y1 = y1 + alpha * (x - y1)
        y2 = y2 + alpha * (y1 - y2)
        sample = max(-0.98, min(0.98, y2 * amp * level))
        out.append(int(sample * 32767))
    return out


def _encode_wav(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return buf.getvalue()


def _recompute_spectrum(data):
    osc = data.get("osc") or {}
    flt = data.get("filter") or {}
    wave_kind = str(osc.get("wave") or "saw").lower()
    cutoff = max(100.0, min(8000.0, float(flt.get("cutoff") or 1200.0)))
    res = max(0.0, min(1.0, float(flt.get("res") or 0.5)))
    norm_cut = max(0.1, min(0.95, math.log10(cutoff / 80.0) / 2.0))
    bins = []
    for i in range(16):
        x = i / 15.0
        if wave_kind == "sine":
            base = 0.95 if i == 0 else (0.18 if i == 1 else 0.04)
        elif wave_kind == "square":
            base = (0.95 / (i + 1) ** 0.65) if (i % 2 == 0) else 0.12
        elif wave_kind == "tri":
            base = 0.95 / ((i + 1) ** 1.15)
        else:
            base = 0.95 / ((i + 1) ** 0.55)
        lpf = 1.0 / (1.0 + max(0.0, (x - norm_cut) * 6.0) ** 2)
        peak = res * 0.45 * math.exp(-((x - norm_cut) ** 2) / 0.012)
        bins.append(round(max(0.03, min(1.0, base * lpf + peak)), 3))
    data["spectrum"] = bins


def _play_pattern(data, root_note="C3", short=False):
    osc = data.get("osc") or {}
    flt = data.get("filter") or {}
    env = data.get("env") or {}
    bpm = max(60.0, min(220.0, float(data.get("bpm") or 128.0)))
    step_dur = (60.0 / bpm) * 0.5
    root = _NOTE_FREQ.get(str(root_note).upper(), 130.81)
    if short:
        samples = _render_note(root, 0.28, osc, flt, env)
    else:
        ratios = [0.5, 1.0, 0.75, 1.189, 0.5, 1.5, 0.891, 1.0]
        samples = []
        for r in ratios:
            samples.extend(_render_note(root * r, step_dur, osc, flt, env))
    app.audio.play_wav(_encode_wav(samples))


@app.on("patch_changed")
def patch_changed(ctx, data):
    if "links" in ctx and isinstance(ctx["links"], list):
        data["links"] = ctx["links"]
    _recompute_spectrum(data)


@app.on("osc_wave")
def osc_wave(ctx, data):
    wave_kind = ctx.get("wave")
    if wave_kind:
        osc = dict(data.get("osc") or {})
        osc["wave"] = wave_kind
        data["osc"] = osc
    _recompute_spectrum(data)
    _play_pattern(data, short=True)


@app.on("note_on")
def note_on(ctx, data):
    note = ctx.get("note") or "C3"
    if "bpm" in ctx and ctx["bpm"] is not None:
        data["bpm"] = float(ctx["bpm"])
    _recompute_spectrum(data)
    _play_pattern(data, root_note=note, short=False)


@app.on("preset")
def preset(ctx, data):
    idx = int(data.get("_preset_idx") or 0) % len(_PRESETS)
    p = _PRESETS[idx]
    data["_preset_idx"] = (idx + 1) % len(_PRESETS)
    data["osc"] = dict(p["osc"])
    data["filter"] = dict(p["filter"])
    data["env"] = dict(p["env"])
    data["bpm"] = p["bpm"]
    _recompute_spectrum(data)
    _play_pattern(data, short=True)
'''

_SYNTH_PATCH_TEST = '''import unittest
from a2ui_app import TrackedDict, app
import main

class SynthPatchTests(unittest.TestCase):
    def setUp(self):
        app._sink.drain_audio()
        self.data = TrackedDict({
            "links": [["osc1", 0, "filt", 0]],
            "osc": {"wave": "saw", "detune": 12.0, "pw": 0.35, "level": 0.8},
            "filter": {"type": "lp24", "cutoff": 1200.0, "res": 0.62, "env": 0.55},
            "env": {"a": 0.01, "d": 0.35, "s": 0.3, "r": 0.25},
            "spectrum": [0.5] * 16,
            "bpm": 128.0,
        }, "", app._sink)

    def test_note_on_emits_wav_and_updates_spectrum(self):
        main.note_on({"note": "C3", "bpm": 128}, self.data)
        clips = app._sink.drain_audio()
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0]["mime"], "audio/wav")
        self.assertGreater(len(clips[0]["data"]), 1000)
        self.assertEqual(len(self.data["spectrum"]), 16)

    def test_preset_and_wave(self):
        main.osc_wave({"wave": "square"}, self.data)
        self.assertEqual(self.data["osc"]["wave"], "square")
        self.assertEqual(len(app._sink.drain_audio()), 1)
        main.preset({}, self.data)
        self.assertEqual(len(app._sink.drain_audio()), 1)

if __name__ == "__main__":
    unittest.main()
'''

_3D_DESIGNER_SPEC = {
    "name": "3D Designer",
    "window": "3D Designer — Scene Studio",
    "width": 1240,
    "description": "Simple Blender-style 3D scene editor with spheres, cubes, and lights, move/rotate/scale transforms, procedural textures, and a live ray-traced viewport.",
    "messages": [
        {
            "version": "1.0",
            "createSurface": {
                "surfaceId": "main",
                "catalogId": "https://a2ui-bui-demo.local/catalogs/bui/v1/catalog.json",
                "sendDataModel": True,
            },
        },
        {
            "version": "1.0",
            "updateDataModel": {
                "surfaceId": "main",
                "value": {
                    "camera": "three_quarter",
                    "render_mode": "solid",
                    "render_seq": 0,
                    "viewport_src": "storage://render_0.png",
                    "status_text": "3 objects · 1 light · Selected: Hero Sphere",
                    "selected_index": 0,
                    "selected_name": "Hero Sphere",
                    "selected_kind": "sphere",
                    "selected_loc": [0.0, 0.0, 0.9],
                    "selected_rot": [0.0, 0.0, 0.0],
                    "selected_scale": [1.0, 1.0, 1.0],
                    "selected_texture": "Checker",
                    "selected_color": [0.92, 0.48, 0.20, 1.0],
                    "selected_roughness": 0.25,
                    "objects": [
                        {
                            "id": "obj_1",
                            "label": "Hero Sphere (sphere)",
                            "name": "Hero Sphere",
                            "kind": "sphere",
                            "icon": "MESH_UVSPHERE",
                            "loc": [0.0, 0.0, 0.9],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": [1.0, 1.0, 1.0],
                            "texture": "Checker",
                            "color": [0.92, 0.48, 0.20, 1.0],
                            "roughness": 0.25,
                        },
                        {
                            "id": "obj_2",
                            "label": "Studio Cube (cube)",
                            "name": "Studio Cube",
                            "kind": "cube",
                            "icon": "MESH_CUBE",
                            "loc": [-2.1, 0.7, 0.75],
                            "rot": [0.0, 0.0, 28.0],
                            "scale": [0.85, 0.85, 0.85],
                            "texture": "Brick",
                            "color": [0.30, 0.62, 0.88, 1.0],
                            "roughness": 0.45,
                        },
                        {
                            "id": "obj_3",
                            "label": "Key Light (light)",
                            "name": "Key Light",
                            "kind": "light",
                            "icon": "LIGHT",
                            "loc": [3.2, -3.5, 4.8],
                            "rot": [0.0, 0.0, 0.0],
                            "scale": [1.0, 1.0, 1.0],
                            "texture": "Solid",
                            "color": [1.0, 0.96, 0.88, 1.0],
                            "roughness": 0.1,
                        },
                    ],
                },
            },
        },
        {
            "version": "1.0",
            "updateComponents": {
                "surfaceId": "main",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "spacing": "small",
                        "padding": 0.5,
                        "children": ["toolbar", "workspace", "status_bar"],
                    },
                    {
                        "id": "toolbar",
                        "component": "Row",
                        "spacing": "small",
                        "children": [
                            "btn_add_sphere",
                            "btn_add_cube",
                            "btn_add_light",
                            "btn_delete",
                            "btn_reset",
                            "cam_label",
                            "btn_cam_34",
                            "btn_cam_front",
                            "btn_cam_top",
                            "mode_enum",
                        ],
                    },
                    {
                        "id": "btn_add_sphere",
                        "component": "Button",
                        "text": "+ Sphere",
                        "icon": "MESH_UVSPHERE",
                        "action": {"event": {"name": "add_object", "context": {"kind": "sphere"}}},
                    },
                    {
                        "id": "btn_add_cube",
                        "component": "Button",
                        "text": "+ Cube",
                        "icon": "MESH_CUBE",
                        "action": {"event": {"name": "add_object", "context": {"kind": "cube"}}},
                    },
                    {
                        "id": "btn_add_light",
                        "component": "Button",
                        "text": "+ Light",
                        "icon": "LIGHT",
                        "action": {"event": {"name": "add_object", "context": {"kind": "light"}}},
                    },
                    {
                        "id": "btn_delete",
                        "component": "Button",
                        "text": "Delete",
                        "icon": "TRASH",
                        "alert": True,
                        "action": {"event": {"name": "delete_selected"}},
                    },
                    {
                        "id": "btn_reset",
                        "component": "Button",
                        "text": "Reset Scene",
                        "icon": "LOOP_BACK",
                        "action": {"event": {"name": "reset_scene"}},
                    },
                    {"id": "cam_label", "component": "Label", "text": "Camera:", "bold": True},
                    {
                        "id": "btn_cam_34",
                        "component": "Button",
                        "text": "3/4",
                        "action": {"event": {"name": "set_camera", "context": {"camera": "three_quarter"}}},
                    },
                    {
                        "id": "btn_cam_front",
                        "component": "Button",
                        "text": "Front",
                        "action": {"event": {"name": "set_camera", "context": {"camera": "front"}}},
                    },
                    {
                        "id": "btn_cam_top",
                        "component": "Button",
                        "text": "Top",
                        "action": {"event": {"name": "set_camera", "context": {"camera": "top"}}},
                    },
                    {
                        "id": "workspace",
                        "component": "Split",
                        "factor": 0.19,
                        "left": "outliner_panel",
                        "right": "viewport_props_split",
                    },
                    {
                        "id": "viewport_props_split",
                        "component": "Split",
                        "factor": 0.68,
                        "left": "viewport_panel",
                        "right": "props_panel",
                    },
                    {
                        "id": "outliner_panel",
                        "component": "Panel",
                        "title": "Scene Outliner",
                        "icon": "OUTLINER",
                        "children": ["outliner_list"],
                    },
                    {
                        "id": "outliner_list",
                        "component": "ListView",
                        "items": {"@path": "/objects"},
                        "selected": {"@path": "/selected_index"},
                        "rows": 21,
                        "action": {
                            "event": {
                                "name": "select_object",
                                "context": {"index": {"@path": "/selected_index"}},
                            }
                        },
                    },
                    {
                        "id": "viewport_panel",
                        "component": "Panel",
                        "title": "3D Viewport",
                        "icon": "VIEW3D",
                        "children": ["viewport_img"],
                    },
                    {
                        "id": "mode_enum",
                        "component": "EnumRow",
                        "value": {"@path": "/render_mode"},
                        "items": [
                            {"value": "wireframe", "label": "Wireframe"},
                            {"value": "solid", "label": "Fast Solid"},
                            {"value": "raytraced", "label": "Raytraced"},
                        ],
                        "action": {
                            "event": {
                                "name": "set_render_mode",
                                "context": {"mode": {"@path": "/render_mode"}},
                            }
                        },
                    },
                    {
                        "id": "viewport_img",
                        "component": "Image",
                        "src": {"@path": "/viewport_src"},
                        "alt": "3D Viewport",
                        "height": 42,
                        "fit": "cover",
                    },
                    {
                        "id": "props_panel",
                        "component": "Panel",
                        "title": "Object & Material",
                        "icon": "PROPERTIES",
                        "children": ["props_col"],
                    },
                    {
                        "id": "props_col",
                        "component": "Column",
                        "spacing": "small",
                        "children": [
                            "sel_header",
                            "loc_label",
                            "loc_vec",
                            "rot_label",
                            "rot_vec",
                            "scale_label",
                            "scale_vec",
                            "mat_div",
                            "tex_label",
                            "tex_drop",
                            "col_label",
                            "col_swatch",
                            "rough_slider",
                        ],
                    },
                    {
                        "id": "sel_header",
                        "component": "Label",
                        "text": {"@path": "/selected_name"},
                        "bold": True,
                        "size": "large",
                    },
                    {"id": "loc_label", "component": "Label", "text": "Location (X, Y, Z)", "color": "muted"},
                    {
                        "id": "loc_vec",
                        "component": "VectorField",
                        "value": {"@path": "/selected_loc"},
                        "precision": 2,
                        "step": 0.2,
                        "suffix": " m",
                        "action": {
                            "event": {
                                "name": "update_transform",
                                "context": {"prop": "loc", "value": {"@path": "/selected_loc"}},
                            }
                        },
                    },
                    {"id": "rot_label", "component": "Label", "text": "Rotation (deg)", "color": "muted"},
                    {
                        "id": "rot_vec",
                        "component": "VectorField",
                        "value": {"@path": "/selected_rot"},
                        "precision": 1,
                        "step": 5.0,
                        "suffix": "°",
                        "action": {
                            "event": {
                                "name": "update_transform",
                                "context": {"prop": "rot", "value": {"@path": "/selected_rot"}},
                            }
                        },
                    },
                    {"id": "scale_label", "component": "Label", "text": "Scale", "color": "muted"},
                    {
                        "id": "scale_vec",
                        "component": "VectorField",
                        "value": {"@path": "/selected_scale"},
                        "precision": 2,
                        "step": 0.1,
                        "action": {
                            "event": {
                                "name": "update_transform",
                                "context": {"prop": "scale", "value": {"@path": "/selected_scale"}},
                            }
                        },
                    },
                    {"id": "mat_div", "component": "Separator", "line": True},
                    {"id": "tex_label", "component": "Label", "text": "Surface Texture", "color": "muted"},
                    {
                        "id": "tex_drop",
                        "component": "Dropdown",
                        "value": {"@path": "/selected_texture"},
                        "items": ["Checker", "Brick", "Marble", "Grid", "Solid"],
                        "action": {
                            "event": {
                                "name": "update_material",
                                "context": {"prop": "texture", "value": {"@path": "/selected_texture"}},
                            }
                        },
                    },
                    {"id": "col_label", "component": "Label", "text": "Base Color", "color": "muted"},
                    {
                        "id": "col_swatch",
                        "component": "ColorSwatch",
                        "value": {"@path": "/selected_color"},
                        "picker": True,
                        "action": {
                            "event": {
                                "name": "update_material",
                                "context": {"prop": "color", "value": {"@path": "/selected_color"}},
                            }
                        },
                    },
                    {
                        "id": "rough_slider",
                        "component": "NumberSlider",
                        "label": "Roughness",
                        "value": {"@path": "/selected_roughness"},
                        "min": 0.05,
                        "max": 1.0,
                        "precision": 2,
                        "action": {
                            "event": {
                                "name": "update_material",
                                "context": {"prop": "roughness", "value": {"@path": "/selected_roughness"}},
                            }
                        },
                    },
                    {
                        "id": "status_bar",
                        "component": "Label",
                        "text": {"@path": "/status_text"},
                        "color": "muted",
                    },
                ],
            },
        },
    ],
}

_3D_DESIGNER_MAIN = '''import math
from a2ui_app import app

_W = 640
_H = 440

_DEFAULT_OBJECTS = [
    {
        "id": "obj_1",
        "label": "Hero Sphere (sphere)",
        "name": "Hero Sphere",
        "kind": "sphere",
        "icon": "MESH_UVSPHERE",
        "loc": [0.0, 0.0, 0.9],
        "rot": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
        "texture": "Checker",
        "color": [0.92, 0.48, 0.20, 1.0],
        "roughness": 0.25,
    },
    {
        "id": "obj_2",
        "label": "Studio Cube (cube)",
        "name": "Studio Cube",
        "kind": "cube",
        "icon": "MESH_CUBE",
        "loc": [-2.1, 0.7, 0.75],
        "rot": [0.0, 0.0, 28.0],
        "scale": [0.85, 0.85, 0.85],
        "texture": "Brick",
        "color": [0.30, 0.62, 0.88, 1.0],
        "roughness": 0.45,
    },
    {
        "id": "obj_3",
        "label": "Key Light (light)",
        "name": "Key Light",
        "kind": "light",
        "icon": "LIGHT",
        "loc": [3.2, -3.5, 4.8],
        "rot": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
        "texture": "Solid",
        "color": [1.0, 0.96, 0.88, 1.0],
        "roughness": 0.1,
    },
]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    l = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if l < 1e-8:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def _rot_matrix(deg):
    rx, ry, rz = [math.radians(float(x)) for x in deg]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # Z * Y * X rotation columns
    m00 = cy * cz
    m01 = cz * sx * sy - cx * sz
    m02 = cx * cz * sy + sx * sz
    m10 = cy * sz
    m11 = cx * cz + sx * sy * sz
    m12 = cx * sy * sz - cz * sx
    m20 = -sy
    m21 = cy * sx
    m22 = cx * cy
    return ((m00, m01, m02), (m10, m11, m12), (m20, m21, m22))


def _mat_t_vec(m, v):
    return (
        m[0][0] * v[0] + m[1][0] * v[1] + m[2][0] * v[2],
        m[0][1] * v[0] + m[1][1] * v[1] + m[2][1] * v[2],
        m[0][2] * v[0] + m[1][2] * v[1] + m[2][2] * v[2],
    )


def _mat_vec(m, v):
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _sample_texture(tex, u, v, base_rgb):
    r, g, b = base_rgb
    if tex == "Checker":
        c = (int(math.floor(u * 3.0)) + int(math.floor(v * 3.0))) & 1
        f = 1.0 if c == 0 else 0.48
        return (r * f, g * f, b * f)
    if tex == "Brick":
        row = int(math.floor(v * 4.0))
        uu = u * 2.5 + (0.5 if (row & 1) else 0.0)
        fx = uu - math.floor(uu)
        fy = (v * 4.0) - math.floor(v * 4.0)
        if fx < 0.08 or fy < 0.10:
            return (0.78, 0.76, 0.72)
        shade = 0.85 + 0.15 * ((row * 3 + int(math.floor(uu))) % 3) / 2.0
        return (r * shade, g * shade, b * shade)
    if tex == "Marble":
        t = 0.5 + 0.5 * math.sin(u * 5.0 + 1.8 * math.sin(v * 4.0 + u * 2.5))
        return (r * (0.45 + 0.55 * t) + 0.18 * t, g * (0.45 + 0.55 * t) + 0.18 * t, b * (0.45 + 0.55 * t) + 0.18 * t)
    if tex == "Grid":
        fx = abs((u * 4.0) - round(u * 4.0))
        fy = abs((v * 4.0) - round(v * 4.0))
        if fx < 0.08 or fy < 0.08:
            return (min(1.0, r * 0.3 + 0.7), min(1.0, g * 0.3 + 0.7), min(1.0, b * 0.3 + 0.7))
        return (r * 0.75, g * 0.75, b * 0.75)
    return (r, g, b)


def _prepare_obj(obj):
    kind = obj.get("kind") or "sphere"
    loc = tuple(float(x) for x in (obj.get("loc") or [0, 0, 0]))
    scale = tuple(max(0.1, float(x)) for x in (obj.get("scale") or [1, 1, 1]))
    m = _rot_matrix(obj.get("rot") or [0, 0, 0])
    col = obj.get("color") or [0.8, 0.8, 0.8, 1.0]
    return {
        "kind": kind,
        "loc": loc,
        "scale": scale,
        "m": m,
        "texture": obj.get("texture") or "Solid",
        "color": (float(col[0]), float(col[1]), float(col[2])),
        "roughness": max(0.05, min(1.0, float(obj.get("roughness") or 0.3))),
    }


def _intersect_obj(ro, rd, obj):
    kind = obj["kind"]
    loc = obj["loc"]
    scale = obj["scale"]
    m = obj["m"]

    # Transform ray into object local space
    dro = (ro[0] - loc[0], ro[1] - loc[1], ro[2] - loc[2])
    lro = _mat_t_vec(m, dro)
    lrd = _mat_t_vec(m, rd)
    sro = (lro[0] / scale[0], lro[1] / scale[1], lro[2] / scale[2])
    srd = (lrd[0] / scale[0], lrd[1] / scale[1], lrd[2] / scale[2])

    if kind in ("sphere", "light"):
        rad = 0.25 if kind == "light" else 0.85
        a = _dot(srd, srd)
        b = 2.0 * _dot(sro, srd)
        c = _dot(sro, sro) - rad * rad
        disc = b * b - 4.0 * a * c
        if disc < 0.0:
            return None
        t = (-b - math.sqrt(disc)) / (2.0 * a)
        if t <= 0.01:
            return None
        lp = _add(sro, _mul(srd, t))
        ln = _norm((lp[0] / scale[0], lp[1] / scale[1], lp[2] / scale[2]))
        wn = _norm(_mat_vec(m, ln))
        u = 0.5 + math.atan2(lp[1], lp[0]) / (2.0 * math.pi)
        v = 0.5 - math.asin(max(-1.0, min(1.0, lp[2] / rad))) / math.pi
        return (t, wn, u, v)

    # Cube: axis-aligned box [-0.75, 0.75]^3 in scaled local space
    half = 0.75
    tmin, tmax = -1e9, 1e9
    hit_axis = 0
    hit_sign = 1.0
    for axis in range(3):
        d = srd[axis]
        o = sro[axis]
        if abs(d) < 1e-8:
            if o < -half or o > half:
                return None
            continue
        t1 = (-half - o) / d
        t2 = (half - o) / d
        sgn = -1.0
        if t1 > t2:
            t1, t2 = t2, t1
            sgn = 1.0
        if t1 > tmin:
            tmin = t1
            hit_axis = axis
            hit_sign = sgn
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    if tmin <= 0.01:
        return None
    lp = _add(sro, _mul(srd, tmin))
    ln_raw = [0.0, 0.0, 0.0]
    ln_raw[hit_axis] = hit_sign / scale[hit_axis]
    wn = _norm(_mat_vec(m, tuple(ln_raw)))
    if hit_axis == 0:
        u, v = lp[1] + 0.5, lp[2] + 0.5
    elif hit_axis == 1:
        u, v = lp[0] + 0.5, lp[2] + 0.5
    else:
        u, v = lp[0] + 0.5, lp[1] + 0.5
    return (tmin, wn, u, v)


def _camera_basis(cam_mode):
    if cam_mode == "front":
        cam_pos = (0.0, -7.2, 1.4)
        target = (0.0, 0.0, 0.9)
        up_hint = (0.0, 0.0, 1.0)
    elif cam_mode == "top":
        cam_pos = (0.0, -0.05, 8.2)
        target = (0.0, 0.0, 0.0)
        up_hint = (0.0, 1.0, 0.0)
    else:
        cam_pos = (4.6, -5.6, 3.4)
        target = (-0.3, 0.1, 0.8)
        up_hint = (0.0, 0.0, 1.0)
    fwd = _norm(_sub(target, cam_pos))
    right = _norm(_cross(fwd, up_hint))
    up = _cross(right, fwd)
    return cam_pos, fwd, right, up


def _project_pt(pt, cam_pos, fwd, right, up):
    d = (pt[0] - cam_pos[0], pt[1] - cam_pos[1], pt[2] - cam_pos[2])
    z = _dot(d, fwd)
    if z <= 0.15:
        return None
    aspect = _W / _H
    fov_scale = 0.62
    sx = _dot(d, right) / (z * aspect * fov_scale)
    sy = _dot(d, up) / (z * fov_scale)
    px = (sx + 1.0) * 0.5 * _W
    py = (1.0 - sy) * 0.5 * _H
    return (px, py, z)


def _draw_line(rgb, x0, y0, x1, y1, col):
    ix0, iy0, ix1, iy1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    dx = abs(ix1 - ix0)
    dy = abs(iy1 - iy0)
    sx = 1 if ix0 < ix1 else -1
    sy = 1 if iy0 < iy1 else -1
    err = dx - dy
    r, g, b = col
    steps = dx + dy + 1
    for _ in range(steps):
        if 0 <= ix0 < _W and 0 <= iy0 < _H:
            off = (iy0 * _W + ix0) * 3
            rgb[off] = r
            rgb[off + 1] = g
            rgb[off + 2] = b
        if ix0 == ix1 and iy0 == iy1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            ix0 += sx
        if e2 < dx:
            err += dx
            iy0 += sy


def _draw_bg_and_grid(rgb, cam_pos, fwd, right, up):
    # Sky + floor gradient
    for py in range(_H):
        sy = (1.0 - 2.0 * (py + 0.5) / _H) * 0.62
        rd_z = fwd[2] + up[2] * sy
        if rd_z < -0.02:
            cr, cg, cb = 40, 42, 46
        else:
            t = max(0.0, min(1.0, 0.5 * (rd_z + 0.2)))
            cr = int((0.11 + 0.09 * (1.0 - t)) * 255)
            cg = int((0.12 + 0.10 * (1.0 - t)) * 255)
            cb = int((0.15 + 0.12 * (1.0 - t)) * 255)
        row_off = py * _W * 3
        for px in range(_W):
            off = row_off + px * 3
            rgb[off] = cr
            rgb[off + 1] = cg
            rgb[off + 2] = cb
    # Ground grid lines (-5..5)
    for g in range(-5, 6):
        col_x = (135, 60, 60) if g == 0 else (66, 68, 74)
        col_y = (58, 130, 70) if g == 0 else (66, 68, 74)
        p0 = _project_pt((-5.0, float(g), 0.0), cam_pos, fwd, right, up)
        p1 = _project_pt((5.0, float(g), 0.0), cam_pos, fwd, right, up)
        if p0 and p1:
            _draw_line(rgb, p0[0], p0[1], p1[0], p1[1], col_x)
        q0 = _project_pt((float(g), -5.0, 0.0), cam_pos, fwd, right, up)
        q1 = _project_pt((float(g), 5.0, 0.0), cam_pos, fwd, right, up)
        if q0 and q1:
            _draw_line(rgb, q0[0], q0[1], q1[0], q1[1], col_y)


def _obj_world_pt(obj, lx, ly, lz):
    sx, sy, sz = obj["scale"]
    vx, vy, vz = _mat_vec(obj["m"], (lx * sx, ly * sy, lz * sz))
    loc = obj["loc"]
    return (loc[0] + vx, loc[1] + vy, loc[2] + vz)


_CUBE_VERTS = [
    (-0.75, -0.75, -0.75), (0.75, -0.75, -0.75), (0.75, 0.75, -0.75), (-0.75, 0.75, -0.75),
    (-0.75, -0.75,  0.75), (0.75, -0.75,  0.75), (0.75, 0.75,  0.75), (-0.75, 0.75,  0.75),
]
_CUBE_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
]
_CUBE_FACES = [
    ((0, 3, 2, 1), (0.0, 0.0, -1.0)),
    ((4, 5, 6, 7), (0.0, 0.0, 1.0)),
    ((0, 1, 5, 4), (0.0, -1.0, 0.0)),
    ((2, 3, 7, 6), (0.0, 1.0, 0.0)),
    ((0, 4, 7, 3), (-1.0, 0.0, 0.0)),
    ((1, 2, 6, 5), (1.0, 0.0, 0.0)),
]


def _render_wireframe(objs, sel_idx, cam_pos, fwd, right, up):
    rgb = bytearray(_W * _H * 3)
    _draw_bg_and_grid(rgb, cam_pos, fwd, right, up)
    for idx, obj in enumerate(objs):
        col = (245, 145, 45) if idx == sel_idx else ((255, 240, 150) if obj["kind"] == "light" else (200, 210, 224))
        kind = obj["kind"]
        if kind == "cube":
            pts = [_project_pt(_obj_world_pt(obj, *v), cam_pos, fwd, right, up) for v in _CUBE_VERTS]
            for a, b in _CUBE_EDGES:
                if pts[a] and pts[b]:
                    _draw_line(rgb, pts[a][0], pts[a][1], pts[b][0], pts[b][1], col)
        elif kind == "light":
            r = 0.28
            oct_pts = [
                _project_pt(_obj_world_pt(obj, r, 0, 0), cam_pos, fwd, right, up),
                _project_pt(_obj_world_pt(obj, -r, 0, 0), cam_pos, fwd, right, up),
                _project_pt(_obj_world_pt(obj, 0, r, 0), cam_pos, fwd, right, up),
                _project_pt(_obj_world_pt(obj, 0, -r, 0), cam_pos, fwd, right, up),
                _project_pt(_obj_world_pt(obj, 0, 0, r), cam_pos, fwd, right, up),
                _project_pt(_obj_world_pt(obj, 0, 0, -r), cam_pos, fwd, right, up),
            ]
            for a, b in ((0, 1), (2, 3), (4, 5), (0, 4), (1, 4), (2, 4), (3, 4), (0, 5), (1, 5), (2, 5), (3, 5)):
                if oct_pts[a] and oct_pts[b]:
                    _draw_line(rgb, oct_pts[a][0], oct_pts[a][1], oct_pts[b][0], oct_pts[b][1], col)
        else:
            rad = 0.85
            segs = 20
            for plane in range(3):
                ring = []
                for k in range(segs + 1):
                    ang = 2.0 * math.pi * k / segs
                    ca, sa = math.cos(ang) * rad, math.sin(ang) * rad
                    if plane == 0:
                        lp = (ca, sa, 0.0)
                    elif plane == 1:
                        lp = (ca, 0.0, sa)
                    else:
                        lp = (0.0, ca, sa)
                    ring.append(_project_pt(_obj_world_pt(obj, *lp), cam_pos, fwd, right, up))
                for k in range(segs):
                    if ring[k] and ring[k + 1]:
                        _draw_line(rgb, ring[k][0], ring[k][1], ring[k + 1][0], ring[k + 1][1], col)
    return rgb


def _fill_tri(rgb, zbuf, p0, p1, p2, col):
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    area = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
    if abs(area) < 1e-4:
        return
    minx = max(0, int(math.floor(min(x0, x1, x2))))
    maxx = min(_W - 1, int(math.ceil(max(x0, x1, x2))))
    miny = max(0, int(math.floor(min(y0, y1, y2))))
    maxy = min(_H - 1, int(math.ceil(max(y0, y1, y2))))
    inv_area = 1.0 / area
    r, g, b = col
    for py in range(miny, maxy + 1):
        py_c = py + 0.5
        row_z = py * _W
        for px in range(minx, maxx + 1):
            px_c = px + 0.5
            w0 = ((x1 - px_c) * (y2 - py_c) - (y1 - py_c) * (x2 - px_c)) * inv_area
            w1 = ((x2 - px_c) * (y0 - py_c) - (y2 - py_c) * (x0 - px_c)) * inv_area
            w2 = 1.0 - w0 - w1
            if w0 >= -1e-4 and w1 >= -1e-4 and w2 >= -1e-4:
                z = w0 * z0 + w1 * z1 + w2 * z2
                zi = row_z + px
                if z < zbuf[zi]:
                    zbuf[zi] = z
                    off = zi * 3
                    rgb[off] = r
                    rgb[off + 1] = g
                    rgb[off + 2] = b


def _render_solid(objs, sel_idx, cam_pos, fwd, right, up):
    rgb = bytearray(_W * _H * 3)
    _draw_bg_and_grid(rgb, cam_pos, fwd, right, up)
    zbuf = [1e9] * (_W * _H)
    key_dir = _norm((0.5, -0.6, 0.8))

    for idx, obj in enumerate(objs):
        kind = obj["kind"]
        base = obj["color"]
        is_sel = (idx == sel_idx)
        if kind == "cube":
            pts = [_project_pt(_obj_world_pt(obj, *v), cam_pos, fwd, right, up) for v in _CUBE_VERTS]
            for f_verts, ln in _CUBE_FACES:
                wn = _norm(_mat_vec(obj["m"], ln))
                if _dot(wn, fwd) > 0.25:
                    continue
                shade = 0.28 + 0.72 * max(0.0, _dot(wn, key_dir))
                if is_sel:
                    col = (
                        min(255, int((base[0] * shade * 0.88 + 0.12) * 255)),
                        min(255, int((base[1] * shade * 0.88 + 0.06) * 255)),
                        min(255, int(base[2] * shade * 0.88 * 255)),
                    )
                else:
                    col = (int(base[0] * shade * 255), int(base[1] * shade * 255), int(base[2] * shade * 255))
                p0, p1, p2, p3 = pts[f_verts[0]], pts[f_verts[1]], pts[f_verts[2]], pts[f_verts[3]]
                if p0 and p1 and p2:
                    _fill_tri(rgb, zbuf, p0, p1, p2, col)
                if p0 and p2 and p3:
                    _fill_tri(rgb, zbuf, p0, p2, p3, col)
            if is_sel:
                for a, b in _CUBE_EDGES:
                    if pts[a] and pts[b]:
                        _draw_line(rgb, pts[a][0], pts[a][1], pts[b][0], pts[b][1], (245, 145, 45))
        else:
            cp = _project_pt(obj["loc"], cam_pos, fwd, right, up)
            if cp is None:
                continue
            cx, cy, cz = cp
            rad_w = (0.25 if kind == "light" else 0.85) * max(obj["scale"])
            prx = max(4.0, (rad_w / (cz * (_W / _H) * 0.62)) * 0.5 * _W)
            pry = max(4.0, (rad_w / (cz * 0.62)) * 0.5 * _H)
            minx = max(0, int(cx - prx))
            maxx = min(_W - 1, int(cx + prx))
            miny = max(0, int(cy - pry))
            maxy = min(_H - 1, int(cy + pry))
            for py in range(miny, maxy + 1):
                ny = -(py + 0.5 - cy) / pry
                row_z = py * _W
                for px in range(minx, maxx + 1):
                    nx = (px + 0.5 - cx) / prx
                    r2 = nx * nx + ny * ny
                    if r2 <= 1.0:
                        nz = math.sqrt(max(0.0, 1.0 - r2))
                        z = cz - nz * rad_w
                        zi = row_z + px
                        if z < zbuf[zi]:
                            zbuf[zi] = z
                            off = zi * 3
                            if kind == "light":
                                rgb[off] = min(255, int(base[0] * 255))
                                rgb[off + 1] = min(255, int(base[1] * 255))
                                rgb[off + 2] = min(255, int(base[2] * 255))
                            else:
                                wn = (
                                    right[0] * nx + up[0] * ny - fwd[0] * nz,
                                    right[1] * nx + up[1] * ny - fwd[1] * nz,
                                    right[2] * nx + up[2] * ny - fwd[2] * nz,
                                )
                                shade = 0.25 + 0.75 * max(0.0, _dot(wn, key_dir))
                                cr, cg, cb = base[0] * shade, base[1] * shade, base[2] * shade
                                if is_sel and r2 > 0.84:
                                    cr, cg, cb = 0.96, 0.57, 0.18
                                rgb[off] = min(255, int(cr * 255))
                                rgb[off + 1] = min(255, int(cg * 255))
                                rgb[off + 2] = min(255, int(cb * 255))
    return rgb


def _render_scene(data):
    cam_pos, fwd, right, up = _camera_basis(data.get("camera") or "three_quarter")
    raw_objs = data.get("objects") or []
    objs = [_prepare_obj(o) for o in raw_objs]
    sel_idx = int(data.get("selected_index") or 0)
    mode = data.get("render_mode") or "solid"

    if mode == "wireframe":
        rgb = _render_wireframe(objs, sel_idx, cam_pos, fwd, right, up)
    elif mode != "raytraced":
        rgb = _render_solid(objs, sel_idx, cam_pos, fwd, right, up)
    else:
        lights = [o for o in objs if o["kind"] == "light"]
        if not lights:
            lights = [{"loc": (3.0, -3.0, 5.0), "color": (1.0, 0.96, 0.9)}]

        rw, rh = _W // 2, _H // 2
        aspect = rw / rh
        fov_scale = 0.62
        small = bytearray(rw * rh * 3)

        for py in range(rh):
            sy = (1.0 - 2.0 * (py + 0.5) / rh) * fov_scale
            for px in range(rw):
                sx = (2.0 * (px + 0.5) / rw - 1.0) * aspect * fov_scale
                rd = _norm((
                    fwd[0] + right[0] * sx + up[0] * sy,
                    fwd[1] + right[1] * sx + up[1] * sy,
                    fwd[2] + right[2] * sx + up[2] * sy,
                ))

                best_t = 1e9
                best_hit = None
                best_idx = -1
                for idx, obj in enumerate(objs):
                    h = _intersect_obj(cam_pos, rd, obj)
                    if h is not None and h[0] < best_t:
                        best_t = h[0]
                        best_hit = h
                        best_idx = idx

                # Ground plane z = 0
                ground_t = None
                if abs(rd[2]) > 1e-5:
                    gt = -cam_pos[2] / rd[2]
                    if 0.01 < gt < best_t:
                        ground_t = gt

                if best_hit is not None and (ground_t is None or best_t < ground_t):
                    t, n, u, v = best_hit
                    obj = objs[best_idx]
                    hp = _add(cam_pos, _mul(rd, t))
                    base = obj["color"]
                    if obj["kind"] == "light":
                        cr, cg, cb = base
                    else:
                        alb = _sample_texture(obj["texture"], u, v, base)
                        rough = obj["roughness"]
                        shininess = max(4.0, 96.0 * (1.0 - rough) ** 2 + 4.0)
                        cr = alb[0] * 0.22
                        cg = alb[1] * 0.22
                        cb = alb[2] * 0.22
                        view_dir = _mul(rd, -1.0)
                        for lt in lights:
                            lpos = lt["loc"]
                            lcol = lt["color"]
                            ldir = _sub(lpos, hp)
                            dist = math.sqrt(_dot(ldir, ldir)) + 1e-6
                            ldir = (ldir[0] / dist, ldir[1] / dist, ldir[2] / dist)
                            diff = max(0.0, _dot(n, ldir))
                            atten = min(1.2, 24.0 / (dist * dist + 10.0))
                            half_v = _norm(_add(ldir, view_dir))
                            spec = (max(0.0, _dot(n, half_v)) ** shininess) * (1.1 - rough * 0.8)
                            cr += (alb[0] * diff + spec * 0.65) * lcol[0] * atten
                            cg += (alb[1] * diff + spec * 0.65) * lcol[1] * atten
                            cb += (alb[2] * diff + spec * 0.65) * lcol[2] * atten
                        if best_idx == sel_idx:
                            rim = (1.0 - abs(_dot(n, view_dir))) ** 2.2
                            cr += 0.95 * rim * 0.55
                            cg += 0.52 * rim * 0.55
                            cb += 0.12 * rim * 0.55
                elif ground_t is not None:
                    hp = _add(cam_pos, _mul(rd, ground_t))
                    fade = math.exp(-0.045 * (hp[0] * hp[0] + hp[1] * hp[1]))
                    gx = abs(hp[0] - round(hp[0]))
                    gy = abs(hp[1] - round(hp[1]))
                    is_axis_x = abs(hp[1]) < 0.035
                    is_axis_y = abs(hp[0]) < 0.035
                    is_grid = gx < 0.025 or gy < 0.025
                    shadow = 1.0
                    lpos = lights[0]["loc"]
                    sdir = _norm(_sub(lpos, hp))
                    s_orig = _add(hp, (0.0, 0.0, 0.01))
                    for obj in objs:
                        if obj["kind"] == "light":
                            continue
                        if _intersect_obj(s_orig, sdir, obj) is not None:
                            shadow = 0.42
                            break
                    bg = 0.15 + 0.06 * fade
                    if is_axis_x:
                        cr, cg, cb = (0.55 * fade + bg * (1 - fade), 0.22, 0.22)
                    elif is_axis_y:
                        cr, cg, cb = (0.22, 0.52 * fade + bg * (1 - fade), 0.26)
                    elif is_grid:
                        gval = 0.27 * fade + bg * (1 - fade)
                        cr, cg, cb = (gval * shadow, gval * shadow, gval * shadow)
                    else:
                        cr, cg, cb = (bg * shadow, (bg + 0.01) * shadow, (bg + 0.02) * shadow)
                else:
                    t_sky = max(0.0, min(1.0, 0.5 * (rd[2] + 0.2)))
                    cr = 0.11 + 0.09 * (1.0 - t_sky)
                    cg = 0.12 + 0.10 * (1.0 - t_sky)
                    cb = 0.15 + 0.12 * (1.0 - t_sky)

                off = (py * rw + px) * 3
                small[off] = max(0, min(255, int(cr * 255)))
                small[off + 1] = max(0, min(255, int(cg * 255)))
                small[off + 2] = max(0, min(255, int(cb * 255)))

        rgb = bytearray(_W * _H * 3)
        for py in range(rh):
            srow = py * rw * 3
            drow0 = (py * 2) * _W * 3
            drow1 = (py * 2 + 1) * _W * 3
            for px in range(rw):
                soff = srow + px * 3
                r, g, b = small[soff], small[soff + 1], small[soff + 2]
                doff = px * 6
                rgb[drow0 + doff] = rgb[drow0 + doff + 3] = rgb[drow1 + doff] = rgb[drow1 + doff + 3] = r
                rgb[drow0 + doff + 1] = rgb[drow0 + doff + 4] = rgb[drow1 + doff + 1] = rgb[drow1 + doff + 4] = g
                rgb[drow0 + doff + 2] = rgb[drow0 + doff + 5] = rgb[drow1 + doff + 2] = rgb[drow1 + doff + 5] = b

    seq = int(data.get("render_seq") or 0) + 1
    data["render_seq"] = seq
    rel = f"render_{seq}.png"
    app.storage.write_png_rgb(rel, _W, _H, bytes(rgb))
    data["viewport_src"] = f"storage://{rel}"


def _sync_selected_to_fields(data):
    objs = data.get("objects") or []
    if not objs:
        data["selected_index"] = -1
        data["selected_name"] = "No object selected"
        data["status_text"] = "0 objects · Add a sphere, cube, or light"
        return
    idx = max(0, min(len(objs) - 1, int(data.get("selected_index") or 0)))
    data["selected_index"] = idx
    o = objs[idx]
    data["selected_name"] = o.get("name") or "Object"
    data["selected_kind"] = o.get("kind") or "sphere"
    data["selected_loc"] = list(o.get("loc") or [0.0, 0.0, 0.0])
    data["selected_rot"] = list(o.get("rot") or [0.0, 0.0, 0.0])
    data["selected_scale"] = list(o.get("scale") or [1.0, 1.0, 1.0])
    data["selected_texture"] = o.get("texture") or "Solid"
    data["selected_color"] = list(o.get("color") or [0.8, 0.8, 0.8, 1.0])
    data["selected_roughness"] = float(o.get("roughness") or 0.3)
    n_lights = sum(1 for x in objs if x.get("kind") == "light")
    n_meshes = len(objs) - n_lights
    mode_lbl = {"wireframe": "Wireframe", "solid": "Fast Solid", "raytraced": "Raytraced"}.get(
        data.get("render_mode") or "solid", "Fast Solid"
    )
    data["status_text"] = f"{mode_lbl} · {n_meshes} objects · {n_lights} light(s) · Selected: {o.get('name')}"


@app.on("set_render_mode")
def set_render_mode(ctx, data):
    mode = ctx.get("mode")
    if mode in ("wireframe", "solid", "raytraced"):
        data["render_mode"] = mode
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("select_object")
def select_object(ctx, data):
    if "index" in ctx and ctx["index"] is not None:
        data["selected_index"] = int(ctx["index"])
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("add_object")
def add_object(ctx, data):
    kind = str(ctx.get("kind") or "sphere")
    objs = list(data.get("objects") or [])
    n = len(objs) + 1
    if kind == "cube":
        item = {
            "id": f"obj_{n}",
            "label": f"Cube {n} (cube)",
            "name": f"Cube {n}",
            "kind": "cube",
            "icon": "MESH_CUBE",
            "loc": [round(((n % 3) - 1) * 1.4, 2), round((n % 2) * 0.9, 2), 0.75],
            "rot": [0.0, 0.0, 15.0 * n],
            "scale": [0.9, 0.9, 0.9],
            "texture": "Grid",
            "color": [0.35, 0.78, 0.56, 1.0],
            "roughness": 0.35,
        }
    elif kind == "light":
        item = {
            "id": f"obj_{n}",
            "label": f"Light {n} (light)",
            "name": f"Light {n}",
            "kind": "light",
            "icon": "LIGHT",
            "loc": [-2.8, -2.5, 4.2],
            "rot": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "texture": "Solid",
            "color": [0.85, 0.92, 1.0, 1.0],
            "roughness": 0.1,
        }
    else:
        item = {
            "id": f"obj_{n}",
            "label": f"Sphere {n} (sphere)",
            "name": f"Sphere {n}",
            "kind": "sphere",
            "icon": "MESH_UVSPHERE",
            "loc": [round(((n % 3) - 1) * 1.5, 2), round(-0.5 + (n % 2), 2), 0.85],
            "rot": [0.0, 0.0, 0.0],
            "scale": [0.9, 0.9, 0.9],
            "texture": "Marble",
            "color": [0.86, 0.42, 0.62, 1.0],
            "roughness": 0.25,
        }
    objs.append(item)
    data["objects"] = objs
    data["selected_index"] = len(objs) - 1
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("delete_selected")
def delete_selected(ctx, data):
    objs = list(data.get("objects") or [])
    idx = int(data.get("selected_index") or 0)
    if 0 <= idx < len(objs):
        objs.pop(idx)
    data["objects"] = objs
    data["selected_index"] = max(0, min(len(objs) - 1, idx))
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("reset_scene")
def reset_scene(ctx, data):
    data["objects"] = [dict(o) for o in _DEFAULT_OBJECTS]
    data["selected_index"] = 0
    data["camera"] = "three_quarter"
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("set_camera")
def set_camera(ctx, data):
    cam = ctx.get("camera")
    if cam in ("three_quarter", "front", "top"):
        data["camera"] = cam
    _render_scene(data)


@app.on("update_transform")
def update_transform(ctx, data):
    prop = ctx.get("prop")
    val = ctx.get("value")
    objs = list(data.get("objects") or [])
    idx = int(data.get("selected_index") or 0)
    if 0 <= idx < len(objs) and prop in ("loc", "rot", "scale") and isinstance(val, list) and len(val) == 3:
        objs[idx] = dict(objs[idx])
        objs[idx][prop] = [float(x) for x in val]
        data["objects"] = objs
    _sync_selected_to_fields(data)
    _render_scene(data)


@app.on("update_material")
def update_material(ctx, data):
    prop = ctx.get("prop")
    val = ctx.get("value")
    objs = list(data.get("objects") or [])
    idx = int(data.get("selected_index") or 0)
    if 0 <= idx < len(objs) and prop in ("texture", "color", "roughness") and val is not None:
        objs[idx] = dict(objs[idx])
        objs[idx][prop] = float(val) if prop == "roughness" else val
        data["objects"] = objs
    _sync_selected_to_fields(data)
    _render_scene(data)
'''

_3D_DESIGNER_TEST = '''import tempfile, unittest
from pathlib import Path
from a2ui_app import TrackedDict, app
import main

class Designer3DTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.storage.root = Path(self.tmp.name)
        self.data = TrackedDict({
            "camera": "three_quarter",
            "render_seq": 0,
            "viewport_src": "storage://render_0.png",
            "status_text": "",
            "selected_index": 0,
            "selected_name": "Hero Sphere",
            "selected_kind": "sphere",
            "selected_loc": [0.0, 0.0, 0.9],
            "selected_rot": [0.0, 0.0, 0.0],
            "selected_scale": [1.0, 1.0, 1.0],
            "selected_texture": "Checker",
            "selected_color": [0.92, 0.48, 0.20, 1.0],
            "selected_roughness": 0.25,
            "objects": [dict(o) for o in main._DEFAULT_OBJECTS],
        }, "", app._sink)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_transform_material_and_render(self):
        main.add_object({"kind": "cube"}, self.data)
        self.assertEqual(len(self.data["objects"]), 4)
        self.assertTrue(self.data["viewport_src"].startswith("storage://render_"))
        png_name = self.data["viewport_src"].split("storage://", 1)[1]
        self.assertTrue((Path(self.tmp.name) / png_name).is_file())
        main.update_transform({"prop": "loc", "value": [1.2, 0.5, 1.0]}, self.data)
        self.assertEqual(self.data["objects"][-1]["loc"], [1.2, 0.5, 1.0])
        main.update_material({"prop": "texture", "value": "Marble"}, self.data)
        self.assertEqual(self.data["objects"][-1]["texture"], "Marble")
        main.delete_selected({}, self.data)
        self.assertEqual(len(self.data["objects"]), 3)

if __name__ == "__main__":
    unittest.main()
'''

SPECS = {
    "project-tracker": (_PROJECT_TRACKER_MAIN, _PROJECT_TRACKER_TEST, "Task tracker with SQLite persistence"),
    "render-farm": (_RENDER_FARM_MAIN, _RENDER_FARM_TEST, "Render queue with streaming job submission and background tick"),
    "synth-patch": (_SYNTH_PATCH_MAIN, _SYNTH_PATCH_TEST, "Modular synthesizer with real-time Web Audio playback"),
    "3d-designer": (_3D_DESIGNER_MAIN, _3D_DESIGNER_TEST, "3D scene studio with spheres, cubes, lights, transforms, and textures"),
}


def _seed_3d_initial_render(rec: AppRecord) -> None:
    """Render render_0.png once at seed time so the viewport opens populated."""
    if (rec.storage_dir / "render_0.png").is_file():
        return
    sdk_dir = str(Path(__file__).resolve().parent / "sdk")
    added_sdk = sdk_dir not in sys.path
    added_be = str(rec.backend_dir) not in sys.path
    if added_sdk:
        sys.path.insert(0, sdk_dir)
    if added_be:
        sys.path.insert(0, str(rec.backend_dir))
    try:
        from a2ui_app import app as sdk_app  # type: ignore
        import main as designer_main  # type: ignore

        sdk_app.storage.root = rec.storage_dir
        state = {"camera": "three_quarter", "render_mode": "solid", "render_seq": -1, "selected_index": 0,
                 "objects": [dict(o) for o in designer_main._DEFAULT_OBJECTS]}
        designer_main._render_scene(state)
    finally:
        if added_be and str(rec.backend_dir) in sys.path:
            sys.path.remove(str(rec.backend_dir))
        if added_sdk and sdk_dir in sys.path:
            sys.path.remove(sdk_dir)


def seed_builtin_apps(base_dir: Path | None = None) -> list[AppRecord]:
    base = base_dir or apps_dir()
    out: list[AppRecord] = []
    for sid, (main_src, test_src, summary) in SPECS.items():
        app_dir = base / sid
        if (app_dir / "app.json").exists():
            rec = AppRecord(app_dir)
            if sid == "3d-designer":
                _seed_3d_initial_render(rec)
            out.append(rec)
            continue
        if sid == "3d-designer":
            sc = _3D_DESIGNER_SPEC
        else:
            sc_path = REPO / "showcases" / f"{sid}.json"
            if not sc_path.exists():
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
        if sid == "3d-designer":
            _seed_3d_initial_render(rec)
        out.append(rec)
    return out
