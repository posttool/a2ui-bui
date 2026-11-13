# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""AppRuntime tests: handler patches, streaming yields, sqlite persistence,
runtime LLM ask + budget, and built-in reference apps."""

import json
import time

from a2ui_bui.apps import create_app, get_app
from a2ui_bui.apps.builtins import seed_builtin_apps
from a2ui_bui.apps.runtime import AppRuntime, _set_pointer


def _sample_messages():
    return [
        {"version": "1.0", "createSurface": {"surfaceId": "main", "catalogId": "https://a2ui-bui-demo.local/catalogs/bui/v1/catalog.json"}},
        {"version": "1.0", "updateDataModel": {"surfaceId": "main", "value": {"count": 0, "steps": 0, "summary": ""}}},
        {"version": "1.0", "updateComponents": {"surfaceId": "main", "components": [
            {"id": "root", "component": "Column", "children": ["btn"]},
            {"id": "btn", "component": "Button", "text": "Go", "action": {"event": {"name": "inc"}}},
        ]}},
    ]


def test_handler_patches_streaming_and_runtime_llm(tmp_path):
    rec = create_app(title="Counter", messages=_sample_messages(), base_dir=tmp_path, max_runtime_calls=2)
    rec.main_py.write_text(
        "from a2ui_app import app\n"
        "@app.on('inc')\n"
        "def inc(ctx, data):\n"
        "    data['count'] = (data.get('count') or 0) + 1\n"
        "    app.db.execute('CREATE TABLE IF NOT EXISTS hits(n INT)')\n"
        "    app.db.execute('INSERT INTO hits VALUES (?)', (data['count'],))\n"
        "@app.on('stream_work')\n"
        "def stream_work(ctx, data):\n"
        "    for i in (1, 2, 3):\n"
        "        data['steps'] = i\n"
        "        yield\n"
        "@app.on('summarize')\n"
        "def summarize(ctx, data):\n"
        "    data['summary'] = app.agent.ask('summarize')\n"
    )

    state = rec.load_state()
    batches = []

    def dispatch(msgs):
        batches.append(msgs)
        for m in msgs:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(state, ud.get("path") or "/", ud.get("value"))

    rt = AppRuntime(
        rec,
        dispatch_ui=dispatch,
        get_data=lambda sid="main": state,
        llm_ask=lambda prompt, schema=None: f"mock:{prompt}",
    )
    rt.start()
    try:
        assert set(rt.handlers) == {"inc", "stream_work", "summarize"}
        r1 = rt.handle_action_sync({"action": {"name": "inc", "surfaceId": "main", "context": {}}})
        assert r1["source"] == "code" and r1["ok"]
        assert state["count"] == 1

        batches.clear()
        r2 = rt.handle_action_sync({"action": {"name": "stream_work", "surfaceId": "main", "context": {}}})
        assert r2["ok"] and len(batches) >= 3
        assert state["steps"] == 3

        # Runtime LLM ask + budget enforcement (max_runtime_calls=2)
        r3 = rt.handle_action_sync({"action": {"name": "summarize", "surfaceId": "main", "context": {}}})
        assert r3["ok"] and state["summary"] == "mock:summarize"
        r4 = rt.handle_action_sync({"action": {"name": "summarize", "surfaceId": "main", "context": {}}})
        assert r4["ok"]
    finally:
        rt.stop()

    # Persisted state survives restart
    reloaded = get_app(rec.id, base_dir=tmp_path)
    assert reloaded.load_state()["count"] == 1
    assert (reloaded.storage_dir / "app.db").exists()


def test_builtin_apps_work_in_sandbox(tmp_path):
    apps = seed_builtin_apps(base_dir=tmp_path)
    by_id = {a.id: a for a in apps}
    assert "project-tracker" in by_id and "render-farm" in by_id

    pt = by_id["project-tracker"]
    state = pt.load_state()

    def dispatch(msgs):
        for m in msgs:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(state, ud.get("path") or "/", ud.get("value"))

    rt = AppRuntime(pt, dispatch_ui=dispatch, get_data=lambda sid="main": state)
    rt.start()
    try:
        before = len(state["tasks"])
        res = rt.handle_action_sync({"action": {"name": "task_add", "surfaceId": "main", "context": {"title": "Ship it"}}})
        assert res["source"] == "code" and res["ok"]
        assert len(state["tasks"]) == before + 1
        assert state["tasks"][-1]["title"] == "Ship it"
    finally:
        rt.stop()


def test_synth_patch_and_3d_designer_builtins(tmp_path):
    apps = seed_builtin_apps(base_dir=tmp_path)
    by_id = {a.id: a for a in apps}
    assert "synth-patch" in by_id and "3d-designer" in by_id

    # 1) Synth patch emits WAV audio and updates spectrum
    sp = by_id["synth-patch"]
    sp_state = sp.load_state()
    events = []

    def sp_dispatch(msgs):
        for m in msgs:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(sp_state, ud.get("path") or "/", ud.get("value"))

    rt_sp = AppRuntime(sp, dispatch_ui=sp_dispatch, get_data=lambda sid="main": sp_state, on_event=events.append)
    rt_sp.start()
    try:
        res = rt_sp.handle_action_sync({"action": {"name": "note_on", "surfaceId": "main", "context": {"note": "C3", "bpm": 128}}})
        assert res["ok"] and res["source"] == "code"
        audio_evs = [e for e in events if e.get("t") == "audio"]
        assert len(audio_evs) == 1
        assert audio_evs[0]["clips"][0]["mime"] == "audio/wav"
        assert len(sp_state["spectrum"]) == 16
    finally:
        rt_sp.stop()

    # 2) 3D Designer renders PNG viewport and supports add/transform/texture
    d3 = by_id["3d-designer"]
    assert (d3.storage_dir / "render_0.png").is_file()
    d3_state = d3.load_state()

    def d3_dispatch(msgs):
        for m in msgs:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(d3_state, ud.get("path") or "/", ud.get("value"))

    rt_3d = AppRuntime(d3, dispatch_ui=d3_dispatch, get_data=lambda sid="main": d3_state)
    rt_3d.start()
    try:
        r1 = rt_3d.handle_action_sync({"action": {"name": "add_object", "surfaceId": "main", "context": {"kind": "cube"}}})
        assert r1["ok"] and len(d3_state["objects"]) == 4
        assert d3_state["viewport_src"].startswith("storage://render_")
        rel = d3_state["viewport_src"].split("storage://", 1)[1]
        assert (d3.storage_dir / rel).is_file()

        r2 = rt_3d.handle_action_sync({"action": {"name": "update_transform", "surfaceId": "main", "context": {"prop": "loc", "value": [1.5, 0.2, 0.9]}}})
        assert r2["ok"] and d3_state["objects"][-1]["loc"] == [1.5, 0.2, 0.9]

        r3 = rt_3d.handle_action_sync({"action": {"name": "update_material", "surfaceId": "main", "context": {"prop": "texture", "value": "Marble"}}})
        assert r3["ok"] and d3_state["objects"][-1]["texture"] == "Marble"
    finally:
        rt_3d.stop()


def test_rapid_slider_actions_are_coalesced(tmp_path):
    msgs = [
        {"version": "1.0", "createSurface": {"surfaceId": "main", "catalogId": "x", "sendDataModel": True}},
        {"version": "1.0", "updateDataModel": {"surfaceId": "main", "value": {"roughness": 0.1, "calls": 0}}},
        {"version": "1.0", "updateComponents": {"surfaceId": "main", "components": [
            {"id": "root", "component": "NumberSlider", "label": "R", "value": {"@path": "/roughness"},
             "min": 0, "max": 1, "action": {"event": {"name": "set_rough", "context": {"prop": "roughness", "value": {"@path": "/roughness"}}}}}
        ]}},
    ]
    rec = create_app(title="SliderBurst", messages=msgs, base_dir=tmp_path)
    rec.main_py.write_text(
        "import time\nfrom a2ui_app import app\n"
        "@app.on('set_rough')\n"
        "def set_rough(ctx, data):\n"
        "    time.sleep(0.03)\n"
        "    data['roughness'] = ctx.get('value')\n"
        "    data['calls'] = (data.get('calls') or 0) + 1\n"
    )
    rec.save_version("v1")
    state = rec.load_state()

    def dispatch(ms):
        for m in ms:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(state, ud.get("path") or "/", ud.get("value"))

    rt = AppRuntime(rec, dispatch_ui=dispatch, get_data=lambda sid="main": state)
    rt.start()
    try:
        for i in range(25):
            val = round(0.1 + i * 0.035, 3)
            rt.submit_action({"action": {"name": "set_rough", "surfaceId": "main", "context": {"prop": "roughness", "value": val}}})
        # Barrier via handle_action_sync ensures the burst has drained.
        rt.handle_action_sync({"action": {"name": "set_rough", "surfaceId": "main", "context": {"prop": "roughness", "value": 0.99}}})
        assert state["roughness"] == 0.99
        assert state["calls"] <= 4, f"expected coalescing, got {state['calls']} calls"
    finally:
        rt.stop()
