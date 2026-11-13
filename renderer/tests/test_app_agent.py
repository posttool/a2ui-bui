# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""ADK builder agent tests: uses a scripted fake ADK BaseLlm driving the real
google.adk Runner + LlmAgent + sandboxed tools."""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import PrivateAttr

from a2ui_bui.apps import create_app
from a2ui_bui.apps.agent import AppAgent
from a2ui_bui.apps.runtime import AppRuntime, _set_pointer


def _fc(name: str, args: dict) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]),
        turn_complete=True,
    )


def _txt(text: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        turn_complete=True,
    )


class _ScriptedLlm(BaseLlm):
    model: str = "fake-adk"
    _steps: list[LlmResponse] = PrivateAttr(default_factory=list)
    _idx: int = PrivateAttr(default=0)

    def __init__(self, steps: list[LlmResponse]):
        super().__init__(model="fake-adk")
        self._steps = steps
        self._idx = 0

    async def generate_content_async(self, llm_request, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        if self._idx < len(self._steps):
            r = self._steps[self._idx]
            self._idx += 1
            yield r
        else:
            yield _txt("done")


def _sample_messages():
    return [
        {"version": "1.0", "createSurface": {"surfaceId": "main", "catalogId": "https://a2ui-bui-demo.local/catalogs/bui/v1/catalog.json"}},
        {"version": "1.0", "updateDataModel": {"surfaceId": "main", "value": {"count": 0, "status": "idle"}}},
        {"version": "1.0", "updateComponents": {"surfaceId": "main", "components": [
            {"id": "root", "component": "Column", "children": ["b1", "b2"]},
            {"id": "b1", "component": "Button", "text": "Inc", "action": {"event": {"name": "inc"}}},
            {"id": "b2", "component": "Button", "text": "Reset", "action": {"event": {"name": "reset_count"}}},
        ]}},
    ]


def test_adk_build_repairs_failing_test_and_saves_version(tmp_path):
    rec = create_app(title="ADK Counter", messages=_sample_messages(), base_dir=tmp_path)
    broken_main = (
        "from a2ui_app import app\n"
        "@app.on('inc')\n"
        "def inc(ctx, data):\n"
        "    data['count'] = (data.get('count') or 0) + 99   # bug\n"
    )
    fixed_main = (
        "from a2ui_app import app\n"
        "@app.on('inc')\n"
        "def inc(ctx, data):\n"
        "    data['count'] = (data.get('count') or 0) + 1\n"
    )
    test_src = (
        "import unittest\n"
        "from a2ui_app import TrackedDict, _PatchSink\n"
        "import main\n"
        "class T(unittest.TestCase):\n"
        "    def test_inc(self):\n"
        "        d = TrackedDict({'count': 0}, '', _PatchSink())\n"
        "        main.inc({}, d)\n"
        "        self.assertEqual(d['count'], 1)\n"
    )
    fake_llm = _ScriptedLlm([
        _fc("list_actions", {}),
        _fc("write_file", {"path": "backend/main.py", "content": broken_main}),
        _fc("write_file", {"path": "backend/test_main.py", "content": test_src}),
        _fc("finish", {"summary": "initial draft"}),
        # Repair turn triggered automatically because test_inc fails (99 != 1):
        _fc("write_file", {"path": "backend/main.py", "content": fixed_main}),
        _fc("run_tests", {}),
        _fc("finish", {"summary": "fixed inc handler"}),
    ])

    res = AppAgent(model=fake_llm).build(rec)
    assert res["ok"] and res["code_updated"] and res["version"] == 1
    assert len(rec.versions()) == 1
    assert "data['count'] = (data.get('count') or 0) + 1" in rec.main_py.read_text()


def test_adk_fallback_handles_unhandled_action_then_runs_as_code(tmp_path):
    rec = create_app(title="ADK Fallback", messages=_sample_messages(), base_dir=tmp_path)
    state = rec.load_state()

    def dispatch(msgs):
        for m in msgs:
            ud = m.get("updateDataModel")
            if ud:
                _set_pointer(state, ud.get("path") or "/", ud.get("value"))

    reset_main = (
        "from a2ui_app import app\n"
        "@app.on('reset_count')\n"
        "def reset_count(ctx, data):\n"
        "    data['count'] = 0\n"
        "    data['status'] = 'reset by code'\n"
    )
    reset_test = (
        "import unittest\n"
        "from a2ui_app import TrackedDict, _PatchSink\n"
        "import main\n"
        "class T(unittest.TestCase):\n"
        "    def test_reset(self):\n"
        "        d = TrackedDict({'count': 5, 'status': ''}, '', _PatchSink())\n"
        "        main.reset_count({}, d)\n"
        "        self.assertEqual(d['count'], 0)\n"
    )
    fake_llm = _ScriptedLlm([
        _fc("set_data", {"path": "/status", "value_json": '"reset by agent"'}),
        _fc("write_file", {"path": "backend/main.py", "content": reset_main}),
        _fc("write_file", {"path": "backend/test_main.py", "content": reset_test}),
        _fc("run_tests", {}),
        _fc("finish", {"summary": "added reset_count handler"}),
    ])

    rt = AppRuntime(
        rec,
        dispatch_ui=dispatch,
        get_data=lambda sid="main": state,
        agent_factory=lambda: AppAgent(model=fake_llm),
    )
    rt.start()
    try:
        # First click: no handler -> ADK agent answers and writes handler.
        r1 = rt.handle_action_sync({"action": {"name": "reset_count", "surfaceId": "main", "context": {}}})
        assert r1["ok"] and r1["source"] == "agent"
        assert state["status"] == "reset by agent"
        assert "reset_count" in rt.handlers

        # Second click: runs in sandboxed Python worker, no LLM!
        state["count"] = 42
        r2 = rt.handle_action_sync({"action": {"name": "reset_count", "surfaceId": "main", "context": {}}})
        assert r2["ok"] and r2["source"] == "code"
        assert state["count"] == 0 and state["status"] == "reset by code"
    finally:
        rt.stop()
