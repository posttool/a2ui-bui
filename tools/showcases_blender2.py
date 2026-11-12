# Copyright 2026 posttool
# SPDX-License-Identifier: Apache-2.0

"""Blender-native showcases, part 2."""

from showcase_lib import P, SEP, Surface, T, ev, M


def outliner():
  b = Surface()

  def ob(label, icon, id, children=None, hide=False, render=True, select=True, expanded=True):
    d = {"label": label, "icon": icon, "id": id,
         "toggles": {"select": select, "hide": not hide, "viewport": True, "render": render}}
    if children:
      d["children"] = children
      d["expanded"] = expanded
    return d

  scene = [ob("Scene Collection", "OUTLINER_COLLECTION", "scene", [
      ob("Environment", "OUTLINER_COLLECTION", "env", [
          ob("Ground", "OUTLINER_OB_MESH", "ground", [ob("Plane", "OUTLINER_DATA_MESH", "ground_data")], expanded=False),
          ob("Sky Dome", "OUTLINER_OB_MESH", "sky", render=True),
          ob("Fog Volume", "OUTLINER_OB_VOLUME", "fog", hide=True, render=False),
      ]),
      ob("Characters", "OUTLINER_COLLECTION", "chars", [
          ob("Rig_Hero", "OUTLINER_OB_ARMATURE", "rig", [ob("Hero_Body", "OUTLINER_OB_MESH", "body"),
                                                         ob("Hero_Hair", "OUTLINER_OB_CURVE", "hair")]),
          ob("Rig_Sidekick", "OUTLINER_OB_ARMATURE", "rig2", expanded=False, hide=True),
      ]),
      ob("Lighting", "OUTLINER_COLLECTION", "lights", [
          ob("Key Light", "OUTLINER_OB_LIGHT", "key"), ob("Fill Light", "OUTLINER_OB_LIGHT", "fill"),
          ob("Rim Light", "OUTLINER_OB_LIGHT", "rim", render=False),
      ]),
      ob("Camera", "OUTLINER_OB_CAMERA", "cam"),
  ])]
  lighting = [ob("Scene Collection", "OUTLINER_COLLECTION", "scene_l", [
      ob("Lighting", "OUTLINER_COLLECTION", "lights_l", [
          ob("Key Light", "OUTLINER_OB_LIGHT", "key_l"), ob("Fill Light", "OUTLINER_OB_LIGHT", "fill_l"),
          ob("Rim Light", "OUTLINER_OB_LIGHT", "rim_l"), ob("Light Probe", "OUTLINER_OB_LIGHTPROBE", "probe_l")]),
      ob("Environment", "OUTLINER_COLLECTION", "env_l", expanded=False, hide=True)])]
  tree_main = b("TreeView", items=P("/tree/main"), columns=["select", "hide", "viewport", "render"],
                selected=P("/tree/selected"), rows=14, action=ev("outliner", selected=P("/tree/selected")))
  tree_light = b("TreeView", items=P("/tree/lighting"), columns=["hide", "render"], rows=14,
                 action=ev("outliner", layer="Lighting"))
  comp = b.col(b.label("Compositing layer uses all collections, with holdout on Characters.", color="muted",
                       icon="INFO"), padding=0.5)
  tabs = b("Tabs", current=0, tabs=[{"title": "ViewLayer", "icon": "RENDERLAYERS", "child": tree_main},
                                     {"title": "Lighting", "icon": "LIGHT", "child": tree_light},
                                     {"title": "Compositing", "icon": "NODE_EDITOR", "child": comp}])
  filt = b("Popover", icon="FILTER", children=[
      b.label("Restriction Toggles", bold=True),
      b.row(b("Toggle", value=True, icon="RESTRICT_SELECT_OFF"), b("Toggle", value=True, icon="HIDE_OFF"),
            b("Toggle", value=False, icon="RESTRICT_VIEW_OFF"), b("Toggle", value=True, icon="RESTRICT_RENDER_OFF"),
            align=True),
      b("Separator", line=True),
      b.label("Filter", bold=True),
      b("Checkbox", label="All View Layers", value=False),
      b("Checkbox", label="Collections", value=True),
      b("Checkbox", label="Objects", value=True),
      b("Checkbox", label="Object Children", value=True),
      b("Dropdown", label="Object", value="All", items=["All", "Visible", "Selected", "Active"]),
  ])
  header = [b("Dropdown", value="View Layer", iconOnly=True,
              items=[{"label": "Scenes", "icon": "SCENE_DATA"}, {"label": "View Layer", "icon": "RENDERLAYERS"},
                     {"label": "Blender File", "icon": "FILE_BLEND"}, {"label": "Orphan Data", "icon": "ORPHAN_DATA"}]),
            b("SearchField", value=P("/filter"), placeholder="Search", action=ev("outliner_filter", text=P("/filter")),
              weight=1),
            filt,
            b("IconButton", icon="COLLECTION_NEW", description="Add a new collection inside selected collection")]
  b("Area", id="root", editor="Outliner", icon="OUTLINER", header=header, child=tabs)
  b.data({"filter": "", "tree": {"main": scene, "lighting": lighting, "selected": "body"}})
  return {"name": "Outliner", "window": "Outliner", "width": 560,
          "description": "Outliner-style TreeView with select / hide / viewport / render toggle columns, a search "
                         "filter and filter popover in the editor header, and Tabs switching between view layers.",
          "messages": b.messages()}


