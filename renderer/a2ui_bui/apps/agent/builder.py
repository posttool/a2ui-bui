# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""ADK-powered app builder agent (google-adk + LiteLlm).

Uses `google.adk.agents.LlmAgent` and `Runner` with the tools in `tools.py`
to write, test, and repair `backend/main.py` + `backend/test_main.py` in the
sandbox, and to handle any live action that lacks a handler or fails.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from ..model import AppRecord
from ..sandbox import Sandbox, SandboxPolicy, select_sandbox
from .tools import make_tools, run_app_tests

REPO = Path(__file__).resolve().parents[4]
PROMPT_PATH = REPO / "prompt" / "backend_prompt.md"


def _resolve_adk_models(model_id: str | None = None) -> list[tuple[Any, str]]:
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    from google.adk.models.lite_llm import LiteLlm

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import server as demo_server

    models = [m for m in demo_server.load_models() if demo_server.load_key(m["provider"])]
    if not models:
        raise RuntimeError(
            "No model API key configured (set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)"
        )
    if model_id:
        models.sort(key=lambda m: m["id"] != model_id)
    out = []
    for m in models[:3]:
        key = demo_server.load_key(m["provider"])
        out.append((LiteLlm(model=m["id"], api_key=key, **m.get("params", {})), m["id"]))
    return out


def _instruction() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return (
        "Write backend/main.py and backend/test_main.py using the `a2ui_app` SDK, "
        "run `run_tests()`, and call `finish(summary)` when all tests pass."
    )


