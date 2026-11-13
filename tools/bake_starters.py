#!/usr/bin/env python3
# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pre-generates the Create tab's starter examples through the live pipeline.

  python3 tools/bake_starters.py [ids...] [--url http://127.0.0.1:8230] [--model gemini-3.8-flash] [-j 4]

For each starter in starters/index.json: POST /api/generate (same prompt,
system prompt and parser the browser uses), validate with bui/validate.js
(node), run one repair round with the validation errors if needed, then write
starters/<id>.json {prompt, meta, messages, model, ms} and set "cached": true
in the index. Starters stay one click away even without an API key.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import subprocess
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent

VALIDATE_JS = """
const {validateMessages} = await import(process.argv[1]);
const msgs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const r = validateMessages(msgs);
console.log(JSON.stringify({errors: r.errors, warnings: r.warnings.length, usage: r.usage}));
"""


def validate(messages: list) -> dict:
  p = subprocess.run(["node", "--input-type=commonjs", "-e",
                      "(async()=>{" + VALIDATE_JS.replace("await import(process.argv[1])",
                                                          f"await import('{(ROOT / 'bui/validate.js').as_uri()}')") + "})()"],
                     input=json.dumps(messages), capture_output=True, text=True, timeout=60)
  if p.returncode:
    raise RuntimeError(p.stderr[-800:])
  return json.loads(p.stdout)


def generate(url: str, body: dict) -> dict:
  req = urllib.request.Request(url + "/api/generate", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
  out = {"messages": [], "meta": None, "model": "", "ms": 0, "error": ""}
  with urllib.request.urlopen(req, timeout=600) as resp:
    for raw in resp:
      line = raw.decode().strip()
      if not line.startswith("data:"):
        continue
      ev = json.loads(line[5:])
      if ev["type"] == "message":
        out["messages"].append(ev["message"])
      elif ev["type"] == "meta":
        out["meta"] = ev["meta"]
      elif ev["type"] == "done":
        out["model"], out["ms"] = ev["model"], ev["ms"]
      elif ev["type"] == "error":
        out["error"] = ev["error"]
  return out


def bake(url: str, model: str, st: dict) -> tuple[str, str]:
  t0 = time.time()
  out = generate(url, {"prompt": st["prompt"], "model": model})
  if out["error"] and not out["messages"]:
    return st["id"], f"ERROR {out['error']}"
  v = validate(out["messages"])
  note = ""
  if v["errors"]:
    fix = generate(url, {"prompt": st["prompt"], "model": model, "previous": out["messages"], "errors": v["errors"]})
    if fix["messages"]:
      v2 = validate(fix["messages"])
      if len(v2["errors"]) < len(v["errors"]):
        fix["ms"] += out["ms"]
        out, v, note = fix, v2, " (repaired)"
  (ROOT / "starters" / f"{st['id']}.json").write_text(json.dumps({
      "prompt": st["prompt"], "meta": out["meta"], "model": out["model"], "ms": out["ms"],
      "messages": out["messages"]}, indent=1) + "\n")
  comps = sum(v["usage"].values())
  return st["id"], (f"OK {len(out['messages'])} msgs, {comps} comps, {len(v['usage'])} kinds, "
                    f"{len(v['errors'])} errors, {v['warnings']} warns, {time.time() - t0:.0f}s{note}")


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("ids", nargs="*")
  ap.add_argument("--url", default="http://127.0.0.1:8230")
  ap.add_argument("--model", default="gemini-3.8-flash")
  ap.add_argument("-j", type=int, default=4)
  args = ap.parse_args()
  idx_path = ROOT / "starters/index.json"
  index = json.loads(idx_path.read_text())
  todo = [s for s in index["starters"] if not args.ids or s["id"] in args.ids]
  with concurrent.futures.ThreadPoolExecutor(args.j) as ex:
    for sid, msg in ex.map(lambda s: bake(args.url, args.model, s), todo):
      print(f"{sid:20s} {msg}", flush=True)
  index = json.loads(idx_path.read_text())
  for s in index["starters"]:
    s["cached"] = (ROOT / "starters" / f"{s['id']}.json").exists()
  idx_path.write_text(json.dumps(index, indent=1) + "\n")


if __name__ == "__main__":
  main()
