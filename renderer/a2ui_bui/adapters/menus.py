# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Menus: MenuBar (Blender top bar) and PieMenu (radial menu)."""

from __future__ import annotations

import logging

import bui.components as C

from .. import props as P
from .base import adapter, apply_common, common_kw, icon

log = logging.getLogger("a2ui_bui")


def _items(node, items, extra=None, on_pick=None):
    """Catalog menu items -> bui MenuItem / '-' entries. Picking calls
    ``on_pick(value)`` (default: fire the node's action with
    ``{"item": value, **extra}``)."""
    def pick(val):
        if on_pick is not None:
            return lambda *a: on_pick(val)
        return lambda *a: P.fire(node, {**(extra or {}), "item": val})

    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append("-" if it == "-" else C.MenuItem(it, pick(it)))
            continue
        if not isinstance(it, dict):
            continue
        if it.get("separator"):
            out.append("-")
            continue
        label = str(it.get("label", it.get("title", "")))
        val = it.get("value", label)
        kw = {}
        if icon(it.get("icon")):
            kw["icon"] = icon(it.get("icon"))
        if it.get("shortcut"):
            kw["shortcut"] = str(it["shortcut"])
        if it.get("checked") is not None:
            kw["checked"] = bool(it["checked"])
        if it.get("enabled") is False:
            kw["enabled"] = False
        if it.get("description"):
            kw["description"] = str(it["description"])
        if isinstance(it.get("items"), list):
            kw["submenu"] = _items(node, it["items"], extra, on_pick)
            out.append(C.MenuItem(label, **kw))
        else:
            out.append(C.MenuItem(label, pick(val), **kw))
    return out


# ===================================================================== MenuBar

def _menubar_right(w):
    return w._a2ui_right


@adapter("MenuBar", children=("right",), container=_menubar_right)
def menu_bar(view, node):
    menus = []
    for m in P.get(node, "menus", []) or []:
        if not isinstance(m, dict):
            continue
        title = str(m.get("title", m.get("label", "")))
        menus.append(C.MenuButton(title, _items(node, m.get("items"), {"menu": title}),
                                  icon=icon(m.get("icon"))))
    # The right side is one weight-0 Row so `right` children reconcile in place.
    right = C.Row(*[view.build(c) for c in P.children(node, "right")], align=True)
    w = C.MenuBar(*menus, right=[right], **common_kw(node))
    w._a2ui_right = right
    return w


# ===================================================================== PieMenu

def _pie_apply(view, node, w, key, value):
    if key == "value":
        return True            # the button label does not show the pick
    if key == "text":
        w.text = str(value or "")
        return True
    return apply_common(w, key, value)


def _pie_open(view, node, at=None):
    def picked(val):
        P.write(node, "value", val)
        P.fire(node, {"item": val, "value": val})

    items = _items(node, P.get(node, "items", []), on_pick=picked)
    ctx = getattr(view.renderer, "ctx", None)
    if ctx is None:
        log.warning("PieMenu: no window context; cannot open the pie")
        return False
    if len(items) > 8:
        log.info("PieMenu: %d items; BUI folds past 8 into \"More\"", len(items))
    C.PieMenu.show(ctx, items, P.get_str(node, "title"), at)
    return True


@adapter("PieMenu", live=("value", "text"), apply=_pie_apply)
def pie_menu(view, node):
    text = P.get_str(node, "text") or P.get_str(node, "title") or "Pie Menu"
    hk = P.get_str(node, "hotkey").strip()
    desc = P.get_str(node, "description")
    if hk and not desc:
        desc = f"Open the {P.get_str(node, 'title') or 'pie'} menu ({hk.upper()})"
    kw = common_kw(node)
    if desc:
        kw["description"] = desc
    w = C.Button(text, lambda *a: _pie_open(view, node), icon=icon(P.get(node, "icon")), **kw)
    if hk:
        _bind(view.renderer, hk.lower(), lambda: _pie_open(view, node))
    return w


def _bind(renderer, combo, fn):
    """Window hotkey: through ``renderer.bind`` (queues until a host attaches
    a context) when available, else straight on the context."""
    try:
        if callable(getattr(renderer, "bind", None)):
            renderer.bind(combo, fn)
        elif getattr(renderer, "ctx", None) is not None:
            renderer.ctx.bind(combo, fn)
    except Exception as e:  # noqa: BLE001 - bad combo: keep the button
        log.warning("PieMenu hotkey %r: %s", combo, e)
