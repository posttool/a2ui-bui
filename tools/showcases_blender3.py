# Copyright 2026 posttool
# SPDX-License-Identifier: GPL-3.0-or-later

"""Blender-native showcases, part 3 (workspace, animation, text, assets)."""

from showcase_lib import P, SEP, Surface, T, ev, M


def top_bar():
  b = Surface()
  file_menu = [
      M("New", icon="FILE_NEW", items=[M("General", icon="FILE_NEW"), M("2D Animation"), M("Sculpting"), M("VFX"),
                                       M("Video Editing")]),
      M("Open...", icon="FILE_FOLDER", shortcut="Ctrl O"),
      M("Open Recent", items=[M("hero.blend", icon="FILE_BLEND"), M("forest_scene.blend", icon="FILE_BLEND"),
                              M("product_shot_v3.blend", icon="FILE_BLEND"), SEP, M("Clear Recent Files List...")],
        shortcut="Shift Ctrl O"),
      M("Revert", enabled=False), M("Recover", items=[M("Last Session", icon="RECOVER_LAST"), M("Auto Save...")]),
      SEP,
      M("Save", icon="FILE_TICK", shortcut="Ctrl S"), M("Save As...", shortcut="Shift Ctrl S"), M("Save Copy..."),
      SEP,
      M("Link...", icon="LINKED"), M("Append...", icon="APPEND_BLEND"),
      SEP,
      M("Import", icon="IMPORT", items=[M("Collada (.dae)"), M("Alembic (.abc)"), M("USD (.usd*)"), M("FBX (.fbx)"),
                                        M("glTF 2.0 (.glb/.gltf)"), M("Wavefront (.obj)")]),
      M("Export", icon="EXPORT", items=[M("Collada (.dae)"), M("Alembic (.abc)"), M("USD (.usd*)"), M("FBX (.fbx)"),
                                        M("glTF 2.0 (.glb/.gltf)"), M("Wavefront (.obj)")]),
      SEP,
      M("External Data", items=[M("Pack Resources"), M("Unpack Resources"), SEP, M("Make Paths Relative"),
                                M("Report Missing Files")]),
      M("Clean Up", items=[M("Purge Unused Data...")]),
      SEP,
      M("Defaults", items=[M("Save Startup File"), M("Load Factory Settings")]),
      SEP,
      M("Quit", icon="QUIT", shortcut="Ctrl Q"),
  ]
  edit_menu = [M("Undo", icon="LOOP_BACK", shortcut="Ctrl Z"), M("Redo", icon="LOOP_FORWARDS", shortcut="Shift Ctrl Z"),
               SEP, M("Undo History...", shortcut="Ctrl Alt Z"), SEP,
               M("Repeat Last", shortcut="Shift R"), M("Repeat History..."), SEP,
               M("Adjust Last Operation...", shortcut="F9"), M("Menu Search...", icon="VIEWZOOM", shortcut="F3"),
               M("Operator Search..."), SEP, M("Rename Active Item...", shortcut="F2"), M("Batch Rename...", shortcut="Ctrl F2"),
               SEP, M("Lock Object Modes", checked=True), SEP, M("Preferences...", icon="PREFERENCES")]
  render_menu = [M("Render Image", icon="RENDER_STILL", shortcut="F12"),
                 M("Render Animation", icon="RENDER_ANIMATION", shortcut="Ctrl F12"),
                 SEP, M("Render Audio..."), SEP, M("View Render", shortcut="F11"), M("View Animation", shortcut="Ctrl F11"),
                 SEP, M("Lock Interface", checked=False)]
  window_menu = [M("New Window"), M("New Main Window"), SEP, M("Toggle Window Fullscreen", icon="FULLSCREEN_ENTER"),
                 SEP, M("Next Workspace", shortcut="Ctrl PageUp"), M("Previous Workspace", shortcut="Ctrl PageDown"),
                 SEP, M("Show Status Bar", checked=True), SEP, M("Save Screenshot"), M("Toggle System Console")]
  help_menu = [M("Manual", icon="HELP", shortcut="F1"), M("Tutorials", icon="URL"), M("Support", icon="URL"), SEP,
               M("User Communities", icon="COMMUNITY"), M("Developer Community"), SEP, M("Report a Bug", icon="URL"),
               SEP, M("Save System Info"), SEP, M("About Blender", icon="BLENDER")]
  workspaces = b("EnumRow", value=P("/workspace"),
                 items=["Layout", "Modeling", "Sculpting", "Shading", "Animation", "Rendering"], action=ev("workspace_switch", workspace=P("/workspace")))
  bar = b.row(b("MenuBar", menus=[{"title": "File", "items": file_menu}, {"title": "Edit", "items": edit_menu},
                           {"title": "Render", "items": render_menu}, {"title": "Window", "items": window_menu},
                           {"title": "Help", "items": help_menu}],
          right=[b("IDSelector", items=["Scene", "Scene.001"], value="Scene", icon="SCENE_DATA")],
          action=ev("menu", item="picked"), weight=1), workspaces, spacing="large")
  mode_pie = b("PieMenu", title="Mode", hotkey="Q", value=P("/mode"), icon="OBJECT_DATAMODE", text="Mode pie",
               items=[{"label": "Object Mode", "icon": "OBJECT_DATAMODE"}, {"label": "Edit Mode", "icon": "EDITMODE_HLT"},
                      {"label": "Sculpt Mode", "icon": "SCULPTMODE_HLT"}, {"label": "Vertex Paint", "icon": "VPAINT_HLT"},
                      {"label": "Weight Paint", "icon": "WPAINT_HLT"}, {"label": "Texture Paint", "icon": "TPAINT_HLT"},
                      {"label": "Pose Mode", "icon": "POSE_HLT"}, {"label": "Particle Edit", "icon": "PARTICLEMODE"}],
               action=ev("mode_set", mode=P("/mode")),
               description="Press Q over the viewport to open the mode pie")
  snap = b("Popover", icon="SNAP_ON", text="Snap", children=[
      b.label("Snap Base", bold=True, size="small"),
      b("EnumRow", value="Closest", items=["Closest", "Center", "Median", "Active"]),
      b.label("Snap Target", bold=True, size="small"),
      b("MenuItem", label="Increment", icon="SNAP_INCREMENT", checked=False, action=ev("snap", target="increment")),
      b("MenuItem", label="Vertex", icon="SNAP_VERTEX", checked=True, action=ev("snap", target="vertex")),
      b("MenuItem", label="Edge", icon="SNAP_EDGE", checked=False, action=ev("snap", target="edge")),
      b("MenuItem", label="Face Project", icon="SNAP_FACE", checked=False, action=ev("snap", target="face")),
      b("MenuItem", label="Volume", icon="SNAP_VOLUME", shortcut="", checked=False),
      b("Separator", line=True),
      b("Checkbox", label="Align Rotation to Target", value=False),
      b("Checkbox", label="Backface Culling", value=False),
  ])
  shading = b("Popover", icon="TRIA_DOWN", children=[
      b.label("Lighting", bold=True, size="small"),
      b("EnumRow", value="Studio", items=["Flat", "Studio", "MatCap"]),
      b.label("Color", bold=True, size="small"),
      b("Grid", columns=3, align=True, children=[b("Toggle", label=l, value=l == "Material") for l in
                                                 ("Material", "Object", "Attribute", "Single", "Random", "Texture")]),
      b("Checkbox", label="Shadow", value=False), b("Checkbox", label="Cavity", value=True),
      b("NumberSlider", label="X-Ray Alpha", value=0.5, min=0, max=1, precision=3),
  ])
  vp_header = [
      b("Dropdown", value=P("/mode"), items=["Object Mode", "Edit Mode", "Sculpt Mode", "Vertex Paint", "Weight Paint",
                                              "Texture Paint", "Pose Mode", "Particle Edit"],
        icons=["OBJECT_DATAMODE", "EDITMODE_HLT", "SCULPTMODE_HLT", "VPAINT_HLT", "WPAINT_HLT", "TPAINT_HLT", "POSE_HLT",
               "PARTICLEMODE"]),
      b("MenuButton", text="View", items=[M("Toolbar", shortcut="T", checked=True), M("Sidebar", shortcut="N"), SEP,
                                          M("Frame Selected", shortcut="Numpad ."), M("Frame All", shortcut="Home"), SEP,
                                          M("Cameras", items=[M("Active Camera", shortcut="Numpad 0"),
                                                              M("Set Active Object as Camera", shortcut="Ctrl Numpad 0")])]),
      b("MenuButton", text="Select", items=[M("All", shortcut="A"), M("None", shortcut="Alt A"), M("Invert", shortcut="Ctrl I")]),
      b("MenuButton", text="Add", items=[M("Mesh", icon="OUTLINER_OB_MESH", items=[M("Plane", icon="MESH_PLANE"), M("Cube", icon="MESH_CUBE"),
                                                                                  M("UV Sphere", icon="MESH_UVSPHERE"),
                                                                                  M("Ico Sphere", icon="MESH_ICOSPHERE"),
                                                                                  M("Cylinder", icon="MESH_CYLINDER"),
                                                                                  M("Monkey", icon="MESH_MONKEY")]),
                                         M("Curve", icon="OUTLINER_OB_CURVE"), M("Light", icon="OUTLINER_OB_LIGHT"),
                                         M("Camera", icon="OUTLINER_OB_CAMERA"), M("Empty", icon="OUTLINER_OB_EMPTY")],
        action=ev("object_add")),
      b("MenuButton", text="Object", items=[M("Transform", items=[M("Move", shortcut="G"), M("Rotate", shortcut="R"),
                                                                  M("Scale", shortcut="S")]),
                                            M("Duplicate Objects", shortcut="Shift D"), M("Join", shortcut="Ctrl J"), SEP,
                                            M("Delete", shortcut="X")]),
      b("Spacer"),
      b("Dropdown", value="Global", items=["Global", "Local", "Normal", "Gimbal", "View", "Cursor"],
        icons=["ORIENTATION_GLOBAL", "ORIENTATION_LOCAL", "", "", "", "ORIENTATION_CURSOR"]),
      snap,
      b("Toggle", value=False, icon="PROP_OFF", iconOn="PROP_ON", emboss=False, description="Proportional Editing"),
      b("Spacer"),
      mode_pie,
      b("Toggle", value=False, icon="XRAY", description="Toggle X-Ray (Alt Z)"),
      b("EnumRow", value=P("/shading"), iconOnly=True,
        items=[{"label": "Wireframe", "icon": "SHADING_WIRE"}, {"label": "Solid", "icon": "SHADING_SOLID"},
               {"label": "Material Preview", "icon": "SHADING_TEXTURE"}, {"label": "Rendered", "icon": "SHADING_RENDERED"}],
        action=ev("viewport_shading", shading=P("/shading"))),
      shading,
  ]
  viewport = b("Image", src="assets/viewport.svg", height=20, fit="cover", alt="3D viewport")
  area = b("Area", editor="3D Viewport", icon="VIEW3D", header=vp_header, child=viewport)
  status = b.row(b.label("Select", icon="MOUSE_LMB", size="small"), b.label("Rotate View", icon="MOUSE_MMB", size="small"),
                 b.label("Object", icon="MOUSE_RMB", size="small"), b("Spacer"),
                 b.label("Cube | Verts 8 | Objects 1/3", size="small", color="muted"),
                 b.label("4.2.3", size="small", color="muted"), spacing="large")
  b.col(bar, area, status, id="root", spacing="none")
  b.data({"workspace": "Layout", "mode": "Object Mode", "shading": "Solid"})
  return {"name": "Top bar & workspace", "window": "Blender 4.2 — hero.blend", "width": 1200,
          "description": "The top bar MenuBar with nested File / Edit / Render / Window / Help menus (submenus, shortcuts, "
                         "check marks, separators), workspace tabs, a 3D Viewport area header with mode dropdown, a PieMenu "
                         "bound to the Q key, a Snap popover made of MenuItem rows and viewport shading buttons.",
          "messages": b.messages()}