def color_grading():
  b = Surface()

  def curve(name, color, pts):
    return {"name": name, "color": color, "points": pts}

  curves = [curve("C", "#dddddd", [[0, 0], [0.25, 0.2], [0.75, 0.82], [1, 1]]),
            curve("R", "#e05252", [[0, 0.02], [0.5, 0.55], [1, 1]]),
            curve("G", "#5bb85b", [[0, 0], [0.5, 0.5], [1, 0.97]]),
            curve("B", "#5285e0", [[0, 0.06], [0.45, 0.42], [1, 0.92]])]
  import math
  def bell(c, s, n=64, amp=1.0):
    return [round(amp * math.exp(-((i / n - c) ** 2) / (2 * s * s)) + 0.05 * math.sin(i * 1.7) ** 2, 3) for i in range(n)]
  bins = {"r": bell(0.62, 0.16), "g": bell(0.45, 0.18, amp=0.9), "b": bell(0.3, 0.14, amp=0.8), "luma": bell(0.48, 0.2)}
  img = b("Image", src="assets/photo.png", height=11, fit="contain", alt="Graded frame")
  view = b.panel("Color Management",
                 b.prop("Display Device", b("Dropdown", value="sRGB", items=["sRGB", "Display P3", "Rec.1886", "Rec.2020"])),
                 b.prop("View", b("Dropdown", value=P("/cm/view"), items=["Standard", "Khronos PBR Neutral", "AgX", "Filmic",
                                                                           "Filmic Log", "False Color", "Raw"])),
                 b.prop("Look", b("Dropdown", value=P("/cm/look"),
                                  items=["None", "Punchy", "Greyscale", "Very High Contrast", "High Contrast",
                                         "Medium High Contrast", "Base Contrast", "Medium Low Contrast", "Low Contrast",
                                         "Very Low Contrast"])),
                 b.prop("Exposure", b("NumberField", value=P("/cm/exposure"), min=-32, max=32, precision=3, step=0.1,
                                      action=ev("grade", exposure=P("/cm/exposure")))),
                 b.prop("Gamma", b("NumberField", value=P("/cm/gamma"), min=0, max=5, precision=3, step=0.05)),
                 icon="COLOR")
  curves_p = b.panel("Curves", b("CurveMapping", curves=P("/cm/curves"), current=P("/cm/channel"), height=9,
                                 action=ev("grade_curves", curves=P("/cm/curves"))),
                     b.row(b.prop("Black Level", b("ColorSwatch", value=[0, 0, 0, 1]), factor=0.5),
                           b.prop("White Level", b("ColorSwatch", value=[1, 1, 1, 1]), factor=0.5)),
                     header=[b("Checkbox", value=P("/cm/use_curves"))])
  ramp_p = b.panel("Color Ramp",
                   b("ColorRamp", stops=P("/cm/ramp"), interpolation="Ease", action=ev("grade_ramp", stops=P("/cm/ramp"))),
                   b.prop("Factor", b("NumberSlider", value=0.35, min=0, max=1, precision=3)), sub=False, collapsed=False)
  scopes = b.panel("Scopes",
                   b("EnumRow", value="RGB", items=["Luma", "RGB", "R", "G", "B"]),
                   b("Histogram", bins=P("/scopes/rgb"), mode="rgb", height=5),
                   b.prop("Accuracy", b("NumberSlider", value=50, min=0, max=100, suffix="%", precision=0)))
  left = b.col(img, scopes, spacing="small", weight=3)
  right = b.col(view, curves_p, ramp_p, spacing="small", weight=2)
  b.row(left, right, id="root", spacing="large")
  b.data({"cm": {"view": "AgX", "look": "Medium High Contrast", "exposure": 0.25, "gamma": 1.0, "use_curves": True,
                 "channel": 0, "curves": curves,
                 "ramp": [{"pos": 0.0, "color": [0.05, 0.03, 0.15, 1]}, {"pos": 0.45, "color": [0.75, 0.3, 0.35, 1]},
                          {"pos": 0.8, "color": [1, 0.72, 0.4, 1]}, {"pos": 1.0, "color": [1, 0.96, 0.85, 1]}]},
          "scopes": {"rgb": bins}})
  return {"name": "Color grading", "window": "Image Editor — Color Management", "width": 1100,
          "description": "Grading view: an Image preview with an RGB Histogram scope, Color Management dropdowns, RGB "
                         "CurveMapping with C/R/G/B channels and a gradient-map ColorRamp, all bound to /cm.",
          "messages": b.messages()}


