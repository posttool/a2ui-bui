# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Editors group: ColorRamp, CurveMapping, NormalBall, Histogram.

All four map onto Blender's data editors in ``bui.components.editors`` (drawn
and driven in C, ``kit_color.c``). Two-way props write the data model on every
edit and update in place when the model changes, so drags are never
interrupted by a rebuild.
"""

from __future__ import annotations

import bui.components as C
from bui.components.editors import INTERPOLATIONS

from .. import props as P
from .base import adapter, apply_common, common_kw, rgba


def _r(x: float) -> float:
    return round(float(x), 4)


# =========================================================================== ColorRamp

def _interp(name) -> str:
    """Catalog interpolation -> BUI's list (BUI has no Cardinal: closest is B-Spline)."""
    n = str(name or "Linear")
    if n in INTERPOLATIONS:
        return n
    return {"Cardinal": "B-Spline", "linear": "Linear", "ease": "Ease",
            "constant": "Constant", "b-spline": "B-Spline"}.get(n, "Linear")


def _stops_in(value) -> list[tuple[float, tuple]]:
    """Catalog stops ([{pos, color}] or [[pos, color]]) -> [(pos, rgba)]."""
    out = []
    for s in value or []:
        if isinstance(s, dict):
            pos, col = s.get("pos", s.get("position", 0.0)), s.get("color", (0, 0, 0, 1))
        elif isinstance(s, (list, tuple)) and len(s) >= 2:
            pos, col = s[0], s[1]
        else:
            continue
        try:
            out.append((min(1.0, max(0.0, float(pos))), tuple(rgba(col, (0, 0, 0, 1)))))
        except (TypeError, ValueError):
            continue
    if not out:
        out = [(0.0, (0, 0, 0, 1.0)), (1.0, (1, 1, 1, 1.0))]
    return out


def _stops_out(stops, like) -> list:
    """BUI ColorStops -> the catalog's own shape (pair lists stay pair lists)."""
    pairs = bool(like) and isinstance(like, list) and isinstance(like[0], (list, tuple))
    out = []
    for s in stops:
        col = [_r(c) for c in s.color]
        out.append([_r(s.pos), col] if pairs else {"pos": _r(s.pos), "color": col})
    return out


def _same_stops(a, b) -> bool:
    if len(a) != len(b):
        return False
    for (pa, ca), (pb, cb) in zip(sorted(a, key=lambda s: s[0]), sorted(b, key=lambda s: s[0])):
        if abs(pa - pb) > 1e-3 or any(abs(x - y) > 1e-3 for x, y in zip(ca, cb)):
            return False
    return True


def _ramp_apply(view, node, w, key, value):
    if key == "stops":
        want = _stops_in(value)
        have = [(float(p), tuple(c)) for p, c in w.band.ramp()]
        if not _same_stops(want, have):
            active = int(w.band.get("active"))
            w.band.set_ramp(want)
            if active < len(want):
                w.band.set("active", active)
            w._sync()
        return True
    if key == "interpolation":
        name = _interp(value)
        if w.interpolation != name:
            w.band.set("interpolation", INTERPOLATIONS.index(name))
            w.interp.set_value(name, notify=False)
        return True
    return apply_common(w, key, value)


@adapter("ColorRamp", live=("stops", "interpolation"), apply=_ramp_apply)
def color_ramp(view, node):
    w = C.ColorRamp(_stops_in(P.get(node, "stops")),
                    interpolation=_interp(P.get(node, "interpolation")), **common_kw(node))

    def changed(stops):
        out = _stops_out(stops, P.get(node, "stops"))
        P.write(node, "stops", out)
        P.fire(node, {"stops": out, "interpolation": w.interpolation})
    w.on_change = changed
    return w


# =========================================================================== CurveMapping

