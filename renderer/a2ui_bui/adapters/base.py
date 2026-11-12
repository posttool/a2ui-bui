# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Adapter protocol: one adapter per catalog component type.

An adapter turns an ``a2ui_core`` ``ComponentNode`` into a real BUI component
(``bui.components.*``) and keeps it in sync:

* ``create(view, node)`` builds the widget (children via ``view.build``).
* ``live`` names props that update in place (two-way values, text); a change
  to any *other* non-structural prop rebuilds the widget (cheap for leaves).
* ``children`` names structural props reconciled in place by ``sync``
  (containers keep their scroll position, open menus and drag state).
* ``apply(view, node, widget, key, value)`` sets one live prop.

Register with the ``@adapter("Type", live=(...), children=(...))`` decorator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import buipy

from .. import props as P

REGISTRY: dict[str, "Adapter"] = {}


@dataclass
class Adapter:
    type: str
    create: Callable[[Any, Any], Any]
    live: tuple[str, ...] = ()
    children: tuple[str, ...] = ()
    apply: Callable[[Any, Any, Any, str, Any], bool] | None = None
    container: Callable[[Any], Any] | None = None     # widget -> kit node holding `children`
    meta: dict = field(default_factory=dict)


def adapter(type_name: str, *, live=(), children=(), apply=None, container=None):
    def deco(fn):
        REGISTRY[type_name] = Adapter(type_name, fn, tuple(live), tuple(children), apply, container)
        return fn
    return deco


# --------------------------------------------------------------------------- helpers

def sync_children(view, parent, nodes) -> None:
    """Make ``parent``'s kit children exactly the widgets of ``nodes``, in
    order, reusing the existing widgets of nodes already mounted."""
    desired = [view.widget_for(n) or view.build(n) for n in nodes]
    current = list(parent.children)
    want = set(map(id, desired))
    for w in current:
        if id(w) not in want:
            buipy.KitNode.remove(parent, w)
    for i, w in enumerate(desired):
        kids = parent.children
        if i < len(kids) and kids[i] is w:
            continue
        if w.parent is not None:
            buipy.KitNode.remove(w.parent, w)
        buipy.KitNode.add(parent, w, i)


def common_kw(node, natural: bool = False) -> dict:
    """Constructor keywords every bui component accepts. ``natural=True``
    keeps the widget's natural width in a Row (weight 0) unless the payload
    sets a weight: icon buttons, menu buttons, decorators, icon-only enums."""
    kw = {"weight": 0.0} if natural else {}
    d = P.get(node, "description")
    if d:
        kw["description"] = str(d)
    if P.get(node, "enabled") is False:
        kw["enabled"] = False
    w = P.get(node, "weight")
    if isinstance(w, (int, float)) and not isinstance(w, bool):
        kw["weight"] = float(w)
    return kw


def apply_common(widget, key, value) -> bool:
    if key == "enabled":
        widget.enabled = value is not False
        return True
    if key == "description":
        widget.description = str(value or "")
        return True
    if key == "weight" and isinstance(value, (int, float)):
        widget.weight = float(value)
        return True
    return False


def bind_value(node, widget, prop: str = "value", convert=lambda v: v, extra=None):
    """Two-way: widget edits write the data model path and fire ``action``
    with ``context.value`` (plus ``extra(v)``)."""
    def on_change(v):
        v = convert(v)
        P.write(node, prop, v)
        ctx = {"value": v}
        if extra is not None:
            ctx.update(extra(v))
        P.fire(node, ctx)
    widget.on_change = on_change
    return widget


def icon(name):
    """A Blender icon name if BUI knows it, else None (unknown names are dropped
    rather than drawn as a missing-icon box)."""
    if not name:
        return None
    n = str(name).upper()
    return n if n in _icons() else None


_ICONS: set | None = None


def _icons() -> set:
    global _ICONS
    if _ICONS is None:
        _ICONS = set(buipy.kit_icon_names())
    return _ICONS


def item_label(it) -> str:
    if isinstance(it, dict):
        return str(it.get("label", it.get("value", "")))
    return str(it)


def item_value(it):
    if isinstance(it, dict):
        return it.get("value", it.get("label"))
    return it


def item_icon(it):
    return icon(it.get("icon")) if isinstance(it, dict) else None


def rgba(v, default=(0.5, 0.5, 0.5, 1.0)) -> tuple:
    """Color from [r,g,b(,a)] floats 0..1 or '#rrggbb(aa)'."""
    if isinstance(v, str) and v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        try:
            parts = [int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
        except ValueError:
            return default
        return tuple(parts + [1.0] * (4 - len(parts)))[:4]
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        f = [float(x) for x in v[:4]]
        if any(x > 1.0 for x in f[:3]):
            f = [x / 255.0 for x in f[:3]] + f[3:]
        return tuple(f + [1.0] * (4 - len(f)))[:4]
    return default
