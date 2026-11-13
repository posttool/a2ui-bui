# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit opt-in unsandboxed runner (trusted local use or inside a container)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from .base import Sandbox, SandboxPolicy

log = logging.getLogger("a2ui_bui.sandbox")


class Unsandboxed(Sandbox):
    name = "none"

    def spawn(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
    ) -> subprocess.Popen:
        log.warning("Running app backend WITHOUT OS sandbox (sandbox=none)")
        py = sys.executable if cmd and cmd[0].endswith("python3") else cmd[0]
        full = [py, *cmd[1:]]
        # Still scrub all API keys from the child environment.
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(storage_dir.resolve()),
            "PYTHONPATH": f"{sdk_dir}:{backend_dir}",
            "A2UI_APP_STORAGE": str(storage_dir.resolve()),
            "A2UI_APP_BACKEND": str(backend_dir.resolve()),
        }
        return subprocess.Popen(
            full,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(storage_dir.resolve()),
            text=True,
            bufsize=1,
        )