def light_setup():
  b = Surface()
  ltype = b("EnumRow", value=P("/light/type"), items=["Point", "Sun", "Spot", "Area"],
            icons=["LIGHT_POINT", "LIGHT_SUN", "LIGHT_SPOT", "LIGHT_AREA"], action=ev("light_type", type=P("/light/type")))
  props = b.panel(
      "Light",
      ltype,
      b("Separator", factor=0.3),
      b.prop("Color", b("ColorSwatch", value=P("/light/color"), picker="circle")),
      b.prop("Strength", b("NumberField", value=P("/light/strength"), min=0, precision=2, suffix="", step=0.1,
                           description="Sunlight strength in watts per square meter (W/m²)")),
      b.prop("Angle", b("NumberField", value=P("/light/angle"), min=0, max=180, precision=2, suffix="°")),
      b.prop("", b("Checkbox", label="Cast Shadow", value=P("/light/shadow"))),
      b.prop("", b("Checkbox", label="Multiple Importance", value=True)),
      b.prop("Max Bounces", b("NumberField", value=1024, integer=True)),
      icon="LIGHT_DATA")
  direction = b.panel(
      "Sun Direction",
      b.row(b("NormalBall", value=P("/light/direction"), size=5, label="Direction",
              action=ev("light_direction", direction=P("/light/direction"))),
            b.col(b("VectorField", value=P("/light/direction"), precision=3, min=-1, max=1, axes="XYZ"),
                  b.prop("Elevation", b("NumberSlider", value=P("/light/elevation"), min=0, max=90, suffix="°", precision=1)),
                  b.prop("Azimuth", b("NumberField", value=P("/light/azimuth"), min=0, max=360, suffix="°", precision=1)),
                  weight=1, spacing="small")),
      description="Drag the ball to aim the sun")
  point = b.panel("Point Light",
                  b.prop("Power", b("NumberField", value=P("/point/power"), suffix=" W", min=0, precision=1, step=10,
                                    description="Light energy emitted over the entire area of the light in all directions")),
                  b.prop("Radius", b("NumberField", value=0.1, suffix=" m", precision=3)),
                  b.prop("Color", b("ColorSwatch", value=P("/point/color"), picker="square")),
                  b.panel("Custom Distance", b.prop("Distance", b("NumberField", value=40, suffix=" m")), sub=True,
                          header=[b("Checkbox", value=False)], collapsed=True),
                  collapsed=True, icon="LIGHT_POINT")
  world = b.panel("World Lighting",
                  b.prop("Sky Texture", b("Dropdown", value="Nishita", items=["Preetham", "Hosek / Wilkie", "Nishita"])),
                  b.prop("Air", b("NumberSlider", value=1.0, min=0, max=10, precision=3)),
                  b.prop("Dust", b("NumberSlider", value=1.0, min=0, max=10, precision=3)),
                  b.prop("Ozone", b("NumberSlider", value=1.0, min=0, max=10, precision=3)), collapsed=True, icon="WORLD")
  b.col(b.row(b("IDSelector", items=["Sun", "Key Light", "Fill Light"], value="Sun", icon="LIGHT_DATA", users=1, weight=1),
              b("Button", text="Use Nodes", icon="NODETREE", action=ev("light_use_nodes"))),
        props, direction, point, world, id="root", spacing="small")
  b.data({"light": {"type": "Sun", "color": [1, 0.93, 0.82, 1], "strength": 4.5, "angle": 0.53, "shadow": True,
                    "direction": [0.42, 0.36, 0.83], "elevation": 56.1, "azimuth": 49.4},
          "point": {"power": 1000, "color": "#ffd2a1"}})
  return {"name": "Light setup", "window": "Properties — Light", "width": 580,
          "description": "Light data properties: light type EnumRow with icons, color wheel and square pickers, a NormalBall "
                         "that aims the sun (two-way bound to the same vector as the XYZ fields), and power in watts.",
          "messages": b.messages()}


