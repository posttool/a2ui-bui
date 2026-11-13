# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Linux sandbox: bubblewrap + prlimit (+ systemd user scope when available)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Sandbox, SandboxPolicy


def _has_systemd_scope() -> bool:
    if not shutil.which("systemd-run"):
        return False
    try:
        r = subprocess.run(
            ["systemd-run", "--user", "--scope", "-q", "true"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


class BwrapSandbox(Sandbox):
    name = "bwrap"

    def __init__(self) -> None:
        self._systemd = _has_systemd_scope()
        self._tested = False

    def _build_cmd(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
    ) -> list[str]:
        bwrap_cmd = ["bwrap"]
        if not policy.allow_network:
            bwrap_cmd.append("--unshare-all")
        else:
            bwrap_cmd += ["--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup"]
        bwrap_cmd += [
            "--die-with-parent",
            "--new-session",
            "--clearenv",
        ]
        for sysdir in ("/usr", "/lib", "/lib64", "/bin", "/etc/alternatives"):
            if Path(sysdir).exists():
                bwrap_cmd += ["--ro-bind", sysdir, sysdir]
        # On corp Linux / Google workstations, home lives under /usr/local/google.
        # Mask it so binding /usr read-only never exposes ~/.config or credentials.
        if Path("/usr/local/google").exists():
            bwrap_cmd += ["--tmpfs", "/usr/local/google"]
        bwrap_cmd += [
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--ro-bind", str(sdk_dir), "/sdk",
            "--ro-bind", str(backend_dir), "/app/backend",
            "--bind", str(storage_dir), "/app/storage",
            "--chdir", "/app",
            "--setenv", "PYTHONPATH", "/sdk:/app/backend",
            "--setenv", "HOME", "/app/storage",
            "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "A2UI_APP_STORAGE", "/app/storage",
            "--setenv", "A2UI_APP_BACKEND", "/app/backend",
        ]
        bwrap_cmd += cmd

        # Do NOT pass --nproc to prlimit: it breaks bwrap's user-namespace creation.
        # Use systemd-run --user --scope TasksMax instead when available.
        prefix: list[str] = []
        if self._systemd:
            prefix += [
                "systemd-run", "--user", "--scope", "-q",
                f"-p", f"MemoryMax={policy.memory_bytes}",
                f"-p", f"TasksMax={policy.max_tasks}",
            ]
        if shutil.which("prlimit"):
            as_bytes = max(policy.memory_bytes * 2, 1024 * 1024 * 1024)
            prefix += ["prlimit", f"--as={as_bytes}", f"--cpu={policy.cpu_seconds}"]
        return prefix + bwrap_cmd

    def spawn(
        self,
        cmd: list[str],
        *,
        sdk_dir: Path,
        backend_dir: Path,
        storage_dir: Path,
        policy: SandboxPolicy,
    ) -> subprocess.Popen:
        if not self._tested:
            self._tested = True
            self.self_test(sdk_dir, storage_dir)
        full_cmd = self._build_cmd(
            cmd, sdk_dir=sdk_dir, backend_dir=backend_dir,
            storage_dir=storage_dir, policy=policy,
        )
        return subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def self_test(self, sdk_dir: Path, tmp_dir: Path) -> None:
        """Refuse to run app code if host ~/.config is readable or network works."""
        cfg = str(Path.home() / ".config")
        probe = (
            "import os, socket, sys\n"
            f"if os.path.exists({cfg!r}): sys.exit(2)\n"
            "try:\n"
            "  socket.create_connection(('1.1.1.1', 80), timeout=0.5)\n"
            "  sys.exit(3)\n"
            "except OSError:\n"
            "  pass\n"
            "print('SANDBOX_OK')\n"
        )
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "b").mkdir()
            (dp / "s").mkdir()
            full_cmd = self._build_cmd(
                ["/usr/bin/python3", "-I", "-c", probe],
                sdk_dir=sdk_dir, backend_dir=dp / "b", storage_dir=dp / "s",
                policy=SandboxPolicy(cpu_seconds=5),
            )
            r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
            if r.returncode != 0 or "SANDBOX_OK" not in r.stdout:
                raise RuntimeError(
                    f"bwrap sandbox self-test failed (rc={r.returncode}): {r.stderr.strip()}"
                )
