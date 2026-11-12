# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading resolved A2UI props off an ``a2ui_core`` ComponentNode.

``NodeResolver`` hands each node a ``props`` dict whose values are one of:

* a plain literal (static enum strings, numbers),
* ``ResolvedBinding`` (read-only snapshot: ``.value``),
* ``WritableBinding`` (two-way, backed by a data model path: ``.value``, ``.set(v)``),
* a closure for ``Action`` props (``closure(metadata=None)``),
* a child ``ComponentNode`` or a list of them (structural props).

Adapters never touch these types directly; they go through the helpers here.
"""

from __future__ import annotations

from typing import Any, Iterable

from a2ui.core.resolution.component_node import ComponentNode
from a2ui.core.resolution.resolved_binding import ResolvedBinding, WritableBinding


def is_node(v: Any) -> bool:
    return isinstance(v, ComponentNode)


def unwrap(v: Any) -> Any:
    """The plain value of a resolved prop (bindings unwrapped, recursively)."""
    if isinstance(v, ResolvedBinding):
        return unwrap(v.value)
    if isinstance(v, list):
        return [unwrap(x) for x in v]
    if isinstance(v, dict):
        return {k: unwrap(x) for k, x in v.items()}
    return v


def get(node: ComponentNode, key: str, default: Any = None) -> Any:
    v = unwrap(node.props.get(key))
    return default if v is None else v


def get_str(node: ComponentNode, key: str, default: str = "") -> str:
    v = get(node, key)
    return default if v is None else str(v)


def get_num(node: ComponentNode, key: str, default: float | None = None) -> float | None:
    v = get(node, key)
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_bool(node: ComponentNode, key: str, default: bool = False) -> bool:
    v = get(node, key)
    return default if v is None else bool(v)


def write(node: ComponentNode, key: str, value: Any) -> bool:
    """Two-way write-back: set the data model path behind ``key``. Reads the
    node's *current* binding (bindings are re-emitted on every change)."""
    b = node.props.get(key)
    if isinstance(b, WritableBinding):
        b.set(value)
        return True
    return False


def child(node: ComponentNode, key: str) -> ComponentNode | None:
    v = node.props.get(key)
    return v if is_node(v) else None


def children(node: ComponentNode, key: str = "children") -> list[ComponentNode]:
    v = node.props.get(key)
    if is_node(v):
        return [v]
    if isinstance(v, list):
        return [c for c in v if is_node(c)]
    return []


def structural_keys(node: ComponentNode) -> set[str]:
    out = set()
    for k, v in node.props.items():
        if is_node(v) or (isinstance(v, list) and any(is_node(c) for c in v)):
            out.add(k)
    return out


def structure(node: ComponentNode, skip: Iterable[str] = ()) -> tuple:
    """Identity signature of the child nodes in every structural prop not in
    ``skip`` (single children, lists, and nodes nested in objects such as
    ``Tabs.tabs[].child``). A change means the widget must be rebuilt."""
    skip = set(skip)

    def ids(v):
        if is_node(v):
            return (v.id, v.state)
        if isinstance(v, list):
            return tuple(ids(x) for x in v if is_node(x) or isinstance(x, (list, dict)))
        if isinstance(v, dict):
            return tuple((k, ids(x)) for k, x in v.items() if is_node(x) or isinstance(x, (list, dict)))
        return ()
    return tuple((k, ids(v)) for k, v in sorted(node.props.items()) if k not in skip and ids(v))


def snapshot(node: ComponentNode, skip: Iterable[str] = ()) -> dict[str, Any]:
    """Plain, comparable view of every non-structural, non-action prop."""
    skip = set(skip)
    out = {}
    for k, v in node.props.items():
        if k in skip or callable(v) or is_node(v):
            continue
        if isinstance(v, list) and any(is_node(c) for c in v):
            continue
        out[k] = unwrap(v)
    return out


def fire(node: ComponentNode, extra: dict | None = None, prop: str = "action") -> None:
    """Dispatch the node's Action prop, merging ``extra`` into an event's
    context (``{"value": ...}``, ``{"index": ...}``), like the web renderer.

    Function-call actions run locally through the bound closure."""
    if not get_bool(node, "enabled", True):
        return
    ctx = node.context
    if ctx is None:
        return
    raw = ctx.component_model.properties.get(prop) if hasattr(ctx.component_model, "properties") else None
    if raw is None:
        closure = node.props.get(prop)
        if callable(closure):
            closure()
        return
    if isinstance(raw, dict) and isinstance(raw.get("event"), dict):
        resolved = ctx.data_context.resolve_action(raw)
        if isinstance(resolved, dict) and isinstance(resolved.get("event"), dict) and extra:
            ev = dict(resolved["event"])
            ev["context"] = {**(ev.get("context") or {}), **_plain(extra)}
            resolved = {**resolved, "event": ev}
        ctx.dispatch_action(resolved)
        return
    closure = node.props.get(prop)
    if callable(closure):
        closure()


def _plain(d: dict) -> dict:
    """JSON-safe copy (tuples -> lists)."""
    def conv(v):
        if isinstance(v, tuple):
            return [conv(x) for x in v]
        if isinstance(v, list):
            return [conv(x) for x in v]
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        return v
    return conv(d)