def animation():
  b = Surface()

  def keyed(label, path, state_path, **kw):
    return b.row(b("NumberField", label=label, value=P(path), weight=1, **kw),
                 b("Decorator", state=P(state_path), action=ev("keyframe_toggle", prop=label, state=P(state_path)),
                   description="Insert keyframe (I)"),
                 spacing="small")
  transform = b.panel(
      "Transform",
      b.label("Location", color="muted"),
      b.col(keyed("X", "/bone/loc/0", "/keys/loc/0", suffix=" m", precision=3),
            keyed("Y", "/bone/loc/1", "/keys/loc/1", suffix=" m", precision=3),
            keyed("Z", "/bone/loc/2", "/keys/loc/2", suffix=" m", precision=3), align=True),
      b.label("Rotation", color="muted"),
      b.col(keyed("X", "/bone/rot/0", "/keys/rot/0", suffix="°", precision=1),
            keyed("Y", "/bone/rot/1", "/keys/rot/1", suffix="°", precision=1),
            keyed("Z", "/bone/rot/2", "/keys/rot/2", suffix="°", precision=1), align=True),
      b.label("Decorator states", color="muted", size="small"),
      b("Grid", columns=3, children=[b.row(b("Decorator", value=v), b.label(v.capitalize(), size="small"), spacing="small")
                                     for v in ("none", "animated", "keyframe", "driven", "changed")]))
  constraint = b.panel(
      "Copy Rotation",
      b.prop("Target", b("TextField", value="Rig_Root", icon="OUTLINER_OB_ARMATURE")),
      b.prop("Bone", b("TextField", value="spine.003", icon="BONE_DATA")),
      b.prop("Axis", b.row(b("Toggle", label="X", value=True), b("Toggle", label="Y", value=True),
                           b("Toggle", label="Z", value=False), align=True)),
      b.prop("Mix", b("Dropdown", value="Replace", items=["Replace", "Add", "Before Original", "After Original", "Offset (Legacy)"])),
      b.prop("Influence", b.row(b("NumberSlider", value=P("/constraint/influence"), min=0, max=1, precision=3, weight=1,
                                   action=ev("constraint_influence", value=P("/constraint/influence"))),
                                 b("Decorator", state=P("/keys/influence")), spacing="small")),
      icon="CONSTRAINT",
      header=[b("Toggle", value=True, icon="HIDE_OFF", iconOn="HIDE_OFF", emboss=False),
              b("IconButton", icon="X", action=ev("constraint_remove"))])
  driver = b.panel("Drivers",
                   b.prop("Type", b("Dropdown", value="Scripted Expression", items=["Averaged Value", "Sum Values",
                                                                                    "Scripted Expression", "Minimum Value",
                                                                                    "Maximum Value"])),
                   b.prop("Expression", b("TextField", value="sin(frame / 8) * 0.25", icon="DRIVER")),
                   b.prop("", b("Checkbox", label="Use Self", value=False)), collapsed=True, icon="DRIVER")
  video = b("Video", src="assets/playblast.mp4", poster="assets/playblast_poster.png", controls=True, loop=True,
            height=11, fit="contain", action=ev("playblast_ended"))
  timeline_opts = b.row(
      b("MenuButton", text="Playback", items=[M("Audio Scrubbing", checked=False), M("Follow Current Frame", checked=True),
                                              SEP, M("Sync", items=[M("Play Every Frame"), M("Frame Dropping"), M("Sync to Audio")])]),
      b("MenuButton", text="Keying", items=[M("Only Insert Needed"), M("Visual Keying"), SEP, M("Cycle-Aware Keying")]),
      b("Toggle", value=P("/auto_key"), icon="REC", description="Automatic keyframe insertion"),
      b("Dropdown", value="Location & Rotation", items=["Location", "Rotation", "Location & Rotation", "Whole Character"],
        icons=["KEYINGSET", "KEYINGSET", "KEYINGSET", "KEYINGSET"], weight=2),
      b("Spacer"),
      b.row(b("NumberField", label="Start", value=P("/range/0"), integer=True),
            b("NumberField", label="End", value=P("/range/1"), integer=True), align=True, weight=3))
  timeline = b.row(
      b.row(b("IconButton", icon="REW", description="Jump to start"), b("IconButton", icon="PREV_KEYFRAME"),
            b("Toggle", value=P("/playing"), icon="PLAY", iconOn="PAUSE", emboss=False,
              action=ev("playback_toggle", playing=P("/playing"), frame=P("/frame"))),
            b("IconButton", icon="NEXT_KEYFRAME"), b("IconButton", icon="FF", description="Jump to end"), spacing="none"),
      b("Spacer"),
      b("NumberField", value=P("/frame"), integer=True, min=P("/range/0"), max=P("/range/1"),
        action=ev("frame_change", frame=P("/frame")), description="Current frame"))
  left = b.col(video, timeline, timeline_opts, b.panel("Influence over time", b("Histogram", bins=P("/curve"), mode="bars", height=4,
                                                                labels=["1", "", "", "24", "", "", "48", "", "", "72", "", "", "96"])),
               weight=3, spacing="small")
  right = b.col(b("IDSelector", items=["Hero_Walk", "Hero_Idle", "Hero_Jump"], value="Hero_Walk", icon="ACTION", users=1,
                  fakeUser=True), transform, constraint, driver, weight=2, spacing="small")
  b.row(left, right, id="root", spacing="large")
  b.data({"bone": {"loc": [0.0, 0.124, 0.98], "rot": [12.5, 0.0, -3.0]},
          "keys": {"loc": ["keyframe", "animated", "none"], "rot": ["animated", "driven", "changed"], "influence": "animated"},
          "constraint": {"influence": 0.75}, "auto_key": False, "playing": False, "frame": 24, "range": [1, 96],
          "curve": [0.1, 0.18, 0.3, 0.45, 0.62, 0.75, 0.82, 0.86, 0.8, 0.66, 0.5, 0.36, 0.25]})
  b.data(36, path="/frame")
  b.data(["keyframe", "keyframe", "none"], path="/keys/loc")
  return {"name": "Animation", "window": "Animation — Hero_Walk", "width": 1150,
          "description": "Playblast Video with Blender's scrubber, timeline transport controls (play Toggle with PLAY/PAUSE "
                         "icons, frame NumberField), keyframe Decorators in every state, a constraint with an animated "
                         "influence slider and follow-up updateDataModel messages that move the playhead.",
          "messages": b.messages()}


