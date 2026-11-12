# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Node editor group: Node and NodeEditor.

Both map onto Blender's node canvas in ``bui.components.nodes`` (C:
``kit_nodes.c``). Every catalog prop updates in place: a Node widget is never
rebuilt for a prop change (location, inputs, title, kind, width, collapsed),
and NodeEditor reconciles its Node children and links in place, so pans,
selections and drags survive data model updates.

Gaps in BUI's node canvas (degraded, see ``REPORTED_GAPS``):
- a Node's ``body`` widget cannot be drawn inside the node (graphnodes have
  no child widgets): NodeEditor shows bodies in a strip under the canvas,
  one titled box per node, still fully interactive and two-way;
- ``preview`` images are not drawn;
- vector / color input values have no field (BUI draws scalar fields only);
- per-input ``min``/``max`` are not enforced while dragging a field.
"""

from __future__ import annotations

import bui.components as C
import buipy

from .. import props as P
from .base import adapter, apply_common

UNIT = 20.0


def _editor_honors_height() -> bool:
    """BUI >= 25adf8e measures the nodeeditor at its "height" (units)."""
    try:
        e = C.NodeEditor()
        e.set("height", 30.0)
        return e.natural()[1] > 20 * buipy.kit_unit()
    except Exception:
        return False


_EDITOR_HONORS_HEIGHT = _editor_honors_height()  # px per UI unit (U.widget_unit at scale 1)

REPORTED_GAPS = ("Node.body drawn under the canvas", "Node.preview ignored",
                 "vector/color input values have no field")


# =========================================================================== Node

def _sockets(value, inputs: bool) -> list[tuple]:
    out = []
    for s in value or []:
        if isinstance(s, dict):
            name, typ, v = str(s.get("name", "")), str(s.get("type") or "float"), s.get("value")
        elif isinstance(s, (list, tuple)) and s:
            name = str(s[0])
            typ = str(s[1]) if len(s) > 1 else "float"
            v = s[2] if len(s) > 2 else None
        else:
            name, typ, v = str(s), "float", None
        if inputs:
            if isinstance(v, bool):
                v = int(v)
            if not isinstance(v, (int, float)):
                v = None  # BUI draws scalar fields only
            out.append((name, typ, v))
        else:
            out.append((name, typ))
    return out


def _xy(v) -> tuple:
    try:
        return (float(v[0]), float(v[1]))
    except (TypeError, ValueError, IndexError):
        return (0.0, 0.0)


def _kind_color(kind):
    from bui.components.nodes import NODE_CLASS_COLORS, _rgba
    return _rgba(NODE_CLASS_COLORS.get(str(kind or "converter"), "#4f4f4f"))


def _editor_of(w):
    p = w.parent
    return p if p is not None and hasattr(p, "_a2ui_relink") else None


def _node_apply(view, node, w, key, value):
    if key == "location":
        xy = _xy(value)
        if tuple(w.location) != xy:
            w.location = xy
        return True
    if key in ("inputs", "outputs"):
        ins, outs = _sockets(P.get(node, "inputs"), True), _sockets(P.get(node, "outputs"), False)
        if ins != w._inputs or outs != w._outputs:
            shape_changed = ([s[:2] for s in ins] != [s[:2] for s in w._inputs]
                             or outs != w._outputs)
            w._inputs, w._outputs = ins, outs
            w._push_sockets()
            ed = _editor_of(w)
            if shape_changed and ed is not None:
                ed._a2ui_relink()  # names may now resolve to other indices
        return True
    if key == "title":
        w.title = str(value or "")
        w.set("label", w.title)
        if getattr(w, "_a2ui_body_title", None) is not None:
            w._a2ui_body_title.set("text", w.title)
        return True
    if key == "kind":
        w.set("color", _kind_color(value))
        return True
    if key == "width":
        w.set("nwidth", float(P.get_num(node, "width", 7.0) or 7.0) * UNIT)
        return True
    if key == "collapsed":
        if w.collapsed != bool(value):
            w.collapsed = bool(value)
        return True
    if key == "key":
        w._a2ui_key = str(value or "")
        ed = _editor_of(w)
        if ed is not None:
            ed._a2ui_relink()
        return True
    if key == "preview":
        return True  # not drawn by BUI (gap)
    return apply_common(w, key, value)


def _body_box(n):
    """The node's titled body box (created once; hidden while it has no body)."""
    box = getattr(n, "_a2ui_body_box", None)
    if box is None:
        title = C.Label(n.title, bold=True)
        box = C.Box(title, n._a2ui_body_holder)
        n._a2ui_body_box = box
        n._a2ui_body_title = title
    return box


