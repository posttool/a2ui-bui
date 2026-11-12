# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Workarounds for a2ui-core (0.6.0) behaviour that disagrees with the A2UI v1.0
schema. Each patch is a no-op once a2ui-core behaves per spec.

1. ChildList templates: the v1.0 schema (common_types.json#/$defs/ChildList)
   defines a template as ``{"componentId": ..., "path": "/list"}``, but
   ``GenericBinder._bind_structural_template`` reads only ``template["@path"]``
   at v1.0, so every templated list resolved to ``[]``. Accept ``path`` when
   ``@path`` is absent.
"""

from __future__ import annotations

from a2ui.core.resolution import generic_binder as _gb

_orig = _gb.GenericBinder._bind_structural_template


def _bind_structural_template(self, value, path, is_sync):
    if self.context.data_context.at_least_v10 and isinstance(value, dict):
        t = value.get("template") if "template" in value else value
        if isinstance(t, dict) and "componentId" in t and "@path" not in t and isinstance(t.get("path"), str):
            t2 = {**t, "@path": t["path"]}
            value = {**value, "template": t2} if "template" in value else t2
    return _orig(self, value, path, is_sync)


if not getattr(_gb.GenericBinder, "_a2ui_bui_patched", False):
    _gb.GenericBinder._bind_structural_template = _bind_structural_template
    _gb.GenericBinder._a2ui_bui_patched = True