SCRIPT = '''import bpy
from mathutils import Vector

# Scatter cubes along a spiral and key their scale.
def build_spiral(count=24, radius=4.0, turns=2.5):
    coll = bpy.data.collections.new("Spiral")
    bpy.context.scene.collection.children.link(coll)
    for i in range(count):
        t = i / count
        angle = t * turns * 6.28318
        loc = Vector((radius * t * cos(angle), radius * t * sin(angle), t * 2))
        bpy.ops.mesh.primitive_cube_add(size=0.3, location=loc)
        ob = bpy.context.active_object
        ob.name = f"Spiral_{i:02d}"
        coll.objects.link(ob)
        ob.keyframe_insert("scale", frame=1 + i)

build_spiral()
print("done")
'''


def text_editor():
  b = Surface()
  templates = M("Templates", items=[
      M("Python", items=[M("Addon Add Object"), M("Background Job"), M("Custom Nodes"), M("Gizmo Simple"),
                         M("Operator Modal"), M("Operator Simple"), M("UI Panel"), M("UI Pie Menu")]),
      M("Open Shading Language", items=[M("Basic Shader"), M("Cell Noise"), M("Noise")])])
  header = [
      b("MenuButton", text="View", items=[M("Sidebar", shortcut="Ctrl T"), SEP, M("Line Numbers", checked=True),
                                          M("Word Wrap", checked=False), M("Syntax Highlight", checked=True), SEP,
                                          M("Top", shortcut="Ctrl Home"), M("Bottom", shortcut="Ctrl End")]),
      b("MenuButton", text="Text", items=[M("New", icon="FILE_NEW", shortcut="Alt N"), M("Open...", icon="FILE_FOLDER",
                                                                                     shortcut="Alt O"),
                                          M("Reload", shortcut="Alt R"), SEP, M("Save", icon="FILE_TICK", shortcut="Alt S"),
                                          M("Save As...", shortcut="Shift Ctrl Alt S"), SEP, M("Run Script", icon="PLAY",
                                                                                              shortcut="Alt P")]),
      b("MenuButton", text="Edit", items=[M("Undo", shortcut="Ctrl Z"), M("Redo", shortcut="Shift Ctrl Z"), SEP,
                                          M("Cut", shortcut="Ctrl X"), M("Copy", shortcut="Ctrl C"), M("Paste", shortcut="Ctrl V"),
                                          SEP, M("Find & Replace...", shortcut="Ctrl F"), M("Jump To...", shortcut="Ctrl J")]),
      b("MenuButton", text="Format", items=[M("Indent", shortcut="Tab"), M("Unindent", shortcut="Shift Tab"), SEP,
                                            M("Toggle Comments", shortcut="Ctrl /"), SEP,
                                            M("Convert Whitespace", items=[M("To Spaces"), M("To Tabs")])]),
      b("MenuButton", text="Templates", items=templates["items"], action=ev("text_template")),
      b("IDSelector", items=P("/texts"), value=P("/text"), icon="TEXT", action=ev("text_select", text=P("/text"))),
      b("Spacer"),
      b.row(b("Toggle", value=P("/view/lines"), icon="LINENUMBERS_OFF", iconOn="LINENUMBERS_ON", description="Line numbers"),
            b("Toggle", value=P("/view/wrap"), icon="WORDWRAP_OFF", iconOn="WORDWRAP_ON", description="Word wrap"),
            b("Toggle", value=P("/view/syntax"), icon="SYNTAX_OFF", iconOn="SYNTAX_ON", description="Syntax highlight"),
            align=True),
      b("Button", text="Run Script", icon="PLAY", action=ev("run_script", text=P("/text"), source=P("/source"))),
  ]
  body = b.col(
      b("TextArea", value=P("/source"), rows=20, monospace=True),
      b.row(b.label(P("/status"), size="small", color="muted"), b("Spacer"),
            b.label("Text: Internal", size="small", color="muted")),
      spacing="small")
  b("Area", id="root", editor="Text Editor", icon="TEXT", header=header, child=body)
  b.data({"texts": ["spiral.py", "rig_ui.py", "render_farm_submit.py"], "text": "spiral.py", "source": SCRIPT,
          "view": {"lines": True, "wrap": False, "syntax": True}, "status": "Ln 12, Col 41"})
  return {"name": "Text editor", "window": "Text Editor — spiral.py", "width": 1100,
          "description": "Text editor area: header menus with a Templates submenu tree, a text data-block selector, "
                         "joined icon Toggles (line numbers, word wrap, syntax) and a monospace TextArea bound to /source "
                         "that the Run Script action sends back to the agent.",
          "messages": b.messages()}


