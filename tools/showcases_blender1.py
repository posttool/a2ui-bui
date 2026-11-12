# Copyright 2026 posttool
# SPDX-License-Identifier: Apache-2.0

"""Blender-native showcases, part 1."""

from showcase_lib import P, SEP, Surface, T, ev, M

X = [0.86, 0.22, 0.27, 1]


def object_properties():
  b = Surface()
  # --- Object tab
  loc = b("VectorField", value=P("/object/location"), suffix=" m", precision=3, step=0.1, decorators=True,
          action=ev("object_transform", prop="location", value=P("/object/location")),
          description="Location of the object")
  rot = b("VectorField", value=P("/object/rotation"), suffix="°", precision=1, decorators=True,
          action=ev("object_transform", prop="rotation_euler", value=P("/object/rotation")),
          description="Rotation in Eulers")
  mode = b("Dropdown", value=P("/object/rotation_mode"),
           items=["Quaternion (WXYZ)", "XYZ Euler", "XZY Euler", "YXZ Euler", "YZX Euler", "ZXY Euler", "ZYX Euler",
                  "Axis Angle"], description="Rotation mode")
  scale = b("VectorField", value=P("/object/scale"), precision=3, decorators=True,
            action=ev("object_transform", prop="scale", value=P("/object/scale")))
  dloc = b("VectorField", value=P("/object/delta_location"), suffix=" m", precision=3)
  drot = b("VectorField", value=P("/object/delta_rotation"), suffix="°", precision=1)
  dscale = b("VectorField", value=P("/object/delta_scale"), precision=3)
  delta = b.panel("Delta Transform", b.prop("Delta Location", dloc), b.prop("Delta Rotation", drot),
                  b.prop("Delta Scale", dscale), sub=True, collapsed=True)
  transform = b.panel("Transform", b.prop("Location", loc), b.prop("Rotation", rot), b.prop("Mode", mode),
                      b.prop("Scale", scale), delta)
  parent = b("Dropdown", value=P("/object/parent"), items=["", "Armature", "Empty", "Rig_Root"],
             icons=["", "OUTLINER_OB_ARMATURE", "OUTLINER_OB_EMPTY", "OUTLINER_OB_EMPTY"])
  ptype = b("Dropdown", value="Object", items=["Object", "Armature", "Bone", "Vertex", "3 Vertices"])
  pidx = b("NumberField", value=P("/object/pass_index"), integer=True, min=0,
           description="Index number for the \"Object Index\" render pass")
  relations = b.panel("Relations", b.prop("Parent", parent), b.prop("Parent Type", ptype), b.prop("Pass Index", pidx),
                      collapsed=True)
  coll_list = b("ListView", items=P("/object/collections"), icons=["OUTLINER_COLLECTION", "OUTLINER_COLLECTION"], rows=2)
  collections = b.panel("Collections", coll_list, collapsed=True)
  vis = b.panel(
      "Visibility",
      b.prop("", b("Checkbox", label="Selectable", value=P("/object/visibility/selectable"))),
      b("Separator", factor=0.3),
      b.prop("Show In", b.col(b("Checkbox", label="Viewports", value=P("/object/visibility/viewport")),
                              b("Checkbox", label="Renders", value=P("/object/visibility/render")), spacing="small")),
      b("Separator", factor=0.3),
      b.prop("Mask", b.col(b("Checkbox", label="Shadow Catcher", value=P("/object/visibility/shadow_catcher")),
                           b("Checkbox", label="Holdout", value=P("/object/visibility/holdout")), spacing="small")),
  )
  display = b.panel(
      "Viewport Display",
      b.prop("Show", b("Grid", columns=2, children=[
          b("Checkbox", label="Name", value=False), b("Checkbox", label="Axes", value=False),
          b("Checkbox", label="Wireframe", value=True), b("Checkbox", label="In Front", value=False)])),
      b.prop("Display As", b("Dropdown", value="Textured", items=["Bounds", "Wire", "Solid", "Textured"])),
      b.prop("Color", b("ColorSwatch", value=P("/object/color"), alpha=True)),
      collapsed=True)
  name = b.row(b("TextField", value=P("/object/name"), icon="OBJECT_DATA", weight=1,
                 action=ev("object_rename", name=P("/object/name"))),
               b("IconButton", icon="PINNED" if False else "UNPINNED", description="Pin ID"))
  obj_tab = b.col(name, transform, relations, collections, vis, display, spacing="small")
  # --- Modifiers tab
  subsurf = b.panel(
      "Subdivision", b("EnumRow", value="Catmull-Clark", items=["Catmull-Clark", "Simple"]),
      b.prop("Levels Viewport", b("NumberField", value=P("/mods/levels"), integer=True, min=0, max=6)),
      b.prop("Render", b("NumberField", value=2, integer=True, min=0, max=6)),
      b.prop("Optimal Display", b("Checkbox", value=True)),
      icon="MOD_SUBSURF",
      header=[b("Toggle", value=True, icon="EDITMODE_HLT", emboss=False, description="Display modifier in Edit mode"),
              b("Toggle", value=True, icon="RESTRICT_VIEW_OFF", iconOn="RESTRICT_VIEW_OFF", emboss=False),
              b("Toggle", value=True, icon="RESTRICT_RENDER_OFF", emboss=False)])
  bevel = b.panel("Bevel", b("EnumRow", value="Offset", items=["Vertices", "Edges"]),
                  b.prop("Amount", b("NumberField", value=0.02, suffix=" m", precision=3)),
                  b.prop("Segments", b("NumberField", value=3, integer=True, min=1)), icon="MOD_BEVEL", collapsed=True)
  add_mod = b("MenuButton", text="Add Modifier", icon="ADD", items=[
      M("Edit", items=[M("Data Transfer"), M("UV Project"), M("Vertex Weight Edit")]),
      M("Generate", items=[M("Array", icon="MOD_ARRAY"), M("Bevel", icon="MOD_BEVEL"), M("Boolean", icon="MOD_BOOLEAN"),
                           M("Mirror", icon="MOD_MIRROR"), M("Solidify", icon="MOD_SOLIDIFY"),
                           M("Subdivision Surface", icon="MOD_SUBSURF", shortcut="Ctrl 1")]),
      M("Deform", items=[M("Displace", icon="MOD_DISPLACE"), M("Lattice", icon="MOD_LATTICE"), M("Smooth", icon="MOD_SMOOTH")]),
      M("Physics", items=[M("Cloth", icon="MOD_CLOTH"), M("Fluid", icon="MOD_FLUIDSIM"), M("Ocean", icon="MOD_OCEAN")]),
  ], action=ev("modifier_add"))
  mods_tab = b.col(add_mod, subsurf, bevel, spacing="small")
  # --- Material tab
  mat_tab = b.col(
      b("ListView", items=["Body Paint", "Chrome Trim", "Glass"], icons=["MATERIAL", "MATERIAL", "MATERIAL"], rows=3,
        selected=0),
      b("IDSelector", items=["Body Paint", "Chrome Trim", "Glass", "Rubber"], value="Body Paint", icon="MATERIAL", users=1),
      b.panel("Surface", b.prop("Base Color", b("ColorSwatch", value=[0.8, 0.05, 0.04, 1])),
              b.prop("Roughness", b("NumberSlider", value=0.25, min=0, max=1, precision=3))),
      spacing="small")
  # --- Scene / World tabs
  scene_tab = b.col(
      b.panel("Scene", b.prop("Camera", b("Dropdown", value="Camera", items=["Camera", "Camera.001"], icons=["CAMERA_DATA", "CAMERA_DATA"])),
              b.prop("Background Scene", b("Dropdown", value="", items=["", "Backdrop"])), icon="SCENE_DATA"),
      b.panel("Units", b.prop("Unit System", b("Dropdown", value="Metric", items=["None", "Metric", "Imperial"])),
              b.prop("Unit Scale", b("NumberField", value=1.0, precision=6))),
      b.panel("Gravity", b.prop("Gravity", b("VectorField", value=[0, 0, -9.81], suffix=" m/s²", precision=2)),
              header=[b("Checkbox", value=True)]),
      spacing="small")
  world_tab = b.col(
      b.panel("Surface", b.prop("Color", b("ColorSwatch", value=[0.05, 0.05, 0.05, 1])),
              b.prop("Strength", b("NumberField", value=1.0, min=0, precision=3))),
      b.panel("Mist Pass", b.prop("Start", b("NumberField", value=5, suffix=" m")),
              b.prop("Depth", b("NumberField", value=25, suffix=" m")), collapsed=True),
      spacing="small")
  stub = b.col(b.label("Settings for this tab are shown in other showcases.", color="muted", icon="INFO"), padding=0.5)
  b("SideTabs", id="root", current=P("/ui/tab"), tabs=[
      {"icon": "TOOL_SETTINGS", "title": "Tool", "child": stub},
      {"icon": "RENDER_STILL", "title": "Render", "child": stub},
      {"icon": "OUTPUT", "title": "Output", "child": stub},
      {"icon": "RENDERLAYERS", "title": "View Layer", "child": stub},
      {"icon": "SCENE_DATA", "title": "Scene", "child": scene_tab},
      {"icon": "WORLD", "title": "World", "child": world_tab},
      {"icon": "OBJECT_DATA", "title": "Object", "child": obj_tab},
      {"icon": "MODIFIER", "title": "Modifiers", "child": mods_tab},
      {"icon": "PARTICLES", "title": "Particles", "child": stub},
      {"icon": "PHYSICS", "title": "Physics", "child": stub},
      {"icon": "CONSTRAINT", "title": "Object Constraints", "child": stub},
      {"icon": "MESH_DATA", "title": "Data", "child": stub},
      {"icon": "MATERIAL", "title": "Material", "child": mat_tab},
  ])
  b.data({
      "ui": {"tab": 6},
      "object": {
          "name": "Cube", "location": [1.25, -0.5, 0.75], "rotation": [0, 0, 45], "rotation_mode": "XYZ Euler",
          "scale": [1, 1, 1.5], "delta_location": [0, 0, 0], "delta_rotation": [0, 0, 0], "delta_scale": [1, 1, 1],
          "parent": "", "pass_index": 0, "collections": ["Collection", "Props"],
          "visibility": {"selectable": True, "viewport": True, "render": True, "shadow_catcher": False, "holdout": False},
          "color": [1, 1, 1, 1],
      },
      "mods": {"levels": 1},
  })
  return {"name": "Object properties", "window": "Properties", "width": 600,
          "description": "Blender's properties editor: vertical side tabs, a Transform panel with keyframe decorators and "
                         "a collapsed Delta Transform sub-panel, Relations, Visibility and Viewport Display. Every value is "
                         "two-way bound to /object in the data model.",
          "messages": b.messages()}


