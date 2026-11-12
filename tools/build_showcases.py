#!/usr/bin/env python3
# Copyright 2026 posttool
# SPDX-License-Identifier: Apache-2.0

"""Writes showcases/*.json and showcases/index.json from the Python showcase definitions.

  python3 tools/build_showcases.py && node tools/validate_showcases.mjs
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import showcases_apps as A  # noqa: E402
import showcases_blender1 as B1  # noqa: E402
import showcases_blender2 as B2  # noqa: E402
import showcases_blender3 as B3  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOWCASES = [
    ("Blender editors", "object-properties", B1.object_properties),
    ("Blender editors", "render-settings", B1.render_settings),
    ("Blender editors", "material-editor", B1.material_editor),
    ("Blender editors", "shader-nodes", B1.shader_nodes),
    ("Blender editors", "outliner", B2.outliner),
    ("Blender editors", "light-setup", B2.light_setup),
    ("Blender editors", "top-bar", B3.top_bar),
    ("Blender editors", "animation", B3.animation),
    ("Blender editors", "text-editor", B3.text_editor),
    ("Blender editors", "keymap-preferences", B2.keymap_prefs),
    ("Blender editors", "file-export", B2.file_export),
    ("Creative tools", "color-grading", B2.color_grading),
    ("Creative tools", "asset-browser", B3.asset_browser),
    ("Creative tools", "photo-editor", A.photo_editor),
    ("Creative tools", "synth-patch", A.synth_patch),
    ("Creative tools", "character-creator", A.character_creator),
    ("Apps & dashboards", "weather-station", A.weather_dashboard),
    ("Apps & dashboards", "smart-home", A.smart_home),
    ("Apps & dashboards", "project-tracker", A.task_tracker),
    ("Data & ops", "render-farm", A.render_farm),
    ("Data & ops", "cicd-pipeline", A.cicd_pipeline),
    ("Data & ops", "drone-mission", A.drone_mission),
]


def main():
  index = []
  for group, slug, fn in SHOWCASES:
    sc = fn()
    (ROOT / "showcases" / f"{slug}.json").write_text(json.dumps(sc, indent=1, ensure_ascii=False) + "\n")
    index.append({"file": f"{slug}.json", "group": group})
  (ROOT / "showcases" / "index.json").write_text(json.dumps({"showcases": index}, indent=1) + "\n")
  print(f"wrote {len(index)} showcases")


if __name__ == "__main__":
  main()
