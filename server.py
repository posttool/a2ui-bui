#!/usr/bin/env python3
# Copyright 2026 posttool
# SPDX-License-Identifier: Apache-2.0

"""A2UI x BUI demo server (stdlib only).

Serves the static demo and a realtime generation endpoint:

  POST /api/generate  {prompt, previous?: [messages], data?: {...}, errors?: [str], model?}
      -> text/event-stream of JSON events:
         {"type":"status","text":...}
         {"type":"meta","meta":{"title","width"}}
         {"type":"message","message":{A2UI v1.0 message}}
         {"type":"done","model":...,"ms":...,"usage":{...}}
         {"type":"error","error":...}
  GET  /api/config    -> {"hasKey": bool, "models": [...], "default": ...}

Gemini streams JSON Lines (one A2UI message per line); each complete line is
forwarded to the browser as soon as it arrives so the surface builds up live.

  python3 server.py [--port 8230]   # key: $GEMINI_API_KEY or ~/.config/a2ui_bui/gemini_api_key
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
MODELS = ["gemini-3.8-flash", "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-flash-latest"]
KEY_PATHS = ["~/.config/a2ui_bui/gemini_api_key"]
EXAMPLES = ["object-properties", "shader-nodes", "smart-home"]  # few-shot showcases


def load_key() -> str:
  k = os.environ.get("GEMINI_API_KEY", "").strip()
  if k:
    return k
  for p in KEY_PATHS:
    fp = pathlib.Path(p).expanduser()
    if fp.exists() and fp.read_text().strip():
      return fp.read_text().strip()
  return ""


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


def stream_gemini(key: str, model: str, system: str, user: str):
  body = {
      "systemInstruction": {"parts": [{"text": system}]},
      "contents": [{"role": "user", "parts": [{"text": user}]}],
      "generationConfig": {"temperature": 0.7, "maxOutputTokens": 32768, "thinkingConfig": {"thinkingLevel": "low"}},
  }
  req = urllib.request.Request(API.format(model=model), data=json.dumps(body).encode(), method="POST",
                               headers={"Content-Type": "application/json", "x-goog-api-key": key})
  # Socket read timeout: a model that sends nothing for 90 s is treated as stuck (next model is tried).
  with urllib.request.urlopen(req, timeout=90) as resp:
    for raw in resp:
      line = raw.decode("utf-8", "replace").strip()
      if not line.startswith("data:"):
        continue
      try:
        chunk = json.loads(line[5:])
      except json.JSONDecodeError:
        continue
      usage = chunk.get("usageMetadata")
      for cand in chunk.get("candidates", []):
        if cand.get("finishReason"):
          yield "finish", cand["finishReason"]
        for part in cand.get("content", {}).get("parts", []):
          if part.get("text") and not part.get("thought"):
            yield "text", part["text"]
      if usage:
        yield "usage", usage


class Handler(http.server.SimpleHTTPRequestHandler):
  server_version = "a2ui-bui/1"

  def __init__(self, *a, **kw):
    super().__init__(*a, directory=str(ROOT), **kw)

  def log_message(self, fmt, *args):
    if "/api/" in (args[0] if args else ""):
      super().log_message(fmt, *args)

  def end_headers(self):
    self.send_header("Cache-Control", "no-store")
    super().end_headers()

  def do_GET(self):
    if self.path.startswith("/ws/surface"):
      # BUI-native rendering: a2ui_bui (GPL-3.0-or-later, renderer/) renders the
      # surface headlessly and streams pixels to viewport.js.
      try:
        from a2ui_bui.hosts.ws import handle_websocket
      except ImportError as e:
        return self.send_error(503, f"a2ui_bui renderer not installed ({e}); run server.py with the renderer venv")
      return handle_websocket(self)
    if self.path.startswith("/api/config"):
      return self._json({"hasKey": bool(load_key()), "models": MODELS, "default": MODELS[0]})
    if self.path.startswith("/api/system_prompt"):
      body = build_system_prompt().encode()
      self.send_response(200)
      self.send_header("Content-Type", "text/plain; charset=utf-8")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)
      return
    return super().do_GET()

  def do_POST(self):
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

    key = load_key()
    if not key:
      send({"type": "error", "error": "No Gemini API key: set GEMINI_API_KEY or write ~/.config/a2ui_bui/gemini_api_key"})
      return
    system = build_system_prompt()
    user = user_turn(req)
    models = [req["model"]] if req.get("model") in MODELS else []
    models += [m for m in MODELS if m not in models]
    t0 = time.time()
    for model in models[:3]:
      parser = LineParser()
      raw_text = []
      finish = ""

      emitted = 0
      usage = {}
      send({"type": "status", "text": f"Generating with {model}…"})
      try:
        for kind, val in stream_gemini(key, model, system, user):
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
      except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if emitted == 0 and e.code in (404, 429, 500, 503):
          send({"type": "status", "text": f"{model}: HTTP {e.code}, trying next model"})
          continue
        send({"type": "error", "error": f"{model}: HTTP {e.code} {detail}"})
        return
      except (BrokenPipeError, ConnectionResetError):
        return
      except Exception as e:  # network errors mid-stream
        if emitted == 0:
          send({"type": "status", "text": f"{model}: {e}, trying next model"})
          continue
        send({"type": "error", "error": f"{model}: {e}"})
        return
      send({"type": "done", "model": model, "ms": int((time.time() - t0) * 1000), "messages": emitted, "finish": finish,
            "usage": {k: usage.get(k) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")}})
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

  def _json(self, obj):
    body = json.dumps(obj).encode()
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--port", type=int, default=8230)
  ap.add_argument("--host", default="0.0.0.0")
  args = ap.parse_args()
  srv = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
  srv.daemon_threads = True
  try:
    import a2ui_bui  # noqa: F401
    renderer = "a2ui_bui " + a2ui_bui.__version__
  except ImportError:
    renderer = "MISSING (pip install -e renderer/)"
  print(f"A2UI x BUI demo on http://{args.host}:{args.port}/  (Gemini key: {'yes' if load_key() else 'MISSING'}, BUI renderer: {renderer})")
  srv.serve_forever()


if __name__ == "__main__":
  main()
