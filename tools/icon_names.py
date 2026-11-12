# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check prompt/icons.json against the icons BUI really ships (run with the
renderer venv). Drops names BUI does not have; --all lists every BUI icon."""

import json
import pathlib
import sys

import bui  # noqa: F401
import buipy

real = set(buipy.kit_icon_names())
if "--all" in sys.argv:
    print("\n".join(sorted(real)))
    sys.exit(0)
path = pathlib.Path(__file__).resolve().parent.parent / "prompt" / "icons.json"
data = json.loads(path.read_text())
bad = [i for i in data["icons"] if i not in real]
data["icons"] = [i for i in data["icons"] if i in real]
path.write_text(json.dumps(data, indent=1) + "\n")
print(f"{len(data['icons'])} icons OK; dropped {len(bad)}: {bad}")
