# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Values: NumberField NumberSlider VectorField TextField TextArea SearchField
HotkeyField Checkbox Toggle Decorator."""

from __future__ import annotations

import bui.components as C

from .. import props as P
from .base import adapter, apply_common, bind_value, common_kw, icon


def _set_value(view, node, w, key, value):
    if key == "value":
        if value is not None and value != w.value:
            w.set_value(value, notify=False)
        return True
    if key == "label" and hasattr(w, "label"):
        w.label = str(value or "")
        return True
    return apply_common(w, key, value)


def _num_kw(node, keys=("min", "max", "step", "precision")):
    kw = {}
    for k in keys:
        v = P.get_num(node, k)
        if v is not None:
            kw[k] = int(v) if k == "precision" else v
    s = P.get(node, "suffix")
    if s:
        kw["suffix"] = str(s)
    return kw


@adapter("NumberField", live=("value", "label"), apply=_set_value)
def number_field(view, node):
    integer = P.get(node, "integer")
    v = P.get(node, "value", 0)
    kw = _num_kw(node)
    if integer is not None:
        kw["integer"] = bool(integer)
    if kw.get("integer"):
        v = int(round(float(v or 0)))
    w = C.NumberField(P.get_str(node, "label"), v if isinstance(v, (int, float)) else 0.0,
                      **kw, **common_kw(node))
    return bind_value(node, w)


@adapter("NumberSlider", live=("value", "label"), apply=_set_value)
def number_slider(view, node):
    kw = _num_kw(node, ("min", "max", "precision"))
    kw.setdefault("min", 0.0)
    kw.setdefault("max", 1.0)
    v = P.get(node, "value", 0.0)
    w = C.NumberSlider(P.get_str(node, "label"), float(v or 0), **kw, **common_kw(node))
    return bind_value(node, w)


def _vec_apply(view, node, w, key, value):
    if key == "value":
        if isinstance(value, (list, tuple)):
            for f, x in zip(w.fields, value):
                if x is not None and f.value != x:
                    f.set_value(x, notify=False)
        return True
    return apply_common(w, key, value)


@adapter("VectorField", live=("value",), apply=_vec_apply)
def vector_field(view, node):
    value = P.get(node, "value", [0, 0, 0]) or [0, 0, 0]
    axes = P.get_str(node, "axes", "XYZW") or "XYZW"
    kw = _num_kw(node)
    w = C.VectorField(P.get_str(node, "label"), tuple(float(x or 0) for x in value),
                      axes=axes, **kw, **common_kw(node))

    def changed(v):
        v = [float(x) for x in v]
        P.write(node, "value", v)
        P.fire(node, {"value": v})
    w.on_change = changed
    return w


@adapter("TextField", live=("value", "label"), apply=_set_value)
def text_field(view, node):
    w = C.TextField(P.get_str(node, "label"), P.get_str(node, "value"),
                    placeholder=P.get_str(node, "placeholder"), icon=icon(P.get(node, "icon")),
                    **common_kw(node))
    return bind_value(node, w, convert=str)


@adapter("SearchField", live=("value",), apply=_set_value)
def search_field(view, node):
    w = C.SearchField(P.get_str(node, "value"),
                      placeholder=P.get_str(node, "placeholder", "Search") or "Search",
                      **common_kw(node))
    return bind_value(node, w, convert=str)


@adapter("HotkeyField", live=("value", "label"), apply=_set_value)
def hotkey_field(view, node):
    w = C.HotkeyField(P.get_str(node, "label"), P.get_str(node, "value"), **common_kw(node))
    return bind_value(node, w, convert=str)


def _ta_apply(view, node, w, key, value):
    ta = getattr(w, "_a2ui_textarea", w)
    if key == "value":
        v = "" if value is None else str(value)
        if ta.value != v:
            ta.set_value(v, notify=False)
        return True
    return apply_common(w, key, value)


@adapter("TextArea", live=("value",), apply=_ta_apply)
def text_area(view, node):
    TextArea = getattr(C, "TextArea", None)
    label = P.get_str(node, "label")
    if TextArea is None:  # bui without TextArea: read-only lines
        col = C.Column(**common_kw(node))
        if label:
            col.add(C.Label(label))
        for line in P.get_str(node, "value").splitlines() or [""]:
            col.add(C.Label(line))
        return col
    rows = P.get_num(node, "rows")
    ta = TextArea(P.get_str(node, "value"), rows=int(rows) if rows else None,
                  **({} if label else common_kw(node)))
    bind_value(node, ta, convert=str)
    if not label:
        return ta
    col = C.Column(C.Label(label), ta, **common_kw(node))
    col._a2ui_textarea = ta
    return col


def _bool_apply(view, node, w, key, value):
    if key == "value":
        b = bool(value)
        if w.value != b:
            w.set_value(b, notify=False)
        return True
    if key == "label":
        w.label = str(value or "")
        return True
    return apply_common(w, key, value)


@adapter("Checkbox", live=("value", "label"), apply=_bool_apply)
def checkbox(view, node):
    w = C.Checkbox(P.get_str(node, "label"), P.get_bool(node, "value"), **common_kw(node))
    return bind_value(node, w, convert=bool)


@adapter("Toggle", live=("value", "label"), apply=_bool_apply)
def toggle(view, node):
    w = C.Toggle(P.get_str(node, "label"), P.get_bool(node, "value"),
                 icon=icon(P.get(node, "icon")), icon_on=icon(P.get(node, "iconOn")),
                 emboss=P.get_bool(node, "emboss", True), **common_kw(node))
    return bind_value(node, w, convert=bool)


# Decorator: the keyframe dot. Catalog `state` is none|keyframe|changed|driven
# (two-way); BUI's Decorator is a boolean "keyed" dot.
@adapter("Decorator", live=("state", "value"),
         apply=lambda view, node, w, key, value: _deco_apply(node, w, key))
def decorator(view, node):
    w = C.Decorator(P.get_str(node, "label"), _keyed(node), **common_kw(node, natural=not P.get_str(node, "label")))

    def changed(v):
        state = "keyframe" if v else "none"
        P.write(node, "state", state) or P.write(node, "value", state)
        P.fire(node, {"value": state, "state": state})
    w.on_change = changed
    return w


def _keyed(node) -> bool:
    s = P.get(node, "state", P.get(node, "value"))
    if isinstance(s, bool):
        return s
    return s not in (None, "", "none", False)


def _deco_apply(node, w, key):
    k = _keyed(node)
    if w.value != k:
        w.set_value(k, notify=False)
    return True
