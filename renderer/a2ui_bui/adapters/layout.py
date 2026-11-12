# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Layout: Column Row Split Grid Box Panel Tabs SideTabs ScrollView Area."""

from __future__ import annotations

import buipy
import bui.components as C

from .. import props as P
from .base import adapter, apply_common, common_kw, icon

_SPACING = {"none": 0.0, "small": 0.15, "normal": None, "large": 0.6}


def _stack_kw(node) -> dict:
    kw = common_kw(node)
    if P.get_bool(node, "align"):
        kw["align"] = True
    sp = P.get(node, "spacing")
    if sp in _SPACING and _SPACING[sp] is not None:
        kw["spacing"] = round(_SPACING[sp] * buipy.kit_unit())
    pad = P.get_num(node, "padding")
    if pad:
        kw["padding"] = round(pad * buipy.kit_unit())
    return kw


def _kids(view, node, key="children"):
    return [view.build(c) for c in P.children(node, key)]


@adapter("Column", children=("children",))
def column(view, node):
    return C.Column(*_kids(view, node), **_stack_kw(node))


@adapter("Row", children=("children",))
def row(view, node):
    kids = _kids(view, node)
    just = P.get(node, "justify")
    if just in ("center", "end", "spaceBetween") and kids:
        # Blender rows have no justify; emulate with Spacers that take the slack.
        def sp():
            return C.Spacer()
        if just == "end":
            kids = [sp()] + kids
        elif just == "center":
            kids = [sp()] + kids + [sp()]
        else:
            out = []
            for i, k in enumerate(kids):
                if i:
                    out.append(sp())
                out.append(k)
            kids = out
        w = C.Row(**_stack_kw(node))
        for k in kids:
            if not isinstance(k, C.Spacer):
                k.weight = 0
            w.add(k)
        return w
    return C.Row(*kids, **_stack_kw(node))


@adapter("Split")
def split(view, node):
    left, right = P.child(node, "left"), P.child(node, "right")
    lw = view.build(left) if left else C.Label("")
    rw = view.build(right) if right else C.Label("")
    return C.Split(lw, rw, factor=P.get_num(node, "factor", 0.4), **common_kw(node))


@adapter("Grid", children=("children",))
def grid(view, node):
    kw = _stack_kw(node)
    return C.Grid(*_kids(view, node), columns=int(P.get_num(node, "columns", 2) or 2), **kw)


@adapter("Box", children=("children",))
def box(view, node):
    return C.Box(*_kids(view, node), **_stack_kw(node))


def _panel_apply(view, node, w, key, value):
    if key == "collapsed":
        w.collapsed = bool(value)
        return True
    return apply_common(w, key, value)


@adapter("Panel", live=("collapsed",), children=("children",), apply=_panel_apply,
         container=lambda w: w.body)
def panel(view, node):
    header = _kids(view, node, "header")
    w = C.Panel(P.get_str(node, "title"), *_kids(view, node),
                collapsed=P.get_bool(node, "collapsed"), icon=icon(P.get(node, "icon")),
                header=header, **common_kw(node))

    def toggled(collapsed):
        P.write(node, "collapsed", bool(collapsed))
        P.fire(node, {"collapsed": bool(collapsed)})
    w.on_toggle = toggled
    return w


def _pages(view, node):
    pages = []
    for t in P.get(node, "tabs", []) or []:
        if not isinstance(t, dict):
            continue
        ch = t.get("child")
        pages.append((t, view.build(ch) if P.is_node(ch) else C.Label("")))
    return pages


def _tabs_apply(view, node, w, key, value):
    if key == "current":
        try:
            i = int(value or 0)
        except (TypeError, ValueError):
            return True
        if hasattr(w, "select"):      # Tabs
            w.select(i)
        else:                          # SideTabs
            w.current = i
        return True
    return apply_common(w, key, value)


def _bind_current(node, w):
    def changed(i):
        P.write(node, "current", int(i))
        P.fire(node, {"current": int(i)})
    w.on_change = changed
    return w


@adapter("Tabs", live=("current",), apply=_tabs_apply)
def tabs(view, node):
    pages = [(str(P.unwrap(t.get("title", ""))), c) for t, c in _pages(view, node)]
    return _bind_current(node, C.Tabs(pages, current=int(P.get_num(node, "current", 0) or 0),
                                      **common_kw(node)))


@adapter("SideTabs", live=("current",), apply=_tabs_apply)
def side_tabs(view, node):
    pages = [(icon(t.get("icon")) or "PROPERTIES", str(P.unwrap(t.get("title", ""))), c)
             for t, c in _pages(view, node)]
    return _bind_current(node, C.SideTabs(pages, current=int(P.get_num(node, "current", 0) or 0),
                                          **common_kw(node)))


@adapter("ScrollView")
def scroll_view(view, node):
    ch = P.child(node, "child")
    inner = view.build(ch) if ch else C.Column()
    return C.ScrollView(inner, rows=P.get_num(node, "rows", 8) or 8, **common_kw(node))


@adapter("Area")
def area(view, node):
    ch = P.child(node, "child")
    body = view.build(ch) if ch else C.Column()
    editor = P.get_str(node, "editor", "Properties")
    header = _kids(view, node, "header")

    def on_editor(name):
        P.write(node, "editor", name)
        P.fire(node, {"editor": name})
    kw = common_kw(node)
    h = P.get_num(node, "height")
    w = C.Area(editor, body, header=header, on_editor=on_editor, **kw)
    if h:
        w.set("height", float(h))
    return w
