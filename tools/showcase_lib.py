# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tiny DSL for authoring A2UI v1.0 BUI showcases (used by build_showcases.py)."""

from __future__ import annotations

CATALOG = "https://a2ui-bui-demo.local/catalogs/bui/v1/catalog.json"
V = "1.0"


def P(path: str) -> dict:
  """Data binding."""
  return {"@path": path}


def ev(_name: str, **ctx) -> dict:
  """Event action; ctx values are literals or P(...) bindings."""
  return {"event": {"name": _name, "context": ctx}} if ctx else {"event": {"name": _name}}


def T(component_id: str, path: str) -> dict:
  """ChildList template."""
  return {"componentId": component_id, "path": path}


def M(label=None, sep=False, **kw) -> dict:
  """Menu item."""
  if sep:
    return {"separator": True}
  d = {"label": label}
  d.update({k: v for k, v in kw.items() if v is not None})
  return d


SEP = {"separator": True}


class Surface:
  """Collects components for one surface. b(Comp, **props) -> id."""

  def __init__(self, sid: str = "main"):
    self.sid = sid
    self.cs: list[dict] = []
    self.n = 0
    self.msgs: list[dict] = [{"version": V, "createSurface": {"surfaceId": sid, "catalogId": CATALOG, "sendDataModel": True}}]

  def __call__(self, comp: str, id: str | None = None, **props) -> str:
    if id is None:
      self.n += 1
      id = f"{comp[0].lower()}{comp[1:]}_{self.n}"
    self.cs.append({"id": id, "component": comp, **props})
    return id

  # common Blender patterns -------------------------------------------------
  def prop(self, label: str, field: str, factor: float = 0.4) -> str:
    """Blender use_property_split row: right-aligned label | field."""
    return self("Split", left=self("Label", text=label, align="right", color="muted"), right=field, factor=factor)

  def col(self, *kids, **kw) -> str:
    return self("Column", children=list(kids), **kw)

  def row(self, *kids, **kw) -> str:
    return self("Row", children=list(kids), **kw)

  def label(self, text, **kw) -> str:
    return self("Label", text=text, **kw)

  def panel(self, title, *kids, **kw) -> str:
    return self("Panel", title=title, children=list(kids), **kw)

  # messages ----------------------------------------------------------------
  def flush(self) -> None:
    """Emits an updateComponents with everything defined since the last flush."""
    if self.cs:
      self.msgs.append({"version": V, "updateComponents": {"surfaceId": self.sid, "components": self.cs}})
      self.cs = []

  def data(self, value, path: str | None = None) -> None:
    self.flush()
    m = {"surfaceId": self.sid, "value": value}
    if path is not None:
      m = {"surfaceId": self.sid, "path": path, "value": value}
    self.msgs.append({"version": V, "updateDataModel": m})

  def messages(self) -> list[dict]:
    self.flush()
    return self.msgs
