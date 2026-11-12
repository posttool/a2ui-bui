# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Views: ListView (Blender UIList), TreeView (Outliner), GridView (preview tiles).

FileBrowser lives in its own module (BUI's FileBrowser component).

Each view keeps purely visual state (scroll, expansion, filter text) in the
BUI widget and writes data edits back through ``P.write`` so a bound
``items`` / ``selected`` goes back to the data model. Action context keys
follow ``bui/spec.js``: ``op`` + ``index`` / ``item`` / ``label`` /
``column`` / ``on``.
"""

from __future__ import annotations

import copy

import bui.components as C

from .. import props as P
from .base import adapter, apply_common, common_kw, icon, item_label, rgba


def _plain_list(v) -> list:
    return list(v) if isinstance(v, list) else []


# ===================================================================== ListView

def _list_rows(node):
    """[(raw_index, label, icon)] of every item, in data order."""
    items = _plain_list(P.get(node, "items", []))
    icons = P.get(node, "icons")
    icons = icons if isinstance(icons, list) else []
    out = []
    for i, it in enumerate(items):
        ic = icon(icons[i]) if i < len(icons) else None
        if ic is None and isinstance(it, dict):
            ic = icon(it.get("icon"))
        out.append((i, item_label(it), ic))
    return out


def _list_fill(lv, node, query: str = "") -> None:
    """Push the (filtered) rows into the BUI list; remember the row -> data
    index map on the widget."""
    rows = _list_rows(node)
    q = (query or "").strip().lower()
    if q:
        items = _plain_list(P.get(node, "items", []))
        def hit(r):
            it = items[r[0]]
            desc = it.get("description", "") if isinstance(it, dict) else ""
            return q in r[1].lower() or q in str(desc).lower()
        rows = [r for r in rows if hit(r)]
    lv._a2ui_map = [r[0] for r in rows]
    lv.items = [r[1] for r in rows]
    ic = [r[2] or "" for r in rows]
    lv.set("icons", ic if any(ic) else [])
    sel = _list_sel(node)
    if sel in lv._a2ui_map:
        lv.set_value(lv._a2ui_map.index(sel), notify=False)
    elif rows:
        lv.set_value(-1 if q else 0, notify=False)


def _list_sel(node) -> int:
    n = P.get_num(node, "selected", 0)
    return int(round(n)) if n is not None else 0


def _list_widget(w):
    return getattr(w, "_a2ui_list", w)


def _list_apply(view, node, w, key, value):
    lv = _list_widget(w)
    if key in ("items", "icons"):
        _list_fill(lv, node, getattr(lv, "_a2ui_query", ""))
        return True
    if key == "selected":
        sel = _list_sel(node)
        m = getattr(lv, "_a2ui_map", [])
        if sel in m and lv.value != m.index(sel):
            lv.set_value(m.index(sel), notify=False)
        return True
    return apply_common(lv, key, value)


@adapter("ListView", live=("items", "icons", "selected"), apply=_list_apply)
def list_view(view, node):
    kw = common_kw(node)
    rows = int(P.get_num(node, "rows", 5) or 5)
    lv = C.ListView([], 0, rows=max(1, rows), **{k: v for k, v in kw.items() if k != "weight"})
    lv._a2ui_query = ""
    _list_fill(lv, node)

    def changed(row):
        m = getattr(lv, "_a2ui_map", [])
        if not (0 <= int(row) < len(m)):
            return
        i = m[int(row)]
        items = _plain_list(P.get(node, "items", []))
        P.write(node, "selected", i)
        P.fire(node, {"op": "select", "index": i, "item": item_label(items[i]) if i < len(items) else ""})

    def renamed(row, label):
        m = getattr(lv, "_a2ui_map", [])
        if not (0 <= int(row) < len(m)):
            return
        i = m[int(row)]
        raw = _plain_list(P.get(node, "items", []))
        if i >= len(raw):
            return
        old = raw[i]
        old_label = item_label(old)
        label = str(label).strip()
        if not label or label == old_label:
            return
        nxt = copy.deepcopy(raw)
        if isinstance(old, dict):
            key = "label" if "label" in old or "name" not in old else "name"
            nxt[i] = {**old, key: label}
        else:
            nxt[i] = label
        P.write(node, "items", nxt)
        P.fire(node, {"op": "rename", "index": i, "item": old_label, "label": label})

    lv.on_change = changed
    lv.on_rename = renamed
    if not P.get_bool(node, "filter"):
        if "weight" in kw:
            lv.weight = kw["weight"]
        return lv

    # Blender's UIList filter row: a search field under the list.
    search = C.SearchField("", placeholder="Filter")

    def filt(q):
        lv._a2ui_query = str(q or "")
        _list_fill(lv, node, lv._a2ui_query)
    search.on_change = filt
    box = C.Column(lv, search, align=True, **({"weight": kw["weight"]} if "weight" in kw else {}))
    box._a2ui_list = lv
    return box


# ===================================================================== TreeView

# column -> (enabled icon, disabled icon). BUI's toggle value is "restricted"
# (1 = second icon), the catalog's toggles[col] is "enabled" (False = off).
COLUMN_ICONS = {
    "select": ("RESTRICT_SELECT_OFF", "RESTRICT_SELECT_ON"),
    "hide": ("HIDE_OFF", "HIDE_ON"),
    "viewport": ("RESTRICT_VIEW_OFF", "RESTRICT_VIEW_ON"),
    "render": ("RESTRICT_RENDER_OFF", "RESTRICT_RENDER_ON"),
}


def _tree_ref(it) -> str:
    if isinstance(it, dict):
        return str(it.get("id", it.get("label", it.get("name", ""))))
    return str(it)


def _tree_key(it, path) -> str:
    if isinstance(it, dict) and it.get("id") is not None:
        return "id:" + str(it["id"])
    return "p:" + "/".join(map(str, path))


def _tree_label(it) -> str:
    if isinstance(it, dict):
        return str(it.get("label", it.get("name", "")))
    return str(it)


def _tree_build(items, columns, open_state, path=()):
    out = []
    for i, raw in enumerate(items or []):
        it = raw if isinstance(raw, dict) else {"label": str(raw)}
        p = path + (i,)
        key = _tree_key(it, p)
        kids_raw = it.get("children") if isinstance(it.get("children"), list) else []
        kids = _tree_build(kids_raw, columns, open_state, p)
        ic = icon(it.get("icon")) or ("OUTLINER_COLLECTION" if kids_raw else None)
        toggles = it.get("toggles") if isinstance(it.get("toggles"), dict) else {}
        expanded = open_state.get(key, it.get("expanded") is not False)
        ti = C.TreeItem(_tree_label(it), *kids, icon=ic, expanded=expanded,
                        data={"path": p, "key": key, "ref": _tree_ref(it)},
                        toggles={c: toggles.get(c) is False for c in columns})
        out.append(ti)
    return out


def _walk(items):
    for it in items:
        yield it
        yield from _walk(it.children)


def _tree_columns(node) -> list:
    cols = P.get(node, "columns")
    return [c for c in cols if c in COLUMN_ICONS] if isinstance(cols, list) else []


def _tree_find(roots, sel):
    if sel is None or sel == "":
        return None
    sel = str(sel)
    for it in _walk(roots):
        d = it.data or {}
        if d.get("ref") == sel or it.label == sel:
            return it
    return None


def _node_at(items, path):
    """The (mutable) item dict at ``path`` inside ``items`` (strings are
    promoted to {label} in place)."""
    lst, node = items, None
    for i in path:
        if not (0 <= i < len(lst)):
            return None
        node = lst[i]
        if not isinstance(node, dict):
            node = lst[i] = {"label": str(node)}
        kids = node.get("children")
        lst = kids if isinstance(kids, list) else []
    return node


def _tree_set_roots(tv, node):
    open_state = {}
    for it in _walk(tv.roots):
        d = it.data or {}
        open_state[d.get("key")] = it.expanded
    open_state.update(getattr(tv, "_a2ui_open", {}))
    cols = _tree_columns(node)
    roots = _tree_build(_plain_list(P.get(node, "items", [])), cols, open_state)
    tv.roots = roots
    it = _tree_find(roots, P.get(node, "selected"))
    if it is not None:
        tv.set_value(it, notify=False)


def _tree_apply(view, node, tv, key, value):
    if key == "items":
        items = _plain_list(value)
        if items == getattr(tv, "_a2ui_items", None):
            return True        # our own write-back (toggle drag): tree already shows it
        tv._a2ui_items = copy.deepcopy(items)
        _tree_set_roots(tv, node)
        return True
    if key == "selected":
        it = _tree_find(tv.roots, value)
        cur = tv.value
        if it is not None and it is not cur:
            tv.set_value(it, notify=False)
        return True
    return apply_common(tv, key, value)


@adapter("TreeView", live=("items", "selected"), apply=_tree_apply)
def tree_view(view, node):
    cols = _tree_columns(node)
    rows = int(P.get_num(node, "rows", 8) or 8)
    items = _plain_list(P.get(node, "items", []))
    tv = C.TreeView(_tree_build(items, cols, {}), rows=max(1, rows), columns=cols, **common_kw(node))
    if cols:
        ics = []
        for c in cols:
            ics.extend(COLUMN_ICONS[c])
        tv.set("icons", ics)
    tv._a2ui_items = copy.deepcopy(items)
    it = _tree_find(tv.roots, P.get(node, "selected"))
    if it is not None:
        tv.set_value(it, notify=False)

    def changed(item):
        if item is None:
            return
        ref = (item.data or {}).get("ref", item.label)
        P.write(node, "selected", ref)
        P.fire(node, {"op": "select", "item": ref})

    def write_items(mutate):
        work = copy.deepcopy(_plain_list(P.get(node, "items", [])))
        if not mutate(work):
            return False
        tv._a2ui_items = copy.deepcopy(work)
        P.write(node, "items", work)
        return True

    def toggled(item, column, restricted):
        d = item.data or {}
        on = not restricted

        def mut(work):
            n = _node_at(work, d.get("path", ()))
            if n is None:
                return False
            n["toggles"] = {**(n.get("toggles") or {}), column: on}
            return True
        write_items(mut)
        P.fire(node, {"op": "toggle", "item": d.get("ref", item.label), "column": column, "on": on})

    def renamed(item, label):
        d = item.data or {}
        label = str(label).strip()
        holder = {}

        def mut(work):
            n = _node_at(work, d.get("path", ()))
            if n is None or not label or label == _tree_label(n):
                return False
            holder["old"] = _tree_ref(n)
            n["label" if "label" in n or "name" not in n else "name"] = label
            return True
        if write_items(mut):
            had_id = "id:" in str(d.get("key", ""))
            if not had_id and str(P.get(node, "selected", "")) == holder["old"]:
                P.write(node, "selected", label)
            P.fire(node, {"op": "rename", "item": holder["old"], "label": label})

    tv.on_change = changed
    tv.on_toggle = toggled
    tv.on_rename = renamed
    return tv


# ===================================================================== GridView

def _tile_preview(t):
    """BUI previews are an icon name or an RGBA color."""
    if not isinstance(t, dict):
        return "MATERIAL"
    if t.get("color") is not None:
        c = t["color"]
        if isinstance(c, str) and not c.startswith("#"):
            c = _css_named(c)
        return tuple(float(x) for x in rgba(c))
    ic = icon(t.get("icon"))
    if ic:
        return ic
    if t.get("image"):
        return _image_color(t["image"]) or "IMAGE_DATA"
    return "MATERIAL"


_NAMED = {"red": "#d33", "green": "#4a4", "blue": "#36c", "white": "#fff", "black": "#000",
          "gray": "#888", "grey": "#888", "yellow": "#ec3", "orange": "#e83", "purple": "#83c"}


def _css_named(c):
    return _NAMED.get(str(c).lower(), "#808080")


_IMG_COLORS: dict = {}


def _svg_color(text):
    """Middle stop of the most saturated gradient (material balls), else the
    most saturated fill; checkerboard/background greys lose."""
    import re

    def sat(c):
        return max(c[:3]) - min(c[:3])

    mids = []
    for g in re.findall(r"<(?:radial|linear)Gradient[^>]*>(.*?)</(?:radial|linear)Gradient>", text, re.S):
        stops = [rgba(h) for h in re.findall(r'stop-color="(#[0-9a-fA-F]{3,6})"', g)]
        if len(stops) >= 2:
            mids.append(stops[len(stops) // 2] if len(stops) > 2 else stops[0])
    fills = [rgba(h) for h in re.findall(r'fill="(#[0-9a-fA-F]{3,6})"', text)]
    cands = mids + fills
    if not cands:
        return None
    best = max(cands, key=sat)
    if sat(best) < 0.08 and mids:      # neutral material: the first (main) gradient tone
        best = mids[0]
    return tuple(float(x) for x in best)


def _image_color(src):
    """A representative color for an image asset. BUI grid tiles take a
    color or an icon, not an image (gap), so SVG tiles use their most
    saturated declared color and still read as distinct swatches."""
    if src in _IMG_COLORS:
        return _IMG_COLORS[src]
    col = None
    try:
        import re
        from .. import assets
        path = assets.resolve(str(src))
        if path is not None and path.lower().endswith(".svg"):
            text = open(path, encoding="utf-8", errors="ignore").read()
            col = _svg_color(text)
    except Exception:  # noqa: BLE001 - best effort
        col = None
    _IMG_COLORS[src] = col
    return col


def _tiles(node):
    raw = _plain_list(P.get(node, "tiles", []))
    labels = [item_label(t) for t in raw]
    return raw, labels, [(lab, _tile_preview(t)) for lab, t in zip(labels, raw)]


def _grid_sel_index(node, labels) -> int:
    s = P.get(node, "selected")
    if s is None:
        return -1
    s = str(s)
    return labels.index(s) if s in labels else -1


def _grid_apply(view, node, w, key, value):
    if key == "tiles":
        _, labels, items = _tiles(node)
        w.items = items
        w._a2ui_labels = labels
        w.set_value(max(-1, _grid_sel_index(node, labels)), notify=False)
        return True
    if key == "selected":
        i = _grid_sel_index(node, getattr(w, "_a2ui_labels", []))
        if i >= 0 and w.value != i:
            w.set_value(i, notify=False)
        return True
    if key == "tile":
        n = P.get_num(node, "tile", 4.0) or 4.0
        w.set("tile", float(n))
        return True
    return apply_common(w, key, value)


@adapter("GridView", live=("tiles", "selected", "tile"), apply=_grid_apply)
def grid_view(view, node):
    _, labels, items = _tiles(node)
    tile = float(P.get_num(node, "tile", 4.0) or 4.0)
    rows = P.get_num(node, "rows")
    if not rows:
        rows = 2.0 if len(items) > 4 else 1.0
    sel = _grid_sel_index(node, labels)
    w = C.GridView(items, max(0, sel), tile=tile, rows=float(rows), **common_kw(node))
    if sel < 0:
        w.set_value(-1, notify=False)
    w._a2ui_labels = labels

    def changed(i):
        labs = w._a2ui_labels
        i = int(i)
        if not (0 <= i < len(labs)):
            return
        P.write(node, "selected", labs[i])
        P.fire(node, {"op": "select", "label": labs[i], "index": i})

    def activated(i):
        labs = w._a2ui_labels
        i = int(i)
        if 0 <= i < len(labs):
            P.fire(node, {"op": "activate", "label": labs[i], "index": i})

    w.on_change = changed
    w.on_activate = activated
    return w
