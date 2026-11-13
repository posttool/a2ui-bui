# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sandbox isolation tests (bwrap on Linux)."""

import sys
from pathlib import Path

import pytest

from a2ui_bui.apps.runtime import SDK_DIR
from a2ui_bui.apps.sandbox import SandboxPolicy, select_sandbox

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="bwrap tests are Linux-only")


def test_bwrap_blocks_network_and_host_files(tmp_path):
    sb = select_sandbox("bwrap")
    backend = tmp_path / "backend"
    storage = tmp_path / "storage"
    backend.mkdir()
    storage.mkdir()
    probe = (
        "import os, socket, sys\n"
        f"assert not os.path.exists({str(Path.home() / '.config')!r}), 'host .config leaked'\n"
        "try:\n"
        "  socket.create_connection(('1.1.1.1', 80), timeout=0.5)\n"
        "  raise AssertionError('network should be blocked')\n"
        "except OSError:\n"
        "  pass\n"
        "try:\n"
        "  open('/app/backend/evil.py', 'w').write('x')\n"
        "  raise AssertionError('backend should be read-only')\n"
        "except OSError:\n"
        "  pass\n"
        "open('/app/storage/ok.txt', 'w').write('hi')\n"
        "print('ALL_BLOCKED')\n"
    )
    res = sb.run(
        ["/usr/bin/python3", "-I", "-c", probe],
        sdk_dir=SDK_DIR,
        backend_dir=backend,
        storage_dir=storage,
        policy=SandboxPolicy(cpu_seconds=5),
    )
    assert res.returncode == 0, res.stderr
    assert "ALL_BLOCKED" in res.stdout
    assert (storage / "ok.txt").read_text() == "hi"
    assert not (backend / "evil.py").exists()


def test_bwrap_enforces_memory_limit(tmp_path):
    sb = select_sandbox("bwrap")
    backend = tmp_path / "backend"
    storage = tmp_path / "storage"
    backend.mkdir()
    storage.mkdir()
    # Try allocating 1.5 GB inside a 256 MB memory-capped sandbox.
    probe = "b = bytearray(1500 * 1024 * 1024); print('ALLOC_OK')"
    res = sb.run(
        ["/usr/bin/python3", "-I", "-c", probe],
        sdk_dir=SDK_DIR,
        backend_dir=backend,
        storage_dir=storage,
        policy=SandboxPolicy(memory_bytes=256 * 1024 * 1024, cpu_seconds=5),
    )
    assert res.returncode != 0 or "ALLOC_OK" not in res.stdout