def render_settings():
  b = Surface()
  engine = b("Dropdown", value=P("/render/engine"), items=["EEVEE", "Workbench", "Cycles"],
             icons=["SHADING_RENDERED", "SHADING_SOLID", "SHADING_TEXTURE"],
             action=ev("set_engine", engine=P("/render/engine")))
  feature = b("Dropdown", value="Supported", items=["Supported", "Experimental"],
              description="Feature set to use for rendering")
  device = b("EnumRow", value=P("/render/device"), items=["CPU", "GPU Compute"], icons=["CPU", "GPU"],
             description="Device to use for rendering")
  opts = b("Popover", text="Options", icon="PREFERENCES", children=[
      b.label("Render Options", bold=True),
      b("Checkbox", label="Lock Interface", value=P("/render/lock_ui"),
        description="Lock interface during rendering in favor of giving more memory to the renderer"),
      b("Checkbox", label="Persistent Data", value=False),
      b("Checkbox", label="Use Spatial Splits", value=False),
      b("Separator", line=True),
      b("Dropdown", label="Display", value="New Window", items=["Keep User Interface", "New Window", "Image Editor"]),
  ])
  top = b.col(b.prop("Render Engine", engine), b.prop("Feature Set", feature), b.prop("Device", device),
              b.row(b("Spacer"), opts), spacing="small")
  vp = b.panel("Viewport",
               b.prop("Noise Threshold", b("NumberField", value=0.1, precision=4, min=0, max=1)),
               b.prop("Max Samples", b("NumberField", value=1024, integer=True, min=1)),
               b.prop("Min Samples", b("NumberField", value=0, integer=True, min=0)), sub=True, collapsed=True)
  denoise = b.panel("Denoise",
                    b.prop("Denoiser", b("Dropdown", value=P("/render/denoiser"), items=["OpenImageDenoise", "OptiX"])),
                    b.prop("Passes", b("Dropdown", value="Albedo and Normal", items=["None", "Albedo", "Albedo and Normal"])),
                    b.prop("Prefilter", b("Dropdown", value="Accurate", items=["None", "Fast", "Accurate"])),
                    sub=True, header=[b("Checkbox", value=P("/render/denoise"), description="Denoise the rendered image")])
  rnd = b.panel("Render",
                b.prop("Noise Threshold", b("NumberField", value=P("/render/threshold"), precision=4, min=0, max=1, step=0.001)),
                b.prop("Max Samples", b("NumberField", value=P("/render/samples"), integer=True, min=1, max=16384,
                                         description="Number of samples to render for each pixel")),
                b.prop("Min Samples", b("NumberField", value=0, integer=True)),
                b.prop("Time Limit", b("NumberField", value=0, suffix=" s")), denoise, sub=True)
  sampling = b.panel("Sampling", vp, rnd, icon="RENDER_STILL")
  bounces = b.col(*[b("NumberField", label=l, value=v, integer=True, min=0) for l, v in
                   (("Total", 12), ("Diffuse", 4), ("Glossy", 4), ("Transmission", 12), ("Volume", 0), ("Transparent", 8))],
                  align=True)
  lp = b.panel("Light Paths", b.prop("Max Bounces", bounces),
               b.prop("Clamping Direct", b("NumberField", value=0, precision=2)),
               b.prop("Indirect", b("NumberField", value=10, precision=2)),
               b.panel("Caustics", b("Checkbox", label="Reflective", value=True),
                       b("Checkbox", label="Refractive", value=True), sub=True, collapsed=True),
               collapsed=True)
  mb = b.panel("Motion Blur",
               b.prop("Position", b("Dropdown", value="Center on Frame", items=["Start on Frame", "Center on Frame", "End on Frame"])),
               b.prop("Shutter", b("NumberSlider", value=0.5, min=0, max=1, precision=2)),
               header=[b("Checkbox", value=False)], collapsed=True)
  status = b.col(
      b("ProgressBar", value=P("/status/progress"), text=P("/status/text")),
      b.row(b.label(P("/status/detail"), color="muted", size="small"), b("Spacer"),
            b.label(P("/status/memory"), color="muted", size="small")),
      b.row(b("Button", text="Render Image", icon="RENDER_STILL", weight=2,
              action=ev("render_start", engine=P("/render/engine"), samples=P("/render/samples"),
                        denoise=P("/render/denoise"), device=P("/render/device"))),
            b("Button", text="Render Animation", icon="RENDER_ANIMATION", weight=2,
              action=ev("render_animation", engine=P("/render/engine"))),
            b("IconButton", icon="CANCEL", emboss=True, description="Cancel render", action=ev("render_cancel"))),
      spacing="small")
  b.col(top, sampling, lp, mb, b("Separator", line=True), status, id="root", spacing="small")
  b.data({
      "render": {"engine": "Cycles", "device": "GPU Compute", "samples": 128, "threshold": 0.01, "denoise": True,
                 "denoiser": "OpenImageDenoise", "lock_ui": False},
      "status": {"progress": 0, "text": "Ready", "detail": "Frame 1 | Last: 00:00.00", "memory": "Mem: 212 MiB"},
  })
  for i, (prog, txt) in enumerate(((0.08, "Building BVH"), (0.25, "Sample 32/128"), (0.5, "Sample 64/128"),
                                   (0.75, "Sample 96/128"), (0.94, "Denoising"), (1.0, "Finished"))):
    b.data({"progress": prog, "text": txt, "detail": f"Frame 1 | Time 00:{(i + 1) * 3:02d}.{i * 17 % 100:02d}",
            "memory": f"Mem: {212 + i * 140} MiB, Peak: {300 + i * 150} MiB"}, path="/status")
  return {"name": "Render settings", "window": "Properties — Render", "width": 560,
          "description": "Cycles render properties: engine menu with icons, device EnumRow, nested Sampling sub-panels, a "
                         "Denoise sub-panel with an enable checkbox in its header, an Options popover and a live render "
                         "status bar that the agent streams with incremental updateDataModel messages.",
          "messages": b.messages()}


