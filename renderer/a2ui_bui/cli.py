# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""a2ui-bui: render A2UI surfaces with BUI.

    a2ui-bui --showcase shader-nodes                 # native window
    a2ui-bui --showcase shader-nodes --screenshot out.png [--theme light]
    a2ui-bui --showcase all --screenshot /tmp/shots/       # every showcase, one PNG each
    a2ui-bui --file messages.jsonl                    # any A2UI v1.0 JSON / JSON Lines
    a2ui-bui --connect http://host:8230 --prompt "make me a shader editor"
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import queue
from pathlib import Path

from .renderer import REPO, BuiRenderer


def load_showcase(name: str) -> dict:
    for d in ("showcases", "starters"):
        p = REPO / d / f"{name}.json"
        if p.exists():
            return json.loads(p.read_text())
    raise SystemExit(f"no showcase or starter named {name!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="a2ui-bui", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--showcase", help="showcases/<name>.json or starters/<name>.json")
    src.add_argument("--file", help="A2UI messages: JSON array, {messages:[...]}, or JSON Lines")
    src.add_argument("--connect", help="server.py base URL; stream a live generation (needs --prompt)")
    ap.add_argument("--prompt", help="prompt for --connect")
    ap.add_argument("--screenshot", help="render headless to this PNG and exit")
    ap.add_argument("--size", help="WxH (default: showcase width x natural height)")
    ap.add_argument("--theme", choices=("dark", "light"), default="dark")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any renderer error")
    ap.add_argument("--actions", action="store_true", help="print action payloads as JSON Lines")
    a = ap.parse_args(argv)

    import bui
    bui.set_theme(a.theme)

    if a.showcase == "all":
        if not a.screenshot:
            raise SystemExit("--showcase all needs --screenshot DIR")
        out = Path(a.screenshot)
        out.mkdir(parents=True, exist_ok=True)
        ids = [s["file"][:-5] for s in json.loads((REPO / "showcases" / "index.json").read_text())["showcases"]]
        failed = 0
        for sid in ids:
            argv2 = ["--showcase", sid, "--screenshot", str(out / f"{sid}.png"), "--theme", a.theme]
            if a.size:
                argv2 += ["--size", a.size]
            if a.strict:
                argv2.append("--strict")
            failed += main(argv2)
        print(f"{len(ids) - failed}/{len(ids)} showcases OK")
        return 1 if failed else 0

    actions_out = (lambda p: print(json.dumps(p), flush=True)) if a.actions else None
    r = BuiRenderer(on_action=actions_out)
    width, title = 900, "A2UI × BUI"
    messages = []
    if a.showcase:
        sc = load_showcase(a.showcase)
        messages, width, title = sc["messages"], int(sc.get("width") or 900), sc.get("name", a.showcase)
    elif a.file:
        text = Path(a.file).read_text()
        data = json.loads(text) if text.lstrip()[:1] in "[{" and "\n{" not in text.strip() else None
        if isinstance(data, dict):
            messages, width = data.get("messages", [data]), int(data.get("width") or 900)
        elif isinstance(data, list):
            messages = data
        else:
            messages = text
    w_req, h_req = (int(x) for x in a.size.lower().split("x")) if a.size else (width, 0)

    if a.screenshot:
        from .hosts.headless import HeadlessHost
        r.process(messages)
        host = HeadlessHost(r, (w_req, h_req or 2000))
        host.frame(full=True)
        if not h_req:
            nh = host.natural_size()[1]
            host.resize(w_req, max(120, min(int(nh) + 2, 4000)))
        Path(a.screenshot).write_bytes(host.screenshot())
        errs = [e for e in r.errors]
        for e in errs:
            print("error:", e.get("code"), e.get("message", "")[:300], file=sys.stderr)
        print(f"wrote {a.screenshot} {host.size[0]}x{host.size[1]}  actions={len(r.actions)} errors={len(errs)}")
        return 1 if (a.strict and errs) else 0

    from .hosts.native import NativeHost
    host = NativeHost(r, title=title, size=(w_req, h_req or 720))
    if a.connect:
        if not a.prompt:
            raise SystemExit("--connect needs --prompt")
        from .client import stream_generation
        q: "queue.Queue" = queue.Queue()
        threading.Thread(target=lambda: stream_generation(a.connect, a.prompt, q.put), daemon=True).start()
        host.feed_queue(q)
    else:
        r.process(messages)
    host.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
