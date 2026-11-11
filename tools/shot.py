#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Screenshot + error check for the A2UI x BUI demo (headless Chrome, stdlib).

  python3 tools/shot.py                      # every showcase -> /tmp/bui_shots/<id>.png
  python3 tools/shot.py object-properties    # one or more ids
  python3 tools/shot.py --theme light --out /tmp/x

Starts a static server on --port (default 8231) over the demo dir unless
--url is given. Prints per-showcase render errors, console errors and the
window size; exits 1 if any showcase has errors.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cdp import Browser  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def serve(port: int) -> None:
  handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
  handler.log_message = lambda *a, **k: None  # quiet
  srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
  threading.Thread(target=srv.serve_forever, daemon=True).start()


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("ids", nargs="*")
  ap.add_argument("--port", type=int, default=8231)
  ap.add_argument("--url", default="")
  ap.add_argument("--out", default="/tmp/bui_shots")
  ap.add_argument("--theme", default="dark")
  ap.add_argument("--scale", default="1.25")
  ap.add_argument("--width", type=int, default=1680)
  ap.add_argument("--full", action="store_true", help="whole page instead of the window")
  ap.add_argument("--eval", default="", help="JS to run after render (interaction tests)")
  ap.add_argument("--index", default="showcases/index.json", help="showcase index (relative to demo root)")
  args = ap.parse_args()

  base = args.url
  if not base:
    serve(args.port)
    base = f"http://127.0.0.1:{args.port}/"
  out = pathlib.Path(args.out)
  out.mkdir(parents=True, exist_ok=True)
  index = json.loads((ROOT / args.index).read_text())
  ids = args.ids or [e["file"].removesuffix(".json") for e in index["showcases"]]
  bad = 0
  with Browser(width=args.width, height=1100) as b:
    page = b.page
    page.navigate(base + "index.html")
    page.evaluate(f"localStorage.setItem('bui-demo.theme', {json.dumps(args.theme)});"
                  f"localStorage.setItem('bui-demo.scale', {json.dumps(args.scale)})")
    page.navigate(base + "index.html?index=" + args.index + "&t=" + str(time.time()))
    page.wait_for("window.__demo && window.__demo.ready", timeout=20)
    for sid in ids:
      page.evaluate(f"window.__demo.select({json.dumps(sid)})")
      time.sleep(0.9)
      if args.eval:
        page.evaluate(args.eval)
        time.sleep(0.6)
      info = page.evaluate("""(() => {
        const w = document.querySelector(args_full ? 'body' : '.window').getBoundingClientRect();
        const errs = document.querySelector('#errors');
        return {x: w.left, y: w.top, w: w.width, h: w.height,
                errors: errs && !errs.hidden ? errs.textContent : '',
                missing: [...document.querySelectorAll('.bui-surface *')].filter(e => e.tagName.startsWith('BUI-') && !customElements.get(e.tagName.toLowerCase())).map(e => e.tagName)};
      })()""".replace("args_full", "true" if args.full else "false"))
      h = max(200, min(info["h"], 6000))
      page.set_viewport(args.width, int(info["y"] + h + 40))
      time.sleep(0.25)
      path = out / f"{sid}.png"
      page.screenshot(str(path), clip={"x": info["x"], "y": info["y"], "width": info["w"], "height": h, "scale": 1})
      console = [c for c in getattr(page, "console", []) if c.get("level") in ("error",)]
      if hasattr(page, "console"):
        page.console.clear()
      status = "OK " if not info["errors"] and not console else "ERR"
      if status == "ERR":
        bad += 1
      print(f"{status} {sid:32s} {int(info['w'])}x{int(h)} -> {path}")
      if info["errors"]:
        print("   render:", info["errors"][:1500].replace("\n", "\n   render: "))
      for c in console[:8]:
        print("   console:", str(c.get("text", c))[:400])
  return 1 if bad else 0


if __name__ == "__main__":
  sys.exit(main())