def material_editor():
  b = Surface()
  tiles = [{"label": n, "image": f"assets/mat_{f}.svg"} for n, f in (
      ("Red Plastic", "red_plastic"), ("Gold", "gold"), ("Brushed Steel", "steel"), ("Rubber", "rubber"),
      ("Jade", "jade"), ("Oak", "wood"), ("Concrete", "concrete"), ("Brick", "brick"), ("Neon", "emission"),
      ("Skin", "skin"), ("Glass", "glass"), ("Copper", "copper"))]
  idsel = b("IDSelector", items=P("/library/names"), value=P("/mat/name"), icon="MATERIAL", users=P("/mat/users"),
            fakeUser=P("/mat/fake_user"), action=ev("material_id", op="select", name=P("/mat/name")),
            description="Browse Material to be linked")
  slots = b("ListView", items=P("/slots"), icons=["MATERIAL", "MATERIAL"], rows=3, selected=0,
             action=ev("material_slot", op="activate"))
  preview = b.panel("Preview",
                    b.row(b("Image", src=P("/mat/preview"), height=9, fit="contain", alt="Material preview", weight=6),
                          b("EnumRow", value="Sphere", vertical=True, iconOnly=True,
                            items=[{"label": "Sphere", "icon": "MESH_UVSPHERE"}, {"label": "Cube", "icon": "MESH_CUBE"},
                                   {"label": "Hair", "icon": "CURVE_DATA"}, {"label": "World", "icon": "WORLD"}], weight=1)),
                    icon="MATERIAL")
  library = b.panel("Library", b("GridView", tiles=tiles, tile=4, selected=P("/mat/name"),
                                 action=ev("material_pick", name=P("/mat/name"))))
  bsdf = [
      b.prop("Surface", b("Dropdown", value="Principled BSDF", items=["Principled BSDF", "Diffuse BSDF", "Glossy BSDF",
                                                                        "Emission", "Mix Shader"], icons=["NODE_MATERIAL", "", "", "", ""])),
      b("Separator", factor=0.3),
      b.prop("Base Color", b("ColorSwatch", value=P("/mat/base_color"), action=ev("material_set", prop="base_color",
                                                                                  value=P("/mat/base_color")))),
      b.prop("Metallic", b("NumberSlider", value=P("/mat/metallic"), min=0, max=1, precision=3)),
      b.prop("Roughness", b("NumberSlider", value=P("/mat/roughness"), min=0, max=1, precision=3)),
      b.prop("IOR", b("NumberField", value=P("/mat/ior"), min=1, max=4, precision=3, step=0.01)),
      b.prop("Alpha", b("NumberSlider", value=P("/mat/alpha"), min=0, max=1, precision=3)),
      b.prop("Normal", b.label("Default", color="muted")),
      b.panel("Subsurface", b.prop("Weight", b("NumberSlider", value=0, min=0, max=1, precision=3)),
              b.prop("Radius", b("VectorField", value=[1, 0.2, 0.1], precision=3)),
              b.prop("Scale", b("NumberField", value=0.05, suffix=" m", precision=3)), sub=True, collapsed=True),
      b.panel("Specular", b.prop("IOR Level", b("NumberSlider", value=0.5, min=0, max=1, precision=3)),
              b.prop("Tint", b("ColorSwatch", value=[1, 1, 1, 1])), sub=True, collapsed=True),
      b.panel("Emission", b.prop("Color", b("ColorSwatch", value=P("/mat/emission"))),
              b.prop("Strength", b("NumberField", value=P("/mat/emission_strength"), min=0, precision=3)), sub=True),
  ]
  surface = b.panel("Surface", *bsdf)
  settings = b.panel("Settings",
                     b.prop("Blend Mode", b("Dropdown", value="Opaque", items=["Opaque", "Alpha Clip", "Alpha Hashed", "Alpha Blend"])),
                     b.prop("Backface Culling", b("Checkbox", value=False)),
                     b.prop("Pass Index", b("NumberField", value=0, integer=True)), collapsed=True)
  b.col(slots, idsel, preview, library, surface, settings, id="root", spacing="small")
  b.data({
      "slots": ["Red Plastic", "Brushed Steel"],
      "library": {"names": [t["label"] for t in tiles]},
      "mat": {"name": "Red Plastic", "users": 2, "fake_user": False, "preview": "assets/material_preview.png",
              "base_color": [0.8, 0.12, 0.1, 1], "metallic": 0.0, "roughness": 0.3, "ior": 1.5, "alpha": 1.0,
              "emission": [0, 0, 0, 1], "emission_strength": 0.0},
  })
  return {"name": "Material editor", "window": "Properties — Material", "width": 600,
          "description": "Material slots, template_ID data-block selector with users and fake user, a preview with shape "
                         "buttons, a GridView of material balls and the Principled BSDF inputs with Subsurface, Specular "
                         "and Emission sub-panels.",
          "messages": b.messages()}


