# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Choice: Dropdown EnumRow ColorSwatch IDSelector PathField."""

from __future__ import annotations

import bui.components as C

from .. import props as P
from .base import adapter, apply_common, common_kw, icon, item_icon, item_label, item_value, rgba


def _items(node):
    items = P.get(node, "items", []) or []
    labels = [item_label(i) for i in items]
    values = [item_value(i) for i in items]
    icons = P.get(node, "icons")
    if isinstance(icons, list) and icons:
        ic = [icon(x) or "" for x in icons]
    else:
        ic = [item_icon(i) or "" for i in items]
    return labels, values, (ic if any(ic) else None)


def _label_for(node, labels, values):
    v = P.get(node, "value")
    if v in labels:
        return v
    if v in values:
        return labels[values.index(v)]
    return labels[0] if labels else None


def _choice_apply(view, node, w, key, value):
    if key == "value":
        labels, values, _ = _items(node)
        lab = _label_for(node, labels, values)
        if lab is not None and w.value != lab:
            w.set_value(lab, notify=False)
        return True
    if key == "label":
        w.label = str(value or "")
        return True
    return apply_common(w, key, value)


def _choice(cls, node, **extra):
    labels, values, icons = _items(node)
    w = cls(P.get_str(node, "label"), labels or ["—"], _label_for(node, labels, values),
            icons=icons, icon_only=P.get_bool(node, "iconOnly"), **extra,
            **common_kw(node, natural=P.get_bool(node, "iconOnly")))

    def changed(lab):
        i = labels.index(lab) if lab in labels else -1
        v = values[i] if i >= 0 else lab
        # Keep the agent's own vocabulary: write back a value if the item has one.
        P.write(node, "value", v)
        P.fire(node, {"value": v, "index": i})
    w.on_change = changed
    return w


@adapter("Dropdown", live=("value", "label"), apply=_choice_apply)
def dropdown(view, node):
    return _choice(C.Dropdown, node)


@adapter("EnumRow", live=("value", "label"), apply=_choice_apply)
def enum_row(view, node):
    return _choice(C.EnumRow, node, vertical=P.get_bool(node, "vertical"))


def _color_apply(view, node, w, key, value):
    if key == "value":
        c = rgba(value)
        if tuple(round(x, 4) for x in w.value) != tuple(round(x, 4) for x in c):
            w.set_value(c, notify=False)
        return True
    if key == "label":
        w.label = str(value or "")
        return True
    return apply_common(w, key, value)


@adapter("ColorSwatch", live=("value", "label"), apply=_color_apply)
def color_swatch(view, node):
    raw = P.get(node, "value")
    hexmode = isinstance(raw, str)
    w = C.ColorSwatch(P.get_str(node, "label"), rgba(raw, (1, 1, 1, 1)),
                      picker=P.get_str(node, "picker", "circle") or "circle",
                      alpha=P.get_bool(node, "alpha", True), **common_kw(node))

    def changed(v):
        v = [round(float(x), 4) for x in v]
        out = C.ColorSwatch.to_text(v[:3]) if hexmode else v
        P.write(node, "value", out)
        P.fire(node, {"value": out})
    w.on_change = changed
    return w


@adapter("IDSelector")
def id_selector(view, node):
    items = [str(i) for i in (P.get(node, "items", []) or [])]
    value = P.get_str(node, "value", items[0] if items else "")

    def op(name, **ctx):
        return lambda *a: P.fire(node, {"op": name, **ctx})

    def on_change(v):
        P.write(node, "value", v)
        P.fire(node, {"op": "select", "value": v})

    w = C.IDSelector(items, value, icon=icon(P.get(node, "icon")) or "MESH_DATA",
                     fake_user=P.get_bool(node, "fakeUser"), on_change=on_change,
                     on_new=op("new"), on_unlink=op("unlink"), **common_kw(node))
    users = P.get_num(node, "users")
    if users is not None and hasattr(w, "users"):
        try:
            w.users = int(users)
        except Exception:
            pass
    return w


@adapter("PathField", live=("value",),
         apply=lambda view, node, w, key, value: _path_apply(w, key, value))
def path_field(view, node):
    def on_change(v):
        P.write(node, "value", str(v))
        P.fire(node, {"value": str(v), "op": "change"})

    def on_browse(*_):
        P.fire(node, {"op": "browse", "value": P.get_str(node, "value")})

    return C.PathField(P.get_str(node, "label"), P.get_str(node, "value"),
                       directory=P.get_bool(node, "directory"),
                       on_browse=on_browse if node.props.get("action") else None,
                       on_change=on_change, **common_kw(node))


def _path_apply(w, key, value):
    if key == "value":
        if hasattr(w, "value") and w.value != value:
            try:
                w.value = str(value or "")
            except Exception:
                return False
        return True
    return apply_common(w, key, value)