def asset_browser():
  b = Surface()
  assets = [
      ("Oak Chair", "asset_chair", "Furniture"), ("Floor Lamp", "asset_lamp", "Furniture"),
      ("Wooden Crate", "asset_crate", "Props"), ("Granite Rock", "asset_rock", "Nature"),
      ("Pine Tree", "asset_tree", "Nature"), ("Suzanne", "asset_suzanne", "Props"),
      ("Meadow HDRI", "asset_hdri", "Worlds"), ("Red Plastic", "mat_red_plastic", "Materials"),
      ("Gold", "mat_gold", "Materials"), ("Brushed Steel", "mat_steel", "Materials"),
      ("Oak Wood", "mat_wood", "Materials"), ("Concrete", "mat_concrete", "Materials"),
      ("Brick Wall", "mat_brick", "Materials"), ("Neon Blue", "mat_emission", "Materials"),
      ("Jade", "mat_jade", "Materials"), ("Copper", "mat_copper", "Materials"),
  ]
  tiles = [{"label": n, "image": f"assets/{f}.svg"} for n, f, _ in assets]
  cats = [{"label": "All", "icon": "ASSET_MANAGER", "id": "all", "children": [
      {"label": "Furniture", "icon": "FILE_FOLDER", "id": "furn"}, {"label": "Materials", "icon": "FILE_FOLDER", "id": "mat",
                                                                      "children": [{"label": "Metals", "icon": "FILE_FOLDER", "id": "metal"},
                                                                                   {"label": "Stone", "icon": "FILE_FOLDER", "id": "stone"}],
                                                                      "expanded": True},
      {"label": "Nature", "icon": "FILE_FOLDER", "id": "nature"}, {"label": "Props", "icon": "FILE_FOLDER", "id": "props"},
      {"label": "Worlds", "icon": "FILE_FOLDER", "id": "worlds"}], "expanded": True},
      {"label": "Unassigned", "icon": "FILE_HIDDEN", "id": "none"}]
  header = [
      b("Dropdown", value=P("/library"), items=["All Libraries", "Current File", "Essentials", "Studio Library"],
        description="Choose the asset library to display"),
      b("MenuButton", text="View", items=[M("Sidebar", shortcut="N", checked=True), M("Source List", shortcut="T", checked=True),
                                          SEP, M("Refresh", icon="FILE_REFRESH")]),
      b("MenuButton", text="Select", items=[M("All", shortcut="A"), M("None", shortcut="Alt A")]),
      b("MenuButton", text="Catalog", items=[M("New Catalog", icon="ADD"), M("Delete Catalog", icon="REMOVE"), SEP,
                                             M("Save All Catalogs")]),
      b("Spacer"),
      b("Dropdown", value="Append (Reuse Data)", items=["Link", "Append", "Append (Reuse Data)"],
        description="Import method"),
      b("SearchField", value=P("/search"), placeholder="Search assets", action=ev("asset_search", q=P("/search"))),
      b("IconButton", icon="FILTER"),
  ]
  side = b("TreeView", items=cats, selected=P("/catalog"), rows=12, action=ev("asset_catalog", catalog=P("/catalog")),
           weight=1)
  grid = b("GridView", tiles=P("/tiles"), tile=P("/tile_size"), selected=P("/active"),
           action=ev("asset_activate", name=P("/active")), weight=4)
  meta = b.col(
      b("Image", src=P("/meta/preview"), height=7, fit="contain", alt="Asset preview"),
      b.panel("Asset Metadata",
              b.prop("Name", b("TextField", value=P("/active"))),
              b.prop("Source", b.label("Studio Library › furniture.blend", color="muted", size="small")),
              b.prop("Description", b("TextArea", value=P("/meta/description"), rows=3)),
              b.prop("License", b("Dropdown", value="CC0", items=["CC0", "CC-BY 4.0", "Studio internal"])),
              b.prop("Author", b("TextField", value=P("/meta/author"), icon="USER")),
              b.prop("Preview size", b("NumberSlider", value=P("/tile_size"), min=3, max=8, precision=1))),
      b.panel("Tags", b("ListView", items=P("/meta/tags"), icons=["TAG", "TAG", "TAG"], rows=3)),
      weight=1.6, spacing="small")
  b("Area", id="root", editor="Asset Browser", icon="ASSET_MANAGER", header=header,
    child=b.row(side, grid, meta, spacing="normal"))
  b.data({"library": "Studio Library", "search": "", "catalog": "all", "tiles": tiles, "tile_size": 4.5,
          "active": "Oak Chair",
          "meta": {"preview": "assets/asset_chair.svg", "description": "Solid oak dining chair, 2k textures, 3.1k tris.",
                   "author": "Maya Okafor", "tags": ["furniture", "wood", "interior"]}})
  return {"name": "Asset browser", "window": "Asset Browser", "width": 1200,
          "description": "Asset browser area: library Dropdown and SearchField in the header, a catalog TreeView, a "
                         "GridView of 16 previews whose size is bound to the Preview size slider, and an asset metadata "
                         "sidebar with Image, TextArea and tag ListView.",
          "messages": b.messages()}
