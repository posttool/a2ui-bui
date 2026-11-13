# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export a self-contained app folder + Dockerfile + run script."""

from __future__ import annotations

import shutil
from pathlib import Path

from .model import AppRecord


def export_app(app: AppRecord, out_dir: Path | str) -> Path:
    dest = Path(out_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    app_dest = dest / "app"
    if app_dest.exists():
        shutil.rmtree(app_dest)
    shutil.copytree(app.root, app_dest)

    # Copy the renderer package and minimal web shell so the bundle is standalone.
    repo_root = Path(__file__).resolve().parents[3]
    rend_dest = dest / "renderer"
    if rend_dest.exists():
        shutil.rmtree(rend_dest)
    shutil.copytree(
        repo_root / "renderer",
        rend_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", "tests"),
    )
    for fname in ("server.py", "app.css", "viewport.js", "models.json", "LICENSE"):
        src = repo_root / fname
        if src.exists():
            shutil.copy2(src, dest / fname)
    for dname in ("bui", "assets", "prompt"):
        src = repo_root / dname
        if src.exists():
            if (dest / dname).exists():
                shutil.rmtree(dest / dname)
            shutil.copytree(src, dest / dname)

    (dest / "requirements.txt").write_text("a2ui-core>=0.6\nblenderui>=0.5\nlitellm>=1.100\ngoogle-adk>=2.14\n")
    run_sh = dest / "run.sh"
    run_sh.write_text(
        "#!/usr/bin/env sh\n"
        "set -e\n"
        "export A2UI_BUI_APPS=\"$(dirname \"$0\")\"\n"
        "exec python3 server.py --port \"${PORT:-8230}\" --app app \"$@\"\n"
    )
    run_sh.chmod(0o755)
    (dest / "Dockerfile").write_text(
        "FROM python:3.13-slim\n"
        "WORKDIR /srv\n"
        "COPY . /srv\n"
        "RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e renderer/\n"
        "EXPOSE 8230\n"
        "CMD [\"python3\", \"server.py\", \"--host\", \"0.0.0.0\", \"--port\", \"8230\", \"--sandbox\", \"none\"]\n"
    )
    return dest
