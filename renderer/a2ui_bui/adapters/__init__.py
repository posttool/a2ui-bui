# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Every catalog component's BUI adapter; importing registers them."""

import importlib

for _m in ("layout", "values", "choice", "buttons", "views", "menus", "editors", "nodes", "files"):
    try:
        importlib.import_module(f"{__name__}.{_m}")
    except ModuleNotFoundError as e:  # groups land incrementally
        if e.name != f"{__name__}.{_m}":
            raise

from .base import REGISTRY  # noqa: E402,F401
