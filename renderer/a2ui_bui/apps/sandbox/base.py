# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sandbox interface and platform selection."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("a2ui_bui.sandbox")


@dataclass(frozen=True)
class SandboxPolicy:
    memory_bytes: int = 512 * 1024 * 1024
    cpu_seconds: int = 30
    max_tasks: int = 64
    allow_network: bool = False
    mode: str = "auto"      # auto | bwrap | seatbelt | none


class Sandbox(ABC):
    name: str = "base"

    @abstractmethod
    def spawn(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
    ) -> subprocess.Popen:
        ...

    def run(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
        timeout: float = 30.0,
    ) -> subprocess.CompletedProcess:
        p = self.spawn(cmd, sdk_dir=sdk_dir, backend_dir=backend_dir,
                       storage_dir=storage_dir, policy=policy)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            raise TimeoutError(f"sandboxed command timed out after {timeout}s")
        return subprocess.CompletedProcess(cmd, p.returncode, out, err)

    def self_test(self, sdk_dir: Path, tmp_dir: Path) -> None:
        """Verify the sandbox blocks network & host config reads before running user code."""
        return None


def select_sandbox(mode: str = "auto") -> Sandbox:
    if mode == "none":
        from .none import Unsandboxed
        return Unsandboxed()
    if mode == "bwrap" or (mode == "auto" and sys.platform.startswith("linux") and shutil.which("bwrap")):
        from .bwrap import BwrapSandbox
        return BwrapSandbox()
    if mode == "seatbelt" or (mode == "auto" and sys.platform == "darwin" and shutil.which("sandbox-exec")):
        from .seatbelt import SeatbeltSandbox
        return SeatbeltSandbox()
    if mode == "auto":
        raise RuntimeError(
            "No OS sandbox available (bwrap on Linux, sandbox-exec on macOS). "
            "Install bubblewrap or explicitly pass sandbox='none' for trusted local use."
        )
    raise ValueError(f"unknown sandbox mode: {mode!r}")