KEYMAP = {
    "window": [
        {"name": "New", "op": "wm.read_homefile", "key": "Ctrl N", "active": True},
        {"name": "Open", "op": "wm.open_mainfile", "key": "Ctrl O", "active": True},
        {"name": "Save", "op": "wm.save_mainfile", "key": "Ctrl S", "active": True},
        {"name": "Save As", "op": "wm.save_as_mainfile", "key": "Shift Ctrl S", "active": True},
        {"name": "Menu Search", "op": "wm.search_menu", "key": "F3", "active": True},
        {"name": "Quit Blender", "op": "wm.quit_blender", "key": "Ctrl Q", "active": True},
        {"name": "Toggle Window Fullscreen", "op": "wm.window_fullscreen_toggle", "key": "Ctrl Alt F", "active": False},
    ],
    "screen": [
        {"name": "Render", "op": "render.render", "key": "F12", "active": True},
        {"name": "Render Animation", "op": "render.render", "key": "Ctrl F12", "active": True},
        {"name": "View Render", "op": "render.view_show", "key": "F11", "active": True},
        {"name": "Repeat Last", "op": "screen.repeat_last", "key": "Shift R", "active": True},
        {"name": "Toggle Maximize Area", "op": "screen.screen_full_area", "key": "Ctrl Space", "active": True},
    ],
    "view3d": [
        {"name": "Move", "op": "transform.translate", "key": "G", "active": True},
        {"name": "Rotate", "op": "transform.rotate", "key": "R", "active": True},
        {"name": "Resize", "op": "transform.resize", "key": "S", "active": True},
        {"name": "Frame Selected", "op": "view3d.view_selected", "key": "Numpad .", "active": True},
        {"name": "Toggle X-Ray", "op": "view3d.toggle_xray", "key": "Alt Z", "active": True},
        {"name": "Local View", "op": "view3d.localview", "key": "Numpad /", "active": False},
    ],
}