def _curves_in(value) -> list[dict]:
    """[{name, color?, points}] (or a bare point list) -> normalized dicts."""
    if isinstance(value, list) and value and isinstance(value[0], (list, tuple)):
        value = [{"name": "C", "points": value}]  # a single bare point list
    out = []
    for i, c in enumerate(value or []):
        if not isinstance(c, dict):
            continue
        pts = []
        for p in c.get("points") or []:
            try:
                pts.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                continue
        out.append({**c, "name": str(c.get("name") or "CRGB"[i % 4]),
                    "points": pts or [(0.0, 0.0), (1.0, 1.0)]})
    return out or [{"name": "C", "points": [(0.0, 0.0), (1.0, 1.0)]}]


def _same_points(a, b) -> bool:
    return len(a) == len(b) and all(abs(x0 - x1) < 1e-4 and abs(y0 - y1) < 1e-4
                                    for (x0, y0), (x1, y1) in zip(a, b))


def _curve_index(node, n) -> int:
    i = P.get_num(node, "current", 0) or 0
    return min(max(int(i), 0), n - 1)


def _curves_apply(view, node, w, key, value):
    if key == "curves":
        curves = _curves_in(value)
        if [c["name"] for c in curves] != w.channels:
            return False  # channel set changed: rebuild
        for ch, c in enumerate(curves):
            if not _same_points(c["points"], w.graph.curve(ch)):
                w.graph.set_curve(ch, list(c["points"]))
        return True
    if key == "current":
        i = _curve_index(node, len(w.channels))
        if int(w.graph.get("channel")) != i:
            w.graph.set("channel", i)
            if w._tabs is not None:
                w._tabs.set_value(w.channels[i], notify=False)
        return True
    return apply_common(w, key, value)


@adapter("CurveMapping", live=("curves", "current"), apply=_curves_apply)
def curve_mapping(view, node):
    curves = _curves_in(P.get(node, "curves"))
    names = [c["name"] for c in curves]
    h = P.get_num(node, "height", 8.0) or 8.0
    w = C.CurveMapping(curves[0]["points"], channels=names if len(names) > 1 else (),
                       height=float(h), **common_kw(node))
    w.channels = names  # single curve keeps its own name
    for ch, c in enumerate(curves):
        w.graph.set_curve(ch, list(c["points"]))
    tools = w.children[0]
    first = tools.children[0] if tools.children else None
    w._tabs = first if isinstance(first, C.EnumRow) else None
    i = _curve_index(node, len(names))
    if i:
        w.graph.set("channel", i)
        if w._tabs is not None:
            w._tabs.set_value(names[i], notify=False)

    def write_curves(ch_name, points):
        raw = P.get(node, "curves")
        cur = _curves_in(raw)
        ch = names.index(ch_name) if ch_name in names else int(w.graph.get("channel"))
        pts = [[_r(x), _r(y)] for x, y in points]
        out = []
        for k, c in enumerate(cur):
            d = dict(c)
            d["points"] = pts if k == ch else [[_r(x), _r(y)] for x, y in c["points"]]
            out.append(d)
        if isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
            out = out[0]["points"]  # keep a bare point list bare
        P.write(node, "curves", out)
        P.fire(node, {"curves": out, "current": ch})

    def tab(name):
        if name in names:
            ch = names.index(name)
            w.graph.set("channel", ch)
            P.write(node, "current", ch)
    if w._tabs is not None:
        w._tabs.on_change = tab
    w.on_change = write_curves
    return w


# =========================================================================== NormalBall

def _vec3(v) -> tuple:
    try:
        x, y, z = (float(c) for c in list(v)[:3])
        return (x, y, z)
    except (TypeError, ValueError):
        return (0.0, 0.0, 1.0)


def _ball_apply(view, node, w, key, value):
    ball = w._ball
    if key == "value":
        want = _vec3(value)
        n = sum(c * c for c in want) ** 0.5 or 1.0
        have = ball.value
        if any(abs(a - b / n) > 1e-3 for a, b in zip(have, want)):
            ball.set_value(want, notify=False)
        return True
    if key == "label":
        if w._label is not None:
            w._label.set("text", str(value or ""))
            return True
        return not value
    return apply_common(ball, key, value)


