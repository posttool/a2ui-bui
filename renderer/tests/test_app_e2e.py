# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""End-to-end headless BUI surface + AppRuntime + persistence across restart."""

from a2ui_bui import BuiRenderer
from a2ui_bui.apps import get_app
from a2ui_bui.apps.builtins import seed_builtin_apps
from a2ui_bui.apps.runtime import AppRuntime
from a2ui_bui.hosts.headless import HeadlessHost


def test_project_tracker_e2e_persists_across_restart(tmp_path):
    seed_builtin_apps(base_dir=tmp_path)

    # First run: mount BUI surface + AppRuntime, trigger task_add
    rec1 = get_app("project-tracker", base_dir=tmp_path)
    r1 = BuiRenderer()
    rt1 = AppRuntime(rec1, dispatch_ui=r1.process, get_data=lambda sid="main": r1.data_model(sid))
    r1.on_action = rt1.submit_action
    rt1.start()
    try:
        r1.process(rec1.messages_with_state())
        h1 = HeadlessHost(r1, (1000, 800))
        h1.frame(full=True)
        before = len(r1.data_model("main")["tasks"])
        res = rt1.handle_action_sync({"action": {"name": "task_add", "surfaceId": "main", "context": {"title": "E2E Task"}}})
        assert res["ok"] and res["source"] == "code"
        h1.frame()
        assert len(r1.data_model("main")["tasks"]) == before + 1
    finally:
        rt1.stop()

    # Second run: new BuiRenderer + AppRuntime restores persisted state.json
    rec2 = get_app("project-tracker", base_dir=tmp_path)
    r2 = BuiRenderer()
    rt2 = AppRuntime(rec2, dispatch_ui=r2.process, get_data=lambda sid="main": r2.data_model(sid))
    rt2.start()
    try:
        r2.process(rec2.messages_with_state())
        h2 = HeadlessHost(r2, (1000, 800))
        h2.frame(full=True)
        titles = [t["title"] for t in r2.data_model("main")["tasks"]]
        assert "E2E Task" in titles
    finally:
        rt2.stop()