def keymap_prefs():
  b = Surface()
  row = b("Box", id="km_row", children=[
      b.row(b("Checkbox", value=P("active"), description="Enable or disable this keymap item"),
            b.label(P("name"), weight=3),
            b("HotkeyField", value=P("key"), weight=2, action=ev("keymap_set", op=P("op"), key=P("key")),
              description="Click, then press a key combination"),
            b("IconButton", icon="X", action=ev("keymap_remove", op=P("op")), description="Remove key map item")),
      b.row(b.label(P("op"), color="muted", size="small")),
  ], align=True)
  def page(path):
    return b("Column", children=T(row, path), spacing="small")
  tabs = b("Tabs", current=P("/ui/km_tab"), tabs=[{"title": "Window", "child": page("/keymap/window")},
                                                   {"title": "Screen", "child": page("/keymap/screen")},
                                                   {"title": "3D View", "child": page("/keymap/view3d")}])
  keymap_tab = b.col(
      b.row(b("Dropdown", value="Blender", items=["Blender", "Blender 2.7x", "Industry Compatible"], weight=1),
            b("IconButton", icon="ADD"), b("IconButton", icon="REMOVE"),
            b("Button", text="Import...", icon="IMPORT"), b("Button", text="Export...", icon="EXPORT")),
      b.panel("Preferences",
              b.prop("Select with", b("EnumRow", value="Left", items=["Left", "Right"], icons=["MOUSE_LMB", "MOUSE_LMB"])),
              b.prop("Spacebar Action", b("EnumRow", value="Play", items=["Play", "Tools", "Search"])),
              b.prop("Activate Gizmo", b("EnumRow", value="Press", items=["Press", "Drag"])),
              b.prop("", b("Checkbox", label="Alt Click Tool Prompt", value=False)),
              sub=True, collapsed=True),
      b.row(b("EnumRow", value="Name", items=["Name", "Key-Binding"]),
            b("SearchField", value=P("/ui/search"), placeholder="Search keymap", weight=1,
              action=ev("keymap_search", text=P("/ui/search")))),
      tabs,
      b.row(b("Spacer"), b("Button", text="Restore", icon="LOOP_BACK", action=ev("keymap_restore"))),
      spacing="small", padding=0.5)
  interface = b.col(
      b.panel("Display", b.prop("Resolution Scale", b("NumberField", value=P("/prefs/scale"), min=0.25, max=4, precision=2, step=0.05)),
              b.prop("Line Width", b("Dropdown", value="Auto", items=["Thin", "Auto", "Thick"])),
              b.prop("", b("Checkbox", label="Splash Screen", value=True)),
              b.prop("", b("Checkbox", label="Developer Extras", value=False)),
              b.prop("Tooltips", b.col(b("Checkbox", label="User Tooltips", value=True),
                                       b("Checkbox", label="Python Tooltips", value=False), spacing="small"))),
      b.panel("Text Rendering", b.prop("", b("Checkbox", label="Anti-Aliasing", value=True)),
              b.prop("Hinting", b("Dropdown", value="Auto", items=["Auto", "None", "Slight", "Full"]))),
      spacing="small", padding=0.5)
  themes = b.col(
      b.row(b("Dropdown", value="Blender Dark", items=["Blender Dark", "Blender Light", "Deep Grey", "Minimal Dark"], weight=1),
            b("Button", text="Reset", icon="LOOP_BACK")),
      b.panel("Regular", b.prop("Outline", b("ColorSwatch", value="#3d3d3d")), b.prop("Inner", b("ColorSwatch", value="#545454")),
              b.prop("Inner Selected", b("ColorSwatch", value="#4772b3")), b.prop("Text", b("ColorSwatch", value="#e5e5e5")),
              b.prop("Roundness", b("NumberSlider", value=0.2, min=0, max=1, precision=3))),
      spacing="small", padding=0.5)
  stub = b.col(b.label("Not part of this showcase.", color="muted"), padding=0.5)
  tabs_left = [("Interface", interface), ("Themes", themes), ("Viewport", stub), ("Lights", stub), ("Editing", stub),
               ("Animation", stub), ("Add-ons", stub), ("Input", stub), ("Navigation", stub), ("Keymap", keymap_tab),
               ("System", stub), ("Save & Load", stub), ("File Paths", stub)]
  icons = ["WINDOW", "COLOR", "VIEW3D", "LIGHT", "EDITMODE_HLT", "ACTION", "PLUGIN", "MOUSE_LMB", "HAND", "KEYINGSET",
           "SYSTEM", "FILE_BACKUP", "FILE_FOLDER"]
  b("SideTabs", id="root", current=P("/ui/tab"),
    tabs=[{"title": t, "icon": i, "child": c} for (t, c), i in zip(tabs_left, icons)])
  b.data({"ui": {"tab": 9, "km_tab": 0, "search": ""}, "prefs": {"scale": 1.0}, "keymap": KEYMAP})
  return {"name": "Keymap preferences", "window": "Blender Preferences", "width": 820,
          "description": "Preferences window: SideTabs for sections, Tabs per keymap, and rows templated from /keymap "
                         "arrays (Checkbox, Label, HotkeyField, remove IconButton). Recording a shortcut writes back to "
                         "the item and fires keymap_set with the operator id.",
          "messages": b.messages()}