@adapter("NormalBall", live=("value", "label"), apply=_ball_apply)
def normal_ball(view, node):
    size = P.get_num(node, "size", 4.0) or 4.0
    ball = C.NormalBall(value=_vec3(P.get(node, "value", (0, 0, 1))), size=float(size),
                        **common_kw(node))

    def changed(v):
        v = [_r(c) for c in v]
        P.write(node, "value", v)
        P.fire(node, {"value": v})
    ball.on_change = changed
    label = P.get_str(node, "label")
    if label:  # BUI's NormalBall draws no label of its own
        lab = C.Label(label)
        w = C.Column(lab, ball)
        w._label = lab
    else:
        w = ball
        w._label = None
    w._ball = ball
    return w


# =========================================================================== Histogram

def _hist_bins(value, mode):
    """-> (bins, channels) normalized to 0..1 for BUI's histogram."""
    if isinstance(value, dict):
        r, g, b = (list(value.get(k) or []) for k in ("r", "g", "b"))
        luma = list(value.get("luma") or value.get("l") or value.get("y") or [])
        if mode == "rgb" and (r or g or b):
            n = max(len(r), len(g), len(b))
            pad = lambda a: [float(x or 0) for x in a] + [0.0] * (n - len(a))  # noqa: E731
            bins = list(zip(pad(r), pad(g), pad(b)))
        elif luma:
            bins = [float(x or 0) for x in luma]
        else:  # luma from rgb
            n = max(len(r), len(g), len(b))
            pad = lambda a: [float(x or 0) for x in a] + [0.0] * (n - len(a))  # noqa: E731
            bins = [0.2126 * x + 0.7152 * y + 0.0722 * z for x, y, z in zip(pad(r), pad(g), pad(b))]
    else:
        bins = []
        for x in value or []:
            if isinstance(x, (list, tuple)):
                bins.append(tuple(float(c or 0) for c in list(x)[:3]))
            else:
                try:
                    bins.append(float(x or 0))
                except (TypeError, ValueError):
                    bins.append(0.0)
        if mode != "rgb":
            bins = [sum(b) / len(b) if isinstance(b, tuple) and b else b for b in bins]
    flat = [c for b in bins for c in (b if isinstance(b, tuple) else (b,))]
    top = max(flat, default=0.0)
    lo = min(flat, default=0.0)
    if top > 1.0 or lo < 0.0:  # bars of arbitrary units: scale into 0..1
        span = top if lo >= 0 else (top - lo) or 1.0
        off = 0.0 if lo >= 0 else lo
        bins = [tuple((c - off) / span for c in b) if isinstance(b, tuple) else (b - off) / span
                for b in bins]
    if mode == "bars" and bins and not isinstance(bins[0], tuple):
        bins = _bars(bins)
    return bins


def _bars(values, per=10, gap=2):
    """Step-expand values (with a gap of empty bins between bars) so BUI's
    filled histogram reads as a discrete bar chart."""
    out = []
    for v in values:
        out.extend([0.0] * (gap // 2) + [v] * (per - gap) + [0.0] * (gap - gap // 2))
    return out


def _hist_set(h, node):
    bins = _hist_bins(P.get(node, "bins"), P.get_str(node, "mode", "luma") or "luma")
    h.set_bins(bins)


def _hist_apply(view, node, w, key, value):
    if key == "bins":
        _hist_set(w._hist, node)
        return True
    return apply_common(w, key, value)


@adapter("Histogram", live=("bins",), apply=_hist_apply)
def histogram(view, node):
    h = C.Histogram((), height=float(P.get_num(node, "height", 5.0) or 5.0), **common_kw(node))
    _hist_set(h, node)
    labels = P.get(node, "labels")
    if isinstance(labels, list) and any(str(x) for x in labels):
        # BUI's histogram has no axis: a row of small centered labels under it.
        row = C.Row(*[C.Label(str(x), align="center", weight=1.0) for x in labels], spacing=0)
        w = C.Column(h, row)
    else:
        w = h
    w._hist = h
    return w

