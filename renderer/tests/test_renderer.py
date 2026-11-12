# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""a2ui_bui end to end: A2UI v1.0 messages -> a2ui_core -> real BUI widgets.

Run: ~/a2ui_bui/venv/bin/python -m pytest renderer/tests -q   (from any cwd)
"""

import json
import time
from pathlib import Path

import pytest

from a2ui_bui import BuiRenderer
from a2ui_bui.adapters import REGISTRY
from a2ui_bui.hosts.headless import HeadlessHost
from a2ui_bui.renderer import REPO

SHOWCASES = [s["file"][:-5] for s in json.loads((REPO / "showcases" / "index.json").read_text())["showcases"]]
CATALOG = json.loads((REPO / "bui" / "catalog.json").read_text())


def load(name):
    return json.loads((REPO / "showcases" / f"{name}.json").read_text())


def render(name, size=None):
    sc = load(name)
    r = BuiRenderer()
    r.process(sc["messages"])
    h = HeadlessHost(r, size or (int(sc.get("width") or 900), 900))
    h.frame(full=True)
    return r, h


def find(r, type_, pred=lambda n: True):
    for v in r.views.values():
        for rec in v.records.values():
            if rec.node.type == type_ and pred(rec.node):
                return rec.node, rec.widget
    raise LookupError(type_)


def test_every_catalog_component_has_an_adapter():
    missing = sorted(set(CATALOG["components"]) - set(REGISTRY))
    assert not missing, f"no BUI adapter for {missing}"


@pytest.mark.parametrize("name", SHOWCASES)
def test_showcase_renders_without_errors(name):
    r, h = render(name)
    assert r.views, "no surface"
    assert not r.errors, r.errors[:3]
    png = h.screenshot()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000


def test_toggle_click_writes_data_model_and_fires_v1_action():
    r, h = render("animation")
    node, w = find(r, "Toggle", lambda n: n.component_id == "toggle_86" or True)
    x, y = w.x + w.w // 2, w.y + w.h // 2
    before = r.data_model("main")["playing"]
    h.press(x, y); h.release(x, y); h.frame()
    assert r.data_model("main")["playing"] is (not before)
    a = r.actions[-1]
    assert a["version"] == "1.0" and a["action"]["name"] == "playback_toggle"
    assert a["action"]["context"]["value"] is (not before)


def test_number_field_drag_is_blender_scrubbing_two_way():
    r, h = render("animation")
    node, w = find(r, "NumberField", lambda n: n.props["value"].path == "/frame")
    x, y = w.x + w.w // 2, w.y + w.h // 2
    start = r.data_model("main")["frame"]
    h.press(x, y)
    for i in range(1, 9):
        h.motion(x + 5 * i, y, {"button1": True})
    h.release(x + 40, y); h.frame()
    assert r.data_model("main")["frame"] > start
    assert r.actions and r.actions[-1]["action"]["name"] == "frame_change"


def test_data_model_update_patches_widget_in_place():
    r, h = render("animation")
    node, w = find(r, "NumberField", lambda n: n.props["value"].path == "/frame")
    r.process([{"version": "1.0", "updateDataModel": {"surfaceId": "main", "path": "/frame", "value": 77}}])
    node2, w2 = find(r, "NumberField", lambda n: n.props["value"].path == "/frame")
    assert w2 is w and w.value == 77           # updated, not rebuilt
    assert h.frame(), "expected damaged tiles"


def test_streaming_components_arrive_incrementally():
    sc = load("object-properties")
    r = BuiRenderer()
    h = HeadlessHost(r, (900, 900))
    for m in sc["messages"]:
        uc = m.get("updateComponents")
        if uc and len(uc["components"]) > 4:
            comps = uc["components"]
            for i in range(0, len(comps), 4):
                r.process([{"version": "1.0", "updateComponents": {"surfaceId": uc["surfaceId"], "components": comps[i:i + 4]}}])
                h.frame()
        else:
            r.process([m])
    assert not r.errors, r.errors[:3]
    assert h.view is not None and h.view.root_widget is not None


def test_rc_version_tag_is_accepted():
    sc = load("smart-home")
    r = BuiRenderer()
    r.process([{**m, "version": "v1.0"} for m in sc["messages"]])
    assert r.views and not r.errors


def test_template_children_resolve():
    r, _ = render("render-farm")
    v = next(iter(r.views.values()))
    assert sum(1 for rec in v.records.values() if rec.node.type == "ProgressBar") >= 4


def test_stream_hub_session_frames_and_actions():
    from a2ui_bui.hosts.stream import StreamHub
    hub = StreamHub()
    sc = load("animation")
    s = hub.open({"messages": sc["messages"], "width": 1150, "theme": "dark", "scale": 1.0})
    events, deadline = [], time.time() + 10
    while time.time() < deadline and not any(e["t"] == "frame" for e in events):
        events.append(s.outbox.get(timeout=10))
    size = next(e for e in events if e["t"] == "size")
    assert size["w"] == 1150 and size["h"] > 200
    _, w = None, None
    s.post({"t": "mouse", "k": "down", "x": 93, "y": 283, "b": 1, "mods": {}})
    s.post({"t": "mouse", "k": "up", "x": 93, "y": 283, "b": 1, "mods": {}})
    got, deadline = [], time.time() + 5
    while time.time() < deadline and not any(e["t"] == "action" for e in got):
        try:
            got.append(s.outbox.get(timeout=1))
        except Exception:
            pass
    s.close()
    acts = [e for e in got if e["t"] == "action"]
    assert acts and acts[0]["payload"]["action"]["name"] == "playback_toggle"