def shader_nodes():
  b = Surface()
  add_menu = [
      M("Input", items=[M("Ambient Occlusion"), M("Attribute"), M("Fresnel"), M("Texture Coordinate"), M("UV Map")]),
      M("Shader", items=[M("Diffuse BSDF"), M("Emission"), M("Glass BSDF"), M("Mix Shader"), M("Principled BSDF")]),
      M("Texture", items=[M("Image Texture", icon="IMAGE_DATA"), M("Noise Texture"), M("Voronoi Texture"), M("Wave Texture")]),
      M("Color", items=[M("Color Ramp"), M("Hue/Saturation/Value"), M("Mix Color")]),
      M("Vector", items=[M("Bump"), M("Mapping"), M("Normal Map")]),
      M("Converter", items=[M("Math"), M("Map Range"), M("Separate XYZ")]),
      SEP, M("Frame", shortcut="Ctrl J"), M("Reroute"),
  ]
  header = [
      b("Dropdown", value="Object", items=["Object", "World", "Line Style"], description="Type of data to take shader from"),
      b("MenuButton", text="View", items=[M("Sidebar", shortcut="N", checked=True), M("Toolbar", shortcut="T"), SEP,
                                          M("Frame All", shortcut="Home"), M("Frame Selected", shortcut="Numpad .")]),
      b("MenuButton", text="Select", items=[M("All", shortcut="A"), M("None", shortcut="Alt A"), M("Invert", shortcut="Ctrl I"),
                                            SEP, M("Box Select", shortcut="B"), M("Circle Select", shortcut="C")]),
      b("MenuButton", text="Add", items=add_menu, action=ev("node_add")),
      b("MenuButton", text="Node", items=[M("Duplicate", shortcut="Shift D"), M("Delete", shortcut="X"), SEP,
                                          M("Make Group", shortcut="Ctrl G"), M("Mute", shortcut="M")]),
      b("Checkbox", label="Use Nodes", value=True),
      b("Spacer"),
      b("IDSelector", items=["Ceramic", "Ceramic.001", "Floor"], value="Ceramic", icon="MATERIAL", users=1),
      b("Spacer"),
      b("Toggle", value=True, icon="SNAP_ON", emboss=False, description="Snap node positions to the grid"),
      b("IconButton", icon="OVERLAY"),
  ]
  node = b("Node", id="node_tpl", key=P("key"), title=P("title"), kind=P("kind"), inputs=P("inputs"), outputs=P("outputs"),
           location=P("location"), width=P("width"), preview=P("preview"), collapsed=P("collapsed"))
  editor = b("NodeEditor", children=T(node, "/nodes"), links=P("/links"), height=22,
             action=ev("node_links_changed", links=P("/links")))
  b("Area", id="root", editor=P("/editor"), icon="NODE_MATERIAL", header=header, child=editor,
    editors=[{"label": "3D Viewport", "icon": "VIEW3D"}, {"label": "Image Editor", "icon": "IMAGE_EDITOR"},
             {"label": "Shader Editor", "icon": "NODE_MATERIAL"}, {"label": "Geometry Node Editor", "icon": "GEOMETRY_NODES"},
             {"label": "Compositor", "icon": "NODE_EDITOR"}, {"label": "Text Editor", "icon": "TEXT"}],
    action=ev("editor_changed", editor=P("/editor")))
  nodes = [
      {"key": "coord", "title": "Texture Coordinate", "kind": "input", "location": [20, 40], "width": 7,
       "outputs": [{"name": n, "type": "vector"} for n in ("Generated", "Normal", "UV", "Object", "Camera", "Window", "Reflection")],
       "inputs": []},
      {"key": "mapping", "title": "Mapping", "kind": "vector", "location": [200, 60], "width": 7,
       "inputs": [{"name": "Vector", "type": "vector"}, {"name": "Location", "type": "vector", "value": [0, 0, 0]},
                  {"name": "Scale", "type": "vector", "value": [4, 4, 4]}],
       "outputs": [{"name": "Vector", "type": "vector"}]},
      {"key": "noise", "title": "Noise Texture", "kind": "texture", "location": [380, 20], "width": 7,
       "preview": "assets/node_noise.svg",
       "inputs": [{"name": "Vector", "type": "vector"}, {"name": "Scale", "type": "float", "value": 5.0},
                  {"name": "Detail", "type": "float", "value": 2.0}, {"name": "Roughness", "type": "float", "value": 0.5}],
       "outputs": [{"name": "Fac", "type": "float"}, {"name": "Color", "type": "color"}]},
      {"key": "ramp", "title": "Color Ramp", "kind": "converter", "location": [570, 40], "width": 7,
       "preview": "assets/node_color.svg",
       "inputs": [{"name": "Fac", "type": "float", "value": 0.5}],
       "outputs": [{"name": "Color", "type": "color"}, {"name": "Alpha", "type": "float"}]},
      {"key": "img", "title": "Image Texture", "kind": "texture", "location": [20, 330], "width": 7,
       "preview": "assets/render.png",
       "inputs": [{"name": "Vector", "type": "vector"}],
       "outputs": [{"name": "Color", "type": "color"}, {"name": "Alpha", "type": "float"}]},
      {"key": "bsdf", "title": "Principled BSDF", "kind": "shader", "location": [770, 60], "width": 8,
       "inputs": [{"name": "Base Color", "type": "color", "value": [0.8, 0.8, 0.8, 1]},
                  {"name": "Metallic", "type": "float", "value": 0.0}, {"name": "Roughness", "type": "float", "value": 0.5},
                  {"name": "IOR", "type": "float", "value": 1.45}, {"name": "Alpha", "type": "float", "value": 1.0},
                  {"name": "Normal", "type": "vector"}],
       "outputs": [{"name": "BSDF", "type": "shader"}]},
      {"key": "out", "title": "Material Output", "kind": "output", "location": [990, 80], "width": 6,
       "inputs": [{"name": "Surface", "type": "shader"}, {"name": "Volume", "type": "shader"},
                  {"name": "Displacement", "type": "vector"}],
       "outputs": []},
  ]
  for n in nodes:
    n.setdefault("preview", "")
    n.setdefault("collapsed", False)
  links = [{"from": "coord", "out": "Object", "to": "mapping", "in": "Vector"},
           {"from": "mapping", "out": "Vector", "to": "noise", "in": "Vector"},
           {"from": "noise", "out": "Fac", "to": "ramp", "in": "Fac"},
           {"from": "ramp", "out": "Color", "to": "bsdf", "in": "Base Color"},
           {"from": "noise", "out": "Fac", "to": "bsdf", "in": "Roughness"},
           {"from": "coord", "out": "UV", "to": "img", "in": "Vector"},
           {"from": "bsdf", "out": "BSDF", "to": "out", "in": "Surface"}]
  b.data({"editor": "Shader Editor", "nodes": nodes, "links": links})
  return {"name": "Shader node graph", "window": "Shader Editor", "width": 1200,
          "description": "An editor Area with a header of menus, a data-block selector and toggles around a NodeEditor. "
                         "The nodes come from the data model through a ChildList template over /nodes, so the agent can "
                         "add, move or relink nodes by sending data, not components.",
          "messages": b.messages()}