def _show_body(n, has_body: bool) -> None:
    box = _body_box(n)
    if bool(box.get("visible")) != has_body:
        box.set("visible", has_body)


def _body_holder(w):
    """Node ``container``: runs before the renderer reconciles ``body``."""
    _show_body(w, P.child(w._a2ui_cnode, "body") is not None)
    return w._a2ui_body_holder


@adapter("Node", live=("key", "title", "kind", "inputs", "outputs", "location", "width",
                       "collapsed", "preview"),
         children=("body",), apply=_node_apply, container=_body_holder)
def graph_node(view, node):
    title = P.get_str(node, "title", "Node")
    w = C.Node(title, inputs=_sockets(P.get(node, "inputs"), True),
               outputs=_sockets(P.get(node, "outputs"), False),
               location=_xy(P.get(node, "location", (0, 0))),
               width=float(P.get_num(node, "width", 7.0) or 7.0) * UNIT,
               kind=P.get_str(node, "kind", "converter") or "converter",
               collapsed=P.get_bool(node, "collapsed"))
    w._a2ui_key = P.get_str(node, "key")
    w._a2ui_cnode = node
    # Body: BUI graphnodes hold no widgets, so the body lives in a holder that
    # the NodeEditor shows under its canvas (reconciled in place by the renderer).
    w._a2ui_body_holder = C.Column()
    w._a2ui_body_title = None
    body = P.child(node, "body")
    if body is not None:
        w._a2ui_body_holder.add(view.build(body))

    def changed(n, what, value):
        if what == "location":
            P.write(node, "location", [round(float(value[0]), 1), round(float(value[1]), 1)])
        elif what == "collapsed":
            P.write(node, "collapsed", bool(value))
        elif what == "value":
            idx, v = value
            raw = P.get(node, "inputs")
            if isinstance(raw, list) and 0 <= idx < len(raw):
                new = [dict(x) if isinstance(x, dict) else x for x in raw]
                item = new[idx]
                if isinstance(item, dict):
                    item["value"] = v
                elif isinstance(item, list):
                    item = list(item) + [None] * (3 - len(item))
                    item[2] = v
                    new[idx] = item
                # keep our socket cache in step so the live update is a no-op
                w._inputs = [(s[0], s[1], v) if k == idx else s for k, s in enumerate(w._inputs)]
                P.write(node, "inputs", new)
    w.on_change = changed
    return w


# =========================================================================== NodeEditor

def _link_index(names, ref):
    if isinstance(ref, bool):
        return None
    if isinstance(ref, (int, float)):
        i = int(ref)
        return i if 0 <= i < len(names) else None
    if isinstance(ref, str):
        if ref in names:
            return names.index(ref)
        try:
            i = int(ref)
            return i if 0 <= i < len(names) else None
        except ValueError:
            return None
    return None


def _resolve_links(ed, value) -> list[tuple[int, int, int, int]]:
    nodes = ed._nodes
    keys = [getattr(n, "_a2ui_key", "") for n in nodes]
    out = []
    for l in value or []:
        if isinstance(l, dict):
            a, o, b, i = l.get("from"), l.get("out", 0), l.get("to"), l.get("in", 0)
        elif isinstance(l, (list, tuple)) and len(l) >= 4:
            a, o, b, i = l[:4]
        else:
            continue
        if a not in keys or b not in keys:
            continue
        na, nb = keys.index(a), keys.index(b)
        oi = _link_index([s[0] for s in nodes[na]._outputs], o)
        ii = _link_index([s[0] for s in nodes[nb]._inputs], i)
        if oi is None or ii is None:
            continue
        out.append((na, oi, nb, ii))
    return out


def _current_links(ed) -> list[tuple[int, int, int, int]]:
    out = []
    for s in ed.strs("items"):
        try:
            a, o, b, i = (int(v) for v in s.split())
        except ValueError:
            continue
        out.append((a, o, b, i))
    return out


def _links_out(ed, links, prev) -> list[dict]:
    """Index links -> catalog [{from, out, to, in}], keeping each existing link's
    form (socket names or indices); new links follow the majority form."""
    nodes = ed._nodes
    prev_form = {}
    named = 0
    for l, idx in zip(prev or [], _resolve_links_keep(ed, prev)):
        if idx is None or not isinstance(l, dict):
            continue
        uses_names = isinstance(l.get("out"), str) or isinstance(l.get("in"), str)
        named += 1 if uses_names else -1
        prev_form[idx] = uses_names
    out = []
    for a, o, b, i in links:
        if a >= len(nodes) or b >= len(nodes):
            continue
        na, nb = nodes[a], nodes[b]
        names = prev_form.get((a, o, b, i), named > 0)
        if names and o < len(na._outputs) and i < len(nb._inputs):
            out.append({"from": na._a2ui_key, "out": na._outputs[o][0],
                        "to": nb._a2ui_key, "in": nb._inputs[i][0]})
        else:
            out.append({"from": na._a2ui_key, "out": o, "to": nb._a2ui_key, "in": i})
    return out


