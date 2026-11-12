# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later
"""a2ui_bui: an A2UI renderer that draws with BUI (Blender's UI, native).

    from a2ui_bui import BuiRenderer
    r = BuiRenderer(on_action=print)
    r.process(open("showcases/shader-nodes.json"))   # A2UI v1.0 messages
    view = r.views["main"]                             # view.root_widget: a bui component
"""

from .renderer import BuiRenderer, SurfaceView, load_catalog  # noqa: F401

__version__ = "0.1.0"
