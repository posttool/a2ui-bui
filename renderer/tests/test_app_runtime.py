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