class AppAgent:
    def __init__(self, model: Any = None, *, model_id: str | None = None, max_repairs: int = 2) -> None:
        self._explicit_model = model
        self._model_id = model_id
        self.max_repairs = max_repairs

    def _models(self) -> list[tuple[Any, str]]:
        if self._explicit_model is not None:
            return [(self._explicit_model, getattr(self._explicit_model, "model", "custom"))]
        return _resolve_adk_models(self._model_id)

    def _run_adk_loop(
        self,
        app: AppRecord,
        prompt: str,
        *,
        sandbox: Sandbox,
        policy: SandboxPolicy,
        surface_id: str = "main",
        dispatch_ui: Callable[[list[dict]], None] | None = None,
        state_box: dict | None = None,
        on_status: Callable[[str], None] | None = None,
        source: str = "build",
    ) -> dict:
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        prev_main = app.main_py.read_text() if app.main_py.exists() else None
        prev_test = app.test_py.read_text() if app.test_py.exists() else None

        candidates = self._models()
        model, model_name = candidates[0]
        tools, tracker = make_tools(
            app, sandbox=sandbox, policy=policy, surface_id=surface_id,
            dispatch_ui=dispatch_ui, state_box=state_box, on_status=on_status,
        )
        sessions = InMemorySessionService()

        def _send(text: str) -> str:
            nonlocal model, model_name
            last_err = None
            for idx, (cand_model, cand_name) in enumerate(candidates):
                model, model_name = cand_model, cand_name
                agent = LlmAgent(
                    name=f"a2ui_backend_{app.id.replace('-', '_')}",
                    model=model,
                    instruction=_instruction(),
                    tools=tools,
                )
                runner = Runner(
                    app_name="a2ui_bui_builder",
                    agent=agent,
                    session_service=sessions,
                    auto_create_session=True,
                )
                sid = str(uuid.uuid4())
                last_text = ""
                msg = types.Content(role="user", parts=[types.Part.from_text(text=text)])
                try:
                    for ev in runner.run(user_id="builder", session_id=sid, new_message=msg):
                        if getattr(ev, "content", None) and getattr(ev.content, "parts", None):
                            for part in ev.content.parts:
                                if getattr(part, "text", None):
                                    last_text = part.text
                    return last_text
                except Exception as e:
                    last_err = e
                    name_low = type(e).__name__.lower()
                    if idx + 1 < len(candidates) and any(k in name_low for k in ("unavailable", "ratelimit", "timeout", "internalserver")):
                        if on_status:
                            on_status(f"{cand_name} busy ({type(e).__name__}); trying {candidates[idx + 1][1]}…")
                        continue
                    raise
            raise last_err  # type: ignore[misc]

        if on_status:
            on_status(f"ADK agent ({model_name}) designing backend…")
        last_reply = _send(prompt)

        # Ensure tests exist and pass before accepting code changes.
        test_res: dict[str, Any] = {"ok": False}
        if app.has_backend():
            for attempt in range(self.max_repairs + 1):
                test_res = run_app_tests(app, sandbox=sandbox, policy=policy)
                if test_res.get("ok"):
                    tracker["tests_passed"] = True
                    break
                if attempt >= self.max_repairs:
                    break
                if on_status:
                    on_status(f"Tests failed; asking agent to repair ({attempt + 1}/{self.max_repairs})…")
                _send(
                    "Tests failed in the sandbox. Fix backend/main.py or backend/test_main.py, "
                    "re-run `run_tests()`, and call `finish(summary)`:\n\n"
                    f"{test_res.get('output') or test_res.get('error')}"
                )

            if not test_res.get("ok"):
                # Roll back so broken code never replaces a working backend.
                if prev_main is None:
                    app.main_py.unlink(missing_ok=True)
                else:
                    app.main_py.write_text(prev_main)
                if prev_test is None:
                    app.test_py.unlink(missing_ok=True)
                else:
                    app.test_py.write_text(prev_test)
                app.append_log({"kind": "agent_rejected", "reason": "tests_failed",
                                "output": (test_res.get("output") or test_res.get("error") or "")[:1000]})
                return {
                    "ok": False,
                    "code_updated": False,
                    "summary": tracker["summary"] or "Backend tests failed; rolled back.",
                    "test_output": test_res.get("output") or test_res.get("error"),
                }

        code_updated = bool(tracker["written"]) and app.has_backend()
        summary = tracker["summary"] or last_reply[:200] or "Updated backend"
        if code_updated:
            ver = app.save_version(summary, source=source)
        else:
            ver = None

        return {
            "ok": True,
            "code_updated": code_updated,
            "version": ver["version"] if ver else None,
            "summary": summary,
            "ui_sent": tracker["ui_sent"],
            "model": model_name,
        }

    def build(
        self,
        app: AppRecord,
        *,
        sandbox: Sandbox | None = None,
        policy: SandboxPolicy | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict:
        meta = app.meta()
        sb = sandbox or select_sandbox(meta.get("sandbox") or "auto")
        pol = policy or SandboxPolicy(mode=sb.name)
        actions = app.declared_actions()
        prompt = (
            f"Build the complete backend for app {meta.get('title', app.id)!r}.\n"
            f"Original user prompt: {meta.get('prompt', '')}\n\n"
            f"Declared UI actions ({len(actions)}):\n{json.dumps(actions, indent=2)}\n\n"
            "First read `state.json` (and `ui.jsonl` if needed) to see the exact data model shape. "
            "Then write `backend/main.py` with `@app.on(...)` handlers for EVERY declared action, "
            "using `app.db` / `app.storage` where persistence makes sense. "
            "Write `backend/test_main.py` with unit tests for every handler, run `run_tests()` and "
            "`try_action()` on the main actions, and finally call `finish(summary)`."
        )
        return self._run_adk_loop(app, prompt, sandbox=sb, policy=pol, on_status=on_status, source="build")

    def handle(
        self,
        app: AppRecord,
        action: dict,
        data: dict,
        *,
        surface_id: str = "main",
        error: str | None = None,
        dispatch_ui: Callable[[list[dict]], None] | None = None,
        sandbox: Sandbox | None = None,
        policy: SandboxPolicy | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict:
        meta = app.meta()
        sb = sandbox or select_sandbox(meta.get("sandbox") or "auto")
        pol = policy or SandboxPolicy(mode=sb.name)
        err_block = f"\nPrevious handler error:\n{error}\n" if error else "\nThere is currently no handler for this action.\n"
        prompt = (
            f"The user triggered action `{action.get('name')}` on app {meta.get('title', app.id)!r}.\n"
            f"Action payload: {json.dumps(action)}\n"
            f"Current data model:\n{json.dumps(data)[:4000]}\n"
            f"{err_block}\n"
            "1. Inspect `backend/main.py` and `backend/test_main.py`.\n"
            "2. Answer the user's current action immediately using `set_data` or `update_ui` so the UI updates right away.\n"
            "3. Add or fix the `@app.on(...)` handler in `backend/main.py` and its test in `backend/test_main.py`, "
            "run `run_tests()` and `try_action(...)` until green, then call `finish(summary)`."
        )
        return self._run_adk_loop(
            app, prompt, sandbox=sb, policy=pol, surface_id=surface_id,
            dispatch_ui=dispatch_ui, state_box=data, on_status=on_status, source="fallback",
        )
