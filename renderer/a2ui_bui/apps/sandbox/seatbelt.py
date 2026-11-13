# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""macOS sandbox using built-in sandbox-exec (Seatbelt)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .base import Sandbox, SandboxPolicy


def _python_roots(cmd: list[str]) -> list[Path]:
    roots: set[Path] = set()
    candidates = [sys.prefix, sys.base_prefix, sys.exec_prefix]
    if cmd:
        exe = Path(cmd[0])
        candidates.extend([str(exe.parent.parent), str(exe.resolve().parent.parent)])
    for raw in candidates:
        if not raw:
            continue
        p = Path(raw)
        roots.add(p)
        try:
            roots.add(p.resolve())
        except OSError:
            pass
    return sorted(roots)


def _profile(backend_dir: Path, storage_dir: Path, allow_network: bool, extra_read: list[Path] = ()) -> str:
    home = Path.home().resolve()
    net = "(allow network*)" if allow_network else "(deny network*)"
    extra_lines = "\n".join(f'  (subpath "{p}")' for p in extra_read)
    # Deny reading user's secrets/dotfiles; allow reading system + python/venv + backend; allow writing only storage + /tmp.
    return f"""(version 1)
(deny default)
(import "system.sb")
(allow process-exec)
(allow process-fork)
(allow signal (target self))
(allow file-read-metadata)
(allow file-map-executable)
{net}
(allow file-read*
  (subpath "/System")
  (subpath "/usr")
  (subpath "/bin")
  (subpath "/sbin")
  (subpath "/Library")
  (subpath "/opt/homebrew")
  (subpath "/private/var")
  (subpath "/private/tmp")
  (subpath "/dev")
  (subpath "{backend_dir.resolve()}")
  (subpath "{storage_dir.resolve()}")
  (subpath "{Path(__file__).resolve().parents[1] / 'sdk'}")
{extra_lines})
(deny file-read*
  (subpath "{home / '.config'}")
  (subpath "{home / '.ssh'}")
  (subpath "{home / '.aws'}")
  (subpath "{home / '.gemini'}"))
(allow file-write*
  (subpath "{storage_dir.resolve()}")
  (subpath "/private/tmp")
  (subpath "/tmp"))
"""


class SeatbeltSandbox(Sandbox):
    name = "seatbelt"

    def spawn(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
    ) -> subprocess.Popen:
        prof = _profile(backend_dir, storage_dir, policy.allow_network, _python_roots(cmd))
        env = {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(storage_dir.resolve()),
            "PYTHONPATH": f"{sdk_dir}:{backend_dir}",
            "A2UI_APP_STORAGE": str(storage_dir.resolve()),
            "A2UI_APP_BACKEND": str(backend_dir.resolve()),
        }
        return subprocess.Popen(
            ["sandbox-exec", "-p", prof, *cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(storage_dir.resolve()),
            text=True,
            bufsize=1,
        )