def _resolve_links_keep(ed, value):
    """Like _resolve_links but one entry (or None) per input link."""
    out = []
    for l in value or []:
        r = _resolve_links(ed, [l])
        out.append(r[0] if r else None)
    return out


def _sync_nodes(view, ed, nodes) -> None:
    desired = [view.widget_for(n) or view.build(n) for n in nodes]
    current = list(ed.children)
    if [id(w) for w in current] != [id(w) for w in desired]:
        want = set(map(id, desired))
        for w in current:
            if id(w) not in want:
                buipy.KitNode.remove(ed, w)
        have = set(map(id, ed.children))
        for w in desired:  # z-order of existing nodes is the user's; append new ones
            if id(w) not in have:
                if w.parent is not None:
                    buipy.KitNode.remove(w.parent, w)
                buipy.KitNode.add(ed, w)
    ed._nodes = list(ed.children)


def _sync_bodies(ed) -> None:
    """Body strip under the canvas: one titled box per node, in node order,
    visible only for nodes with a body (BUI draws no widgets inside nodes)."""
    strip = ed._a2ui_strip
    want = []
    for n in ed._nodes:
        if not hasattr(n, "_a2ui_body_holder"):
            continue
        _show_body(n, P.child(n._a2ui_cnode, "body") is not None)
        want.append(_body_box(n))
    current = list(strip.children)
    if [id(b) for b in current] == [id(b) for b in want]:
        return
    for b in current:
        buipy.KitNode.remove(strip, b)
    for b in want:
        if b.parent is not None:
            buipy.KitNode.remove(b.parent, b)
        buipy.KitNode.add(strip, b)


def _editor_apply(view, node, w, key, value):
    ed = w._editor
    if key == "children":
        _sync_nodes(view, ed, P.children(node, "children"))
        _sync_bodies(ed)
        ed._a2ui_relink()
        return True
    if key == "links":
        ed._a2ui_relink()
        return True
    if key == "height":
        h = float(P.get_num(node, "height", 16.0) or 16.0)
        ed.set("height", h)
        if ed._a2ui_canvas is not ed:
            ed._a2ui_canvas.set("height", h)
        return True
    return apply_common(ed, key, value)


@adapter("NodeEditor", live=("children", "links", "height"), apply=_editor_apply)
def node_editor(view, node):
    # No fill: the canvas keeps its catalog height. A filled editor takes its
    # first arrange's size (e.g. a tall probe window) and frames the nodes
    # there once (view_all); a later shrink then leaves them off-canvas.
    ed = C.NodeEditor()
    ed.set("height", float(P.get_num(node, "height", 16.0) or 16.0))
    for d in ("description",):
        if P.get(node, d):
            ed.description = P.get_str(node, d)
    if P.get(node, "enabled") is False:
        ed.enabled = False
    ed._a2ui_node = node

    def relink():
        ed._nodes = list(ed.children)
        want = _resolve_links(ed, P.get(node, "links"))
        if want != _current_links(ed):
            ed.set("items", ["%d %d %d %d" % l for l in want])
    ed._a2ui_relink = relink

    def links_changed(_links):
        ed._nodes = list(ed.children)
        out = _links_out(ed, _current_links(ed), P.get(node, "links"))
        P.write(node, "links", out)
        P.fire(node, {"links": out})
    ed.on_links = links_changed

    def delete(doomed):
        # The data model owns the node list: report, don't delete locally.
        P.fire(node, {"links": P.get(node, "links") or [],
                      "delete": [getattr(n, "_a2ui_key", "") for n in doomed]})
    ed.on_delete = delete

    for child in P.children(node, "children"):
        ed.add_node(view.build(child))
    ed._nodes = list(ed.children)
    relink()

    canvas = ed
    if not _EDITOR_HONORS_HEIGHT:
        # Older BUI: the nodeeditor measured 14 units regardless of "height". A
        # ScrollView viewport arranges its child at max(viewport, content).
        h = float(P.get_num(node, "height", 16.0) or 16.0)
        canvas = C.ScrollView(ed, height=int(h * buipy.kit_unit()), fill=True)
    ed._a2ui_canvas = canvas
    ed._a2ui_strip = C.Row()
    w = C.Column(canvas, ed._a2ui_strip)  # strip: Node bodies (see module doc)
    _sync_bodies(ed)
    w._editor = ed
    if P.get(node, "weight") is not None:
        w.weight = float(P.get_num(node, "weight", 1.0) or 1.0)
    return w
