# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Buttons and feedback: Button IconButton Popover MenuButton MenuItem Label
Image Video ProgressBar Separator Spacer."""

from __future__ import annotations

import bui.components as C

from .. import assets
from .. import props as P
from .base import adapter, apply_common, common_kw, icon, rgba

# Label color roles -> RGBA (Blender theme-ish accents).
ROLE_COLORS = {
    "muted": (0.62, 0.62, 0.62, 1.0),
    "accent": (0.33, 0.55, 0.92, 1.0),
    "red": (0.92, 0.32, 0.32, 1.0),
    "green": (0.45, 0.78, 0.36, 1.0),
    "yellow": (0.95, 0.80, 0.30, 1.0),
    "orange": (0.96, 0.58, 0.24, 1.0),
    "blue": (0.33, 0.55, 0.92, 1.0),
}


def _click(node):
    return lambda *a: P.fire(node)


def _text_apply(view, node, w, key, value):
    if key == "text" and hasattr(w, "text"):
        w.text = str(value if value is not None else "")
        return True
    return apply_common(w, key, value)


@adapter("Button", live=("text",), apply=_text_apply)
def button(view, node):
    w = C.Button(P.get_str(node, "text"), _click(node), icon=icon(P.get(node, "icon")),
                 emboss=P.get_bool(node, "emboss", True), **common_kw(node))
    for prop in ("depress", "alert"):   # kit properties where this BUI build has them
        if P.get_bool(node, prop):
            try:
                w.set(prop, True)
            except KeyError:
                pass
    return w


@adapter("IconButton")
def icon_button(view, node):
    return C.IconButton(icon(P.get(node, "icon")) or "DOT", _click(node),
                        emboss=P.get_bool(node, "emboss"), **common_kw(node, natural=True))


@adapter("Popover", children=("children",), container=lambda w: w)
def popover(view, node):
    kids = [view.build(c) for c in P.children(node)]
    return C.Popover(P.get_str(node, "text"), *kids, icon=icon(P.get(node, "icon")),
                     **common_kw(node))


def menu_items(node, items, prefix=""):
    """Catalog menu items -> bui MenuItem / '-' entries; picking fires the
    node's action with context.item (value or label)."""
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append("-" if it == "-" else C.MenuItem(it, _pick(node, it)))
            continue
        if not isinstance(it, dict):
            continue
        if it.get("separator"):
            out.append("-")
            continue
        label = str(it.get("label", ""))
        val = it.get("value", label)
        kw = {}
        if icon(it.get("icon")):
            kw["icon"] = icon(it.get("icon"))
        if it.get("shortcut"):
            kw["shortcut"] = str(it["shortcut"])
        if "checked" in it and it["checked"] is not None:
            kw["checked"] = bool(it["checked"])
        if it.get("enabled") is False:
            kw["enabled"] = False
        if it.get("description"):
            kw["description"] = str(it["description"])
        if isinstance(it.get("items"), list):
            kw["submenu"] = menu_items(node, it["items"])
            out.append(C.MenuItem(label, **kw))
        else:
            out.append(C.MenuItem(label, _pick(node, val), **kw))
    return out


def _pick(node, val):
    return lambda *a: P.fire(node, {"item": val})


@adapter("MenuButton")
def menu_button(view, node):
    return C.MenuButton(P.get_str(node, "text"), menu_items(node, P.get(node, "items", [])),
                        icon=icon(P.get(node, "icon")), **common_kw(node, natural=True))


@adapter("MenuItem")
def menu_item(view, node):
    # A menu row used directly in a layout: draw it like a menu button row.
    label = P.get_str(node, "label")
    sc = P.get_str(node, "shortcut")
    checked = P.get(node, "checked")
    if checked is not None:
        w = C.Checkbox(label, bool(checked), **common_kw(node))
        w.on_change = lambda v: (P.write(node, "checked", bool(v)), P.fire(node, {"checked": bool(v)}))
        return w
    text = f"{label}    {sc}" if sc else label
    return C.Button(text, _click(node), icon=icon(P.get(node, "icon")), emboss=False,
                    **common_kw(node))


@adapter("Label", live=("text",), apply=_text_apply)
def label(view, node):
    color = P.get(node, "color")
    col = None
    if isinstance(color, str):
        col = ROLE_COLORS.get(color) or (rgba(color) if color.startswith("#") else None)
    size = P.get(node, "size")
    bold = P.get_bool(node, "bold") or size in ("large", "title")
    return C.Label(P.get_str(node, "text"), icon=icon(P.get(node, "icon")),
                   align=P.get_str(node, "align", "left") or "left", color=col, bold=bold,
                   **common_kw(node))


def _sized(w, node):
    h = P.get_num(node, "height")
    if h:
        w.set("height", float(h))
    return w


@adapter("Image")
def image(view, node):
    extra = [view.renderer.storage_dir] if getattr(view.renderer, "storage_dir", None) else ()
    path = assets.resolve(P.get_str(node, "src"), extra_roots=extra)
    if path is None or not hasattr(C, "Image"):
        return _sized(C.Label(P.get_str(node, "alt") or (path.name if path else "[image]"),
                              icon="IMAGE_DATA", **common_kw(node)), node)
    fit = P.get_str(node, "fit", "contain") or "contain"
    return _sized(C.Image(path, fit=fit if fit in C.Image.FITS else "contain", **common_kw(node)), node)


@adapter("Video")
def video(view, node):
    path = assets.resolve(P.get_str(node, "src"))
    if path is None or not hasattr(C, "Video"):
        return C.Label("[video]", icon="FILE_MOVIE")
    poster = assets.resolve(P.get_str(node, "poster"))
    w = C.Video(path, autoplay=P.get_bool(node, "autoplay", False), loop=P.get_bool(node, "loop"),
                controls=P.get_bool(node, "controls"), poster=poster,
                fit=P.get_str(node, "fit", "contain") or "contain",
                on_ended=lambda: P.fire(node, {"ended": True}), **common_kw(node))
    return _sized(w, node)


def _progress_apply(view, node, w, key, value):
    if key == "value":
        w.set_value(float(value or 0))
        return True
    if key == "text":
        w.text = str(value or "")
        return True
    return apply_common(w, key, value)


@adapter("ProgressBar", live=("value", "text"), apply=_progress_apply)
def progress_bar(view, node):
    t = P.get(node, "text")
    return C.ProgressBar(float(P.get_num(node, "value", 0) or 0),
                         None if t is None else str(t), **common_kw(node))


@adapter("Separator")
def separator(view, node):
    return C.Separator(P.get_num(node, "factor", 0.5) or 0.5, line=P.get_bool(node, "line"),
                       **common_kw(node))


@adapter("Spacer")
def spacer(view, node):
    return C.Spacer(**common_kw(node))