def file_export():
  b = Surface()
  places = b.col(
      b.panel("Volumes", b("ListView", items=P("/places/volumes"), icons=["DISK_DRIVE", "NETWORK_DRIVE", "DISK_DRIVE"], rows=3)),
      b.panel("System", b("ListView", items=P("/places/system"), icons=["HOME", "DESKTOP", "FILE_FOLDER", "FILE_FOLDER",
                                                                          "FILE_IMAGE", "FILE_MOVIE"], rows=6)),
      b.panel("Bookmarks", b("ListView", items=P("/places/bookmarks"), icons=["BOOKMARKS", "BOOKMARKS"], rows=2)),
      b.panel("Recent", b("ListView", items=P("/places/recent"), icons=["FILE_FOLDER", "FILE_FOLDER", "FILE_FOLDER"], rows=3),
              collapsed=True),
      weight=1.1, spacing="small")
  browser = b("FileBrowser", path=P("/dir"), entries=P("/entries"), view="list", selected=P("/file"),
              action=ev("file_browse", dir=P("/dir"), file=P("/file")))
  bottom = b.row(b("TextField", value=P("/file"), weight=1, action=ev("file_name", file=P("/file"))),
                 b("Button", text="Export glTF 2.0", depress=True,
                   action=ev("export_gltf", dir=P("/dir"), file=P("/file"), format=P("/opts/format"),
                             selected=P("/opts/selected"), y_up=P("/opts/y_up"), draco=P("/opts/draco"))),
                 b("Button", text="Cancel", action=ev("export_cancel")))
  center = b.col(browser, bottom, weight=3, spacing="small")
  options = b.col(
      b.prop("Format", b("Dropdown", value=P("/opts/format"),
                         items=["glTF Binary (.glb)", "glTF Separate (.gltf + .bin + textures)", "glTF Embedded (.gltf)"])),
      b.prop("Copyright", b("TextField", value="", placeholder="Legal rights and conditions")),
      b.prop("Textures", b("PathField", value=P("/opts/textures"), directory=True, action=ev("browse_textures"))),
      b.prop("", b("Checkbox", label="Remember Export Settings", value=False)),
      b.panel("Include",
              b.prop("Limit to", b.col(b("Checkbox", label="Selected Objects", value=P("/opts/selected")),
                                       b("Checkbox", label="Visible Objects", value=False),
                                       b("Checkbox", label="Renderable Objects", value=True),
                                       b("Checkbox", label="Active Collection", value=False), spacing="small")),
              b.prop("Data", b.col(b("Checkbox", label="Custom Properties", value=False),
                                   b("Checkbox", label="Cameras", value=True),
                                   b("Checkbox", label="Punctual Lights", value=False), spacing="small"))),
      b.panel("Transform", b.prop("", b("Checkbox", label="+Y Up", value=P("/opts/y_up")))),
      b.panel("Data",
              b.panel("Mesh", b.prop("", b("Checkbox", label="Apply Modifiers", value=True)),
                      b.prop("", b("Checkbox", label="UVs", value=True)),
                      b.prop("", b("Checkbox", label="Normals", value=True)), sub=True),
              b.panel("Material", b.prop("Materials", b("Dropdown", value="Export", items=["Export", "Placeholder", "No Export"])),
                      b.prop("Images", b("Dropdown", value="Automatic", items=["Automatic", "JPEG Format (.jpg)", "WebP", "None"])),
                      sub=True, collapsed=True),
              b.panel("Compression", b.prop("Level", b("NumberSlider", value=6, min=0, max=10, precision=0)),
                      sub=True, header=[b("Checkbox", value=P("/opts/draco"))])),
      b.panel("Animation", b.prop("Mode", b("Dropdown", value="Actions", items=["Actions", "Active Actions merged", "NLA Tracks", "Scene"])),
              header=[b("Checkbox", value=True)], collapsed=True),
      weight=1.6, spacing="small")
  b.row(places, center, b("ScrollView", child=options, rows=24, weight=1.6), id="root", spacing="normal")
  entries = [
      {"name": "textures", "type": "dir", "modified": "Today 09:12"},
      {"name": "renders", "type": "dir", "modified": "Yesterday"},
      {"name": "hero_v012.glb", "type": "file", "size": "48.2 MiB", "modified": "Today 10:41", "icon": "FILE_3D"},
      {"name": "hero_v011.glb", "type": "file", "size": "47.9 MiB", "modified": "Mon 18:03", "icon": "FILE_3D"},
      {"name": "hero.blend", "type": "file", "size": "212 MiB", "modified": "Today 10:40", "icon": "FILE_BLEND"},
      {"name": "hero.blend1", "type": "file", "size": "211 MiB", "modified": "Today 10:32", "icon": "FILE_BACKUP"},
      {"name": "turntable.mp4", "type": "file", "size": "18.4 MiB", "modified": "Sun 14:20", "icon": "FILE_MOVIE"},
      {"name": "notes.txt", "type": "file", "size": "2 KiB", "modified": "Sun 11:02", "icon": "FILE_TEXT"},
  ]
  b.data({"dir": "/home/maya/projects/hero/export/", "file": "hero_v013.glb", "entries": entries,
          "places": {"volumes": ["/", "Studio NAS", "Scratch"], "system": ["Home", "Desktop", "Documents", "Downloads",
                                                                               "Pictures", "Videos"],
                     "bookmarks": ["hero/export", "textures"], "recent": ["export", "renders", "refs"]},
          "opts": {"format": "glTF Binary (.glb)", "textures": "//textures/", "selected": True, "y_up": True, "draco": False}})
  return {"name": "File export dialog", "window": "Blender File View — Export glTF 2.0", "width": 1200,
          "description": "Blender's file browser as an export dialog: places ListViews, a FileBrowser bound to /dir and "
                         "/file, a filename row with the operator button, and a scrolling options column with PathField, "
                         "checkboxes and a Compression sub-panel enabled from its header.",
          "messages": b.messages()}
