#!/usr/bin/env python3
# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later

"""A2UI x BUI demo server.

Serves the static demo and a realtime generation endpoint:

  POST /api/generate  {prompt, previous?: [messages], data?: {...}, errors?: [str], model?}
      -> text/event-stream of JSON events:
         {"type":"status","text":...}
         {"type":"meta","meta":{"title","width"}}
         {"type":"message","message":{A2UI v1.0 message}}
         {"type":"done","model":...,"ms":...,"usage":{...}}
         {"type":"error","error":...}
  GET  /api/config    -> {"hasKey": bool, "models": [{id, label, provider, hasKey}], "default": id,
                          "providers": {name: {"hasKey": bool, "env": [...], "file": path}}}

Any model LiteLLM supports (Gemini, Claude, GPT, ...; see models.json) streams
JSON Lines (one A2UI message per line); each complete line is forwarded to the
browser as soon as it arrives so the surface builds up live.

  venv/bin/python server.py [--port 8230]
  keys: $GEMINI_API_KEY / $ANTHROPIC_API_KEY / $OPENAI_API_KEY, or
        ~/.config/a2ui_bui/{gemini,anthropic,openai}_api_key
  models: models.json (override with ~/.config/a2ui_bui/models.json)
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_DIR = pathlib.Path("~/.config/a2ui_bui").expanduser()
EXAMPLES = ["object-properties", "shader-nodes", "smart-home"]  # few-shot showcases

# Provider -> where its API key comes from. Model ids are LiteLLM's "<provider>/<model>".
PROVIDERS = {
    "gemini": {"label": "Gemini", "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"], "file": "gemini_api_key"},
    "anthropic": {"label": "Claude", "env": ["ANTHROPIC_API_KEY"], "file": "anthropic_api_key"},
    "openai": {"label": "GPT", "env": ["OPENAI_API_KEY"], "file": "openai_api_key"},
}


def load_key(provider: str = "gemini") -> str:
  spec = PROVIDERS.get(provider)
  if not spec:
    return ""
  for var in spec["env"]:
    k = os.environ.get(var, "").strip()
    if k:
      return k
  fp = CONFIG_DIR / spec["file"]
  if fp.exists() and fp.read_text().strip():
    return fp.read_text().strip()
  return ""


def provider_of(model_id: str) -> str:
  return model_id.split("/", 1)[0] if "/" in model_id else "gemini"


def load_models() -> list[dict]:
  """models.json (or the user's override): [{id, label, params?}], in fallback order."""
  override = os.environ.get("A2UI_BUI_MODELS")
  for p in ([pathlib.Path(override)] if override else []) + [CONFIG_DIR / "models.json", ROOT / "models.json"]:
    if p.exists():
      models = json.loads(p.read_text())["models"]
      for m in models:
        m.setdefault("label", m["id"].split("/", 1)[-1])
        m["provider"] = provider_of(m["id"])
      return models
  return [{"id": "gemini/gemini-flash-latest", "label": "Gemini Flash", "provider": "gemini"}]


# --------------------------------------------------------------------------- prompt

def _kind(p: dict) -> str:
  if "$ref" in p:
    return {"DynamicString": "str", "DynamicNumber": "num", "DynamicBoolean": "bool", "DynamicStringList": "strList",
            "DynamicValue": "value", "ComponentId": "child", "ChildList": "children", "Action": "action"}.get(
                p["$ref"].rsplit("/", 1)[-1], "value")
  if "enum" in p:
    return " | ".join(f'"{v}"' for v in p["enum"])
  if p.get("type") == "array":
    return "tabs"
  return p.get("type", "value")


def catalog_text(catalog: dict) -> str:
  out = []
  for name, c in catalog["components"].items():
    body = c["allOf"][1]
    req = set(body.get("required", []))
    props = []
    for k, p in body["properties"].items():
      if k in ("component", "description", "enabled", "weight"):
        continue
      doc = f" — {p['description']}" if p.get("description") else ""
      props.append(f"  - {k}{'*' if k in req else ''}: {_kind(p)}{doc}")
    out.append(f"## {name}\n{c['description']}\n" + "\n".join(props))
  return "\n\n".join(out)


def build_system_prompt() -> str:
  catalog = json.loads((ROOT / "bui/catalog.json").read_text())
  icons = json.loads((ROOT / "prompt/icons.json").read_text())["icons"]
  assets = sorted(p.name for p in (ROOT / "assets").iterdir()
                  if p.suffix in (".svg", ".png", ".jpg", ".mp4") and not p.name.startswith("test"))
  examples = []
  for sid in EXAMPLES:
    f = ROOT / "showcases" / f"{sid}.json"
    if not f.exists():
      continue
    sc = json.loads(f.read_text())
    lines = [json.dumps({"meta": {"title": sc.get("window", sc["name"]), "width": sc.get("width", 600)}})]
    lines += [json.dumps(m, separators=(",", ":")) for m in sc["messages"]]
    examples.append(f"## Request: {sc['description']}\n\n" + "\n".join(lines))
  tpl = (ROOT / "prompt/system_prompt.md").read_text()
  return (tpl.replace("__CATALOG_ID__", catalog["catalogId"])
          .replace("__CATALOG__", catalog_text(catalog))
          .replace("__ICONS__", ", ".join(icons))
          .replace("__ASSETS__", ", ".join(f"assets/{a}" for a in assets))
          .replace("__EXAMPLES__", "\n\n".join(examples)))


def user_turn(req: dict) -> str:
  parts = [f"User request: {req.get('prompt', '').strip()}"]
  prev = req.get("previous")
  if prev:
    parts.append("Current UI (A2UI messages, JSON Lines):\n" +
                 "\n".join(json.dumps(m, separators=(",", ":")) for m in prev))
    if req.get("data") is not None:
      parts.append("Current data model (includes the user's edits; keep these values):\n" +
                   json.dumps(req["data"], separators=(",", ":")))
  if req.get("errors"):
    parts.append("The previous output had these renderer/validation errors. Output the complete corrected UI:\n- " +
                 "\n- ".join(req["errors"][:30]))
  parts.append("Respond with JSON Lines only.")
  return "\n\n".join(parts)


# --------------------------------------------------------------------------- streaming

def close_json(s: str) -> str | None:
  """Appends the closers for unbalanced {/[ outside strings (None if balanced/invalid)."""
  stack, in_str, esc = [], False, False
  for ch in s:
    if in_str:
      if esc:
        esc = False
      elif ch == "\\":
        esc = True
      elif ch == '"':
        in_str = False
    elif ch == '"':
      in_str = True
    elif ch in "{[":
      stack.append("}" if ch == "{" else "]")
    elif ch in "}]":
      if not stack or stack[-1] != ch:
        return None
      stack.pop()
  if in_str or not stack:
    return None
  return s.rstrip().rstrip(",") + "".join(reversed(stack))


class LineParser:
  """Accumulates streamed text and yields complete JSON objects (one per line,
  tolerating code fences and objects split across lines)."""

  def __init__(self):
    self.buf = ""
    self.pending = ""

  def feed(self, text: str):
    self.buf += text
    while "\n" in self.buf:
      line, self.buf = self.buf.split("\n", 1)
      yield from self._line(line)

  def flush(self):
    if self.buf:
      line, self.buf = self.buf, ""
      yield from self._line(line)
    if self.pending.strip():
      yield from self._try(self.pending, final=True)
      self.pending = ""

  def _line(self, line: str):
    s = line.strip()
    if not s or s.startswith("```"):
      return
    if self.pending:
      self.pending += s
      yield from self._try(self.pending)
      return
    if s.startswith("{"):
      self.pending = s
      yield from self._try(s)

  def _try(self, s: str, final: bool = False):
    try:
      obj = json.loads(s.rstrip(","))
    except json.JSONDecodeError:
      # Models occasionally drop a closing bracket at the end of a long line:
      # close whatever is still open if the line is a whole message.
      fixed = close_json(s) if (final or (len(s) > 40 and re.search(r'"(meta|createSurface|updateComponents|updateDataModel)"', s))) else None
      try:
        obj = json.loads(fixed) if fixed else None
      except json.JSONDecodeError:
        obj = None
      if obj is None:
        if final or len(s) > 400_000:
          self.pending = ""
        return
    self.pending = ""
    if isinstance(obj, dict):
      yield obj


_litellm = None


def litellm():
  """Imported on first use: LiteLLM is large, and the static demo doesn't need it."""
  global _litellm
  if _litellm is None:
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # no network fetch at import
    import litellm as _l
    _l.telemetry = False
    _l.suppress_debug_info = True
    _l.drop_params = True  # params a provider doesn't support are dropped, not errors
    import logging
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    _litellm = _l
  return _litellm


class RetryableError(Exception):
  """Failed before any output for a reason another model may not have (rate limit, overload, unknown model)."""


def stream_model(model: dict, system: str, user: str):
  """Yields ("text", str), ("finish", reason), ("usage", {prompt, output, reasoning}) for any LiteLLM model."""
  L = litellm()
  params = {"max_tokens": 32000, **model.get("params", {})}
  try:
    resp = L.completion(
        model=model["id"], api_key=load_key(model["provider"]), stream=True, timeout=180,
        stream_options={"include_usage": True},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **params)
  except (L.RateLimitError, L.NotFoundError, L.ServiceUnavailableError, L.InternalServerError,
          L.APIConnectionError, L.Timeout) as e:
    raise RetryableError(f"{type(e).__name__}: {str(e)[:200]}") from e
  for chunk in resp:
    for choice in chunk.choices or []:
      text = getattr(choice.delta, "content", None)
      if text:
        yield "text", text
      if choice.finish_reason:
        yield "finish", choice.finish_reason
    u = getattr(chunk, "usage", None)
    if u:
      details = getattr(u, "completion_tokens_details", None)
      yield "usage", {"prompt": u.prompt_tokens, "output": u.completion_tokens,
                      "reasoning": getattr(details, "reasoning_tokens", None)}


class Handler(http.server.SimpleHTTPRequestHandler):
  server_version = "a2ui-bui/1"

  def __init__(self, *a, **kw):
    super().__init__(*a, directory=str(ROOT), **kw)

  def log_message(self, fmt, *args):
    if "/api/" in str(args[0] if args else ""):
      super().log_message(fmt, *args)

  def end_headers(self):
    self.send_header("Cache-Control", "no-store")
    super().end_headers()

  def do_GET(self):
    if self.path.startswith("/ws/surface") or self.path.startswith("/ws/app/"):
      # BUI-native rendering: a2ui_bui (GPL-3.0-or-later, renderer/) renders the
      # surface headlessly and streams pixels to viewport.js.
      try:
        from a2ui_bui.hosts.ws import handle_websocket
      except ImportError as e:
        return self.send_error(503, f"a2ui_bui renderer not installed ({e}); run server.py with the renderer venv")
      return handle_websocket(self)
    if self.path == "/api/apps":
      try:
        from a2ui_bui.apps import list_apps
        return self._json({"apps": list_apps()})
      except Exception as e:
        return self._json({"apps": [], "error": str(e)}, status=500)
    if self.path.startswith("/api/apps/"):
      app_id = self.path[len("/api/apps/"):].split("?", 1)[0].strip("/")
      if "/" not in app_id and app_id:
        return self._get_app(app_id)
    if self.path.startswith("/app/"):
      app_id = self.path[len("/app/"):].split("?", 1)[0].strip("/")
      if app_id:
        return self._serve_app_page(app_id)
    if self.path.startswith("/api/config"):
      models = load_models()
      has = {p: bool(load_key(p)) for p in PROVIDERS}
      listed = [{**{k: m[k] for k in ("id", "label", "provider")}, "hasKey": has.get(m["provider"], False)}
                for m in models]
      default = next((m["id"] for m in listed if m["hasKey"]), listed[0]["id"] if listed else "")
      return self._json({"hasKey": any(has.values()), "models": listed, "default": default,
                         "providers": {p: {"label": v["label"], "hasKey": has[p], "env": v["env"],
                                           "file": f"~/.config/a2ui_bui/{v['file']}"} for p, v in PROVIDERS.items()}})
    if self.path.startswith("/api/system_prompt"):
      body = build_system_prompt().encode()
      self.send_response(200)
      self.send_header("Content-Type", "text/plain; charset=utf-8")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)
      return
    return super().do_GET()

  def do_DELETE(self):
    if not self.path.startswith("/api/apps/"):
      return self.send_error(404)
    app_id = self.path[len("/api/apps/"):].split("?", 1)[0].strip("/")
    from a2ui_bui.apps.model import delete_app
    from a2ui_bui.hosts.ws import hub
    rt = hub().runtimes.pop(app_id, None)
    if rt is not None:
      rt.stop()
    ok = delete_app(app_id)
    return self._json({"ok": ok})

  def do_POST(self):
    if self.path == "/api/apps":
      return self._create_app()
    if self.path.startswith("/api/apps/") and self.path.endswith("/build"):
      app_id = self.path[len("/api/apps/"):-len("/build")].strip("/")
      return self._build_app(app_id)
    if self.path.startswith("/api/apps/") and self.path.endswith("/rollback"):
      app_id = self.path[len("/api/apps/"):-len("/rollback")].strip("/")
      return self._rollback_app(app_id)
    if not self.path.startswith("/api/generate"):
      return self.send_error(404)
    n = int(self.headers.get("Content-Length", 0))
    try:
      req = json.loads(self.rfile.read(n) or b"{}")
    except json.JSONDecodeError:
      return self.send_error(400, "bad json")
    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream")
    self.send_header("X-Accel-Buffering", "no")
    self.end_headers()

    def send(ev: dict):
      self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
      self.wfile.flush()

    models = [m for m in load_models() if load_key(m["provider"])]
    if not models:
      send({"type": "error", "error": "No model API key: set GEMINI_API_KEY, ANTHROPIC_API_KEY or OPENAI_API_KEY "
                                      "(or write ~/.config/a2ui_bui/<provider>_api_key)"})
      return
    # The requested model first, then the others that have a key (models.json order) as fallbacks.
    wanted = req.get("model") or ""
    if wanted and "/" not in wanted:  # pre-LiteLLM ids ("gemini-3.8-flash")
      wanted = f"gemini/{wanted}"
    models.sort(key=lambda m: m["id"] != wanted)
    system = build_system_prompt()
    user = user_turn(req)
    t0 = time.time()
    for model in models[:3]:
      parser = LineParser()
      raw_text = []
      finish = ""
      emitted = 0
      usage = {}
      send({"type": "status", "text": f"Generating with {model['label']}…"})
      try:
        for kind, val in stream_model(model, system, user):
          if kind == "usage":
            usage = val
            continue
          if kind == "finish":
            finish = val
            continue
          raw_text.append(val)
          for obj in parser.feed(val):
            emitted += self._emit(obj, send)
        for obj in parser.flush():
          emitted += self._emit(obj, send)
        pathlib.Path("/tmp/bui_last_gen.txt").write_text("".join(raw_text))
      except (BrokenPipeError, ConnectionResetError):
        return
      except RetryableError as e:
        if emitted == 0:
          send({"type": "status", "text": f"{model['label']}: {e}; trying the next model"})
          continue
        send({"type": "error", "error": f"{model['label']}: {e}"})
        return
      except Exception as e:  # auth, bad request, network errors mid-stream
        if emitted == 0 and model is not models[min(2, len(models) - 1)]:
          send({"type": "status", "text": f"{model['label']}: {str(e)[:200]}; trying the next model"})
          continue
        send({"type": "error", "error": f"{model['label']}: {str(e)[:400]}"})
        return
      send({"type": "done", "model": model["id"], "ms": int((time.time() - t0) * 1000), "messages": emitted,
            "finish": finish, "usage": usage})
      return
    send({"type": "error", "error": "All models failed"})

  @staticmethod
  def _emit(obj: dict, send) -> int:
    if "meta" in obj and isinstance(obj["meta"], dict):
      send({"type": "meta", "meta": obj["meta"]})
      return 0
    if any(k in obj for k in ("createSurface", "updateComponents", "updateDataModel", "deleteSurface")):
      obj["version"] = "1.0"
      send({"type": "message", "message": obj})
      return 1
    return 0

  def _get_app(self, app_id: str):
    try:
      from a2ui_bui.apps import get_app
      from a2ui_bui.hosts.ws import hub
      rec = get_app(app_id)
    except FileNotFoundError:
      return self.send_error(404, f"unknown app {app_id!r}")
    rt = hub().runtimes.get(app_id)
    return self._json({
        "meta": rec.meta(),
        "actions": rec.declared_actions(),
        "handlers": rt.handlers if rt is not None else [],
        "versions": rec.versions(),
        "main_py": rec.main_py.read_text() if rec.main_py.exists() else "",
        "test_py": rec.test_py.read_text() if rec.test_py.exists() else "",
        "log": rec.read_log(80),
        "messages": rec.messages_with_state(),
    })

  def _create_app(self):
    n = int(self.headers.get("Content-Length", 0))
    try:
      req = json.loads(self.rfile.read(n) or b"{}")
    except json.JSONDecodeError:
      return self.send_error(400, "bad json")
    from a2ui_bui.apps import create_app
    rec = create_app(
        title=req.get("title") or "Untitled App",
        messages=req.get("messages") or [],
        width=int(req.get("width") or 900),
        prompt=req.get("prompt") or "",
        model=req.get("model") or "",
        app_id=req.get("app_id"),
    )
    return self._json({"ok": True, "app": rec.meta()})

  def _build_app(self, app_id: str):
    n = int(self.headers.get("Content-Length", 0))
    try:
      req = json.loads(self.rfile.read(n) or b"{}") if n else {}
    except json.JSONDecodeError:
      req = {}
    try:
      from a2ui_bui.apps import get_app
      from a2ui_bui.apps.agent import AppAgent
      from a2ui_bui.hosts.ws import hub
      rec = get_app(app_id)
    except FileNotFoundError:
      return self.send_error(404, f"unknown app {app_id!r}")

    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream")
    self.send_header("X-Accel-Buffering", "no")
    self.end_headers()

    def send(ev: dict):
      try:
        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
        self.wfile.flush()
      except (BrokenPipeError, ConnectionResetError):
        pass

    try:
      agent = AppAgent(model_id=req.get("model"))
      res = agent.build(rec, on_status=lambda s: send({"type": "status", "text": s}))
      rt = hub().runtimes.get(app_id)
      handlers = rt.reload_worker() if (rt is not None and res.get("ok")) else []
      send({"type": "done", **res, "handlers": handlers})
    except Exception as e:
      send({"type": "error", "error": str(e)})

  def _rollback_app(self, app_id: str):
    n = int(self.headers.get("Content-Length", 0))
    try:
      req = json.loads(self.rfile.read(n) or b"{}") if n else {}
    except json.JSONDecodeError:
      req = {}
    try:
      from a2ui_bui.apps import get_app
      from a2ui_bui.hosts.ws import hub
      rec = get_app(app_id)
    except FileNotFoundError:
      return self.send_error(404, f"unknown app {app_id!r}")
    ver = rec.rollback(req.get("version"))
    if ver is None:
      return self._json({"ok": False, "error": "no version to roll back to"}, status=400)
    rt = hub().runtimes.get(app_id)
    handlers = rt.reload_worker() if rt is not None else []
    return self._json({"ok": True, "version": ver, "handlers": handlers})

  def _serve_app_page(self, app_id: str):
    try:
      from a2ui_bui.apps import get_app
      rec = get_app(app_id)
      meta = rec.meta()
    except FileNotFoundError:
      return self.send_error(404, f"unknown app {app_id!r}")
    title = meta.get("title") or app_id
    width = int(meta.get("width") or 900)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — A2UI × BUI App</title>
  <link rel="stylesheet" href="/app.css">
  <style>
    body {{ margin: 0; background: #1e1e1e; color: #e5e5e5; font: 13px Inter, system-ui, sans-serif; }}
    .app-bar {{ display: flex; align-items: center; justify-content: space-between; padding: 8px 16px;
                background: #141414; border-bottom: 1px solid #2b2b2b; }}
    .app-bar b {{ font-weight: 600; }}
    .app-bar .ctrl {{ display: flex; gap: 10px; align-items: center; font-size: 12px; color: #aaa; }}
    .app-bar a {{ color: #aaa; text-decoration: none; }}
    .app-stage {{ display: flex; justify-content: center; padding: 20px; }}
    .app-win {{ width: {width}px; max-width: calc(100vw - 40px); border-radius: 10px; overflow: hidden;
                box-shadow: 0 12px 32px rgba(0,0,0,.45); background: #303030; }}
    #app-status {{ font-size: 12px; color: #f6b96c; }}
  </style>
</head>
<body>
  <header class="app-bar">
    <div><b>{title}</b> <span id="app-status"></span></div>
    <div class="ctrl">
      <label>Theme <select id="theme"><option value="dark">Dark</option><option value="light">Light</option></select></label>
      <label>Scale <select id="scale"><option>1</option><option selected>1.25</option><option>1.5</option></select></label>
      <a href="/#apps">All apps</a>
    </div>
  </header>
  <main class="app-stage"><div class="app-win"><div id="surface" class="surface-host"></div></div></main>
  <script type="module">
    import {{mountSurface}} from '/viewport.js';
    const surface = mountSurface(document.getElementById('surface'), [], {{
      appId: {json.dumps(app_id)},
      width: {width},
      theme: localStorage.getItem('bui-demo.theme') || 'dark',
      scale: Number(localStorage.getItem('bui-demo.scale') || 1.25),
      onBackend: (ev) => {{
        const st = document.getElementById('app-status');
        if (ev.t === 'agent_status') st.textContent = ev.text || '';
      }},
      onError: (e) => {{ document.getElementById('app-status').textContent = e; }},
    }});
    document.getElementById('theme').onchange = (e) => surface.setTheme(e.target.value);
    document.getElementById('scale').onchange = (e) => surface.setScale(Number(e.target.value));
  </script>
</body>
</html>"""
    body = html.encode()
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _json(self, obj, status: int = 200):
    body = json.dumps(obj).encode()
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--port", type=int, default=8230)
  ap.add_argument("--host", default="127.0.0.1")
  ap.add_argument("--sandbox", choices=("auto", "bwrap", "seatbelt", "none"), default="auto")
  args = ap.parse_args()
  srv = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
  srv.daemon_threads = True
  try:
    import a2ui_bui  # noqa: F401
    from a2ui_bui.apps.builtins import seed_builtin_apps
    from a2ui_bui.hosts.ws import hub
    hub().sandbox_mode = args.sandbox
    seed_builtin_apps()
    renderer = "a2ui_bui " + a2ui_bui.__version__
  except ImportError:
    renderer = "MISSING (pip install -e renderer/)"
  keys = ", ".join(f"{v['label']} {'yes' if load_key(p) else 'no'}" for p, v in PROVIDERS.items())
  print(f"A2UI x BUI demo on http://{args.host}:{args.port}/  (keys: {keys}; BUI renderer: {renderer})")
  srv.serve_forever()


if __name__ == "__main__":
  main()
