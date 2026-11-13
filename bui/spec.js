/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// BUI catalog spec: the single source of truth for every BUI component's
// A2UI props. bui/catalog.js turns it into Zod schemas for the renderer, and
// tools/build_catalog.mjs turns it into catalog.json (A2UI v1.0 catalog
// definition, JSON Schema) for agents and validators.
//
// Component names, props and semantics follow BUI's component library
// (github.com/ppmpreetham/BUI, docs/components.md), which is Blender's
// interface as a library. Prop kinds:
//   str / num / bool / strList  bindable literal or {"@path"} / {"@call"};
//                               two-way where the user can change it
//   value                       any JSON (arrays / objects) or a binding
//   enum                        static string from `values`
//   child / children            component id / ChildList (ids or template)
//   action                      A2UI Action (event or functionCall)
//   tabs                        [{title, child, icon?}]

export const BUI_CATALOG_ID = 'https://a2ui-bui-demo.local/catalogs/bui/v1/catalog.json';

const COMMON = {
  description: {kind: 'str', doc: 'Tooltip text, shown after hovering (Blender tooltip).'},
  enabled: {kind: 'bool', doc: 'false draws the widget inactive and ignores input.'},
  weight: {kind: 'number', doc: 'Share of the width inside a Row (flex-grow).'},
};

const ITEM_DOC = 'Items are strings, or objects {label, icon?, description?, value?}.';
const MENU_ITEM_DOC =
    'Menu items: {label, icon?, shortcut?, value?, description?, enabled?, checked?, items? (submenu)} or {separator: true}.';

export const COMPONENTS = {
  // ---------------------------------------------------------------- layout
  Column: {
    group: 'Layout',
    doc: 'Vertical stack. align=true joins widgets like Blender\'s column(align=True).',
    props: {
      children: {kind: 'children', required: true},
      align: {kind: 'bool', doc: 'Join adjacent widgets (shared outline, no gaps).'},
      spacing: {kind: 'enum', values: ['none', 'small', 'normal', 'large']},
      padding: {kind: 'num', doc: 'Inner padding in UI units.'},
    },
  },
  Row: {
    group: 'Layout',
    doc: 'Horizontal stack. Each child\'s weight is its share of the width.',
    props: {
      children: {kind: 'children', required: true},
      align: {kind: 'bool', doc: 'Join adjacent widgets.'},
      spacing: {kind: 'enum', values: ['none', 'small', 'normal', 'large']},
      justify: {kind: 'enum', values: ['start', 'center', 'end', 'spaceBetween']},
    },
  },
  Split: {
    group: 'Layout',
    doc: 'Label / value split used by property rows (Blender use_property_split).',
    props: {
      left: {kind: 'child', required: true},
      right: {kind: 'child', required: true},
      factor: {kind: 'num', doc: 'Share of the width for the left side (default 0.4).'},
    },
  },
  Grid: {
    group: 'Layout',
    doc: 'Grid flow of children.',
    props: {
      children: {kind: 'children', required: true},
      columns: {kind: 'num', doc: 'Column count (default 2).'},
      align: {kind: 'bool'},
    },
  },
  Box: {
    group: 'Layout',
    doc: 'Blender layout.box(): an inset, outlined region.',
    props: {
      children: {kind: 'children', required: true},
      align: {kind: 'bool'},
    },
  },
  Panel: {
    group: 'Layout',
    doc: 'Collapsible properties-editor panel with optional icon, header widgets and sub-panels.',
    props: {
      title: {kind: 'str', required: true},
      children: {kind: 'children', required: true},
      collapsed: {kind: 'bool', doc: 'Two-way: true when folded.'},
      icon: {kind: 'str', doc: 'Blender icon name (e.g. "SCENE_DATA").'},
      header: {kind: 'children', doc: 'Widgets drawn in the header (e.g. an enable Checkbox).'},
      sub: {kind: 'bool', doc: 'Draw as a sub-panel (nested, lighter header).'},
    },
  },
  Tabs: {
    group: 'Layout',
    doc: 'Horizontal tab row switching between child components.',
    props: {
      tabs: {kind: 'tabs', required: true},
      current: {kind: 'num', doc: 'Two-way: index of the open tab.'},
    },
  },
  SideTabs: {
    group: 'Layout',
    doc: 'The properties editor\'s vertical icon tabs.',
    props: {
      tabs: {kind: 'tabs', required: true, doc: 'Each tab: {icon, title, child}.'},
      current: {kind: 'num', doc: 'Two-way: index of the open tab.'},
    },
  },
  ScrollView: {
    group: 'Layout',
    doc: 'Scrolling region with Blender\'s thin scrollbar.',
    props: {
      child: {kind: 'child', required: true},
      rows: {kind: 'num', doc: 'Visible height in UI rows (default 8).'},
    },
  },
  Area: {
    group: 'Layout',
    doc: 'An editor area: 1.3-unit header with the editor-type menu, then the editor.',
    props: {
      editor: {kind: 'str', required: true, doc: 'Editor type name, e.g. "Shader Editor". Two-way.'},
      icon: {kind: 'str'},
      editors: {kind: 'value', doc: 'Editor types for the editor-type menu: strings or {label, icon}.'},
      header: {kind: 'children', doc: 'Header items (MenuButton, Spacer, IconButton ...).'},
      child: {kind: 'child', required: true},
      height: {kind: 'num', doc: 'Height in UI units (default fits content).'},
      action: {kind: 'action', doc: 'Fired when the editor type changes; context.editor is the new type.'},
    },
  },

  // ---------------------------------------------------------------- values
  NumberField: {
    group: 'Values',
    doc: 'Blender number field: drag sideways to change, click arrows to step, double-click to type.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'num', required: true, doc: 'Two-way.'},
      min: {kind: 'num'}, max: {kind: 'num'}, step: {kind: 'num'},
      precision: {kind: 'num', doc: 'Decimal places.'},
      integer: {kind: 'bool'},
      suffix: {kind: 'str', doc: 'Unit suffix: "m", "°", "%", "W" ...'},
      action: {kind: 'action', doc: 'Fired after a change; context.value is the new value.'},
    },
  },
  NumberSlider: {
    group: 'Values',
    doc: 'Blender factor slider: a filled bar between min and max.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'num', required: true, doc: 'Two-way.'},
      min: {kind: 'num'}, max: {kind: 'num'},
      precision: {kind: 'num'},
      suffix: {kind: 'str'},
      action: {kind: 'action'},
    },
  },
  VectorField: {
    group: 'Values',
    doc: 'Aligned number fields for a vector (Location, Rotation, Scale ...).',
    props: {
      label: {kind: 'str'},
      value: {kind: 'value', required: true, doc: 'Two-way array of numbers.'},
      axes: {kind: 'str', doc: 'Axis letters, default "XYZW".'},
      min: {kind: 'num'}, max: {kind: 'num'}, step: {kind: 'num'},
      precision: {kind: 'num'},
      suffix: {kind: 'str'},
      decorators: {kind: 'bool', doc: 'Draw a keyframe decorator after each field.'},
      action: {kind: 'action'},
    },
  },
  TextField: {
    group: 'Values',
    doc: 'Single-line text field.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'str', required: true, doc: 'Two-way.'},
      placeholder: {kind: 'str'},
      icon: {kind: 'str'},
      action: {kind: 'action', doc: 'Fired on Enter; context.value.'},
    },
  },
  TextArea: {
    group: 'Values',
    doc: 'Multi-line text area (Blender text editor styling).',
    props: {
      label: {kind: 'str'},
      value: {kind: 'str', required: true, doc: 'Two-way.'},
      rows: {kind: 'num', doc: 'Visible rows (default 4).'},
      monospace: {kind: 'bool'},
    },
  },
  SearchField: {
    group: 'Values',
    doc: 'Search field with the search icon and a clear button.',
    props: {
      value: {kind: 'str', doc: 'Two-way.'},
      placeholder: {kind: 'str'},
      action: {kind: 'action'},
    },
  },
  HotkeyField: {
    group: 'Values',
    doc: 'Click, then press a key combination to record it.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'str', required: true, doc: 'Two-way, e.g. "Ctrl Shift S".'},
      action: {kind: 'action'},
    },
  },
  Checkbox: {
    group: 'Values',
    doc: 'Blender checkbox with label.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'bool', required: true, doc: 'Two-way.'},
      action: {kind: 'action'},
    },
  },
  Toggle: {
    group: 'Values',
    doc: 'Toggle button (depressed when on), optionally icon-only.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'bool', required: true, doc: 'Two-way.'},
      icon: {kind: 'str'},
      iconOn: {kind: 'str', doc: 'Icon while on (e.g. HIDE_OFF / HIDE_ON).'},
      emboss: {kind: 'bool', doc: 'false draws without a button background.'},
      action: {kind: 'action'},
    },
  },
  Decorator: {
    group: 'Values',
    doc: 'The keyframe dot next to a property; click to insert or remove a keyframe.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'enum', values: ['none', 'animated', 'keyframe', 'driven', 'changed']},
      state: {kind: 'str', doc: 'Two-way state (none | animated | keyframe | driven | changed); overrides value.'},
      action: {kind: 'action'},
    },
  },
  Dropdown: {
    group: 'Values',
    doc: 'Blender enum menu button. ' + ITEM_DOC,
    props: {
      label: {kind: 'str'},
      items: {kind: 'value', required: true},
      icons: {kind: 'strList', doc: 'One icon per item ("" for none).'},
      value: {kind: 'str', doc: 'Two-way selected item (label or value).'},
      iconOnly: {kind: 'bool'},
      action: {kind: 'action'},
    },
  },
  EnumRow: {
    group: 'Values',
    doc: 'Expanded enum: a row (or column) of radio buttons. ' + ITEM_DOC,
    props: {
      label: {kind: 'str'},
      items: {kind: 'value', required: true},
      icons: {kind: 'strList'},
      value: {kind: 'str', doc: 'Two-way.'},
      vertical: {kind: 'bool'},
      iconOnly: {kind: 'bool'},
      action: {kind: 'action'},
    },
  },
  ColorSwatch: {
    group: 'Values',
    doc: 'Color swatch; click to open the HSV wheel or SV-square picker with RGB/HSV sliders and hex.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'value', required: true, doc: 'Two-way [r, g, b, a] floats 0..1, or a hex string.'},
      picker: {kind: 'enum', values: ['circle', 'square']},
      alpha: {kind: 'bool'},
      action: {kind: 'action'},
    },
  },
  IDSelector: {
    group: 'Values',
    doc: 'Blender template_ID: data-block menu, name field, user count, fake user, new and unlink.',
    props: {
      items: {kind: 'strList', required: true},
      value: {kind: 'str', doc: 'Two-way.'},
      icon: {kind: 'str'},
      users: {kind: 'num'},
      fakeUser: {kind: 'bool', doc: 'Two-way.'},
      action: {kind: 'action', doc: 'context.op is "select" | "new" | "unlink" | "fake_user" | "rename".'},
    },
  },
  PathField: {
    group: 'Values',
    doc: 'File or directory path field with a browse button.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'str', required: true, doc: 'Two-way.'},
      directory: {kind: 'bool'},
      action: {kind: 'action', doc: 'Fired by the browse button.'},
    },
  },

  // ------------------------------------------------------ buttons, feedback
  Button: {
    group: 'Buttons',
    doc: 'Operator button.',
    props: {
      text: {kind: 'str'},
      icon: {kind: 'str'},
      emboss: {kind: 'bool'},
      depress: {kind: 'bool', doc: 'Draw pressed / highlighted (Blender depress).'},
      alert: {kind: 'bool', doc: 'Red alert styling (Blender layout.alert).'},
      action: {kind: 'action'},
    },
  },
  IconButton: {
    group: 'Buttons',
    doc: 'Icon-only button (unembossed by default).',
    props: {
      icon: {kind: 'str', required: true},
      emboss: {kind: 'bool'},
      action: {kind: 'action'},
    },
  },
  Popover: {
    group: 'Buttons',
    doc: 'A button that opens a floating panel with child widgets.',
    props: {
      text: {kind: 'str'},
      icon: {kind: 'str'},
      children: {kind: 'children', required: true},
    },
  },
  MenuButton: {
    group: 'Buttons',
    doc: 'Pulldown menu button (header style). ' + MENU_ITEM_DOC,
    props: {
      text: {kind: 'str'},
      icon: {kind: 'str'},
      items: {kind: 'value', required: true},
      action: {kind: 'action', doc: 'Fired on pick; context.item is the item value or label.'},
    },
  },
  MenuItem: {
    group: 'Buttons',
    doc: 'A menu row (icon, label, shortcut) usable directly in layouts or popovers.',
    props: {
      label: {kind: 'str', required: true},
      icon: {kind: 'str'},
      shortcut: {kind: 'str'},
      checked: {kind: 'bool'},
      action: {kind: 'action'},
    },
  },
  Label: {
    group: 'Buttons',
    doc: 'Text label with optional icon.',
    props: {
      text: {kind: 'str', required: true},
      icon: {kind: 'str'},
      align: {kind: 'enum', values: ['left', 'center', 'right']},
      color: {kind: 'str', doc: 'CSS color or role: muted | accent | red | green | yellow | orange.'},
      bold: {kind: 'bool'},
      size: {kind: 'enum', values: ['small', 'normal', 'large', 'title']},
    },
  },
  Image: {
    group: 'Buttons',
    doc: 'An image (PNG, JPEG, WebP, GIF, SVG).',
    props: {
      src: {kind: 'str', required: true},
      fit: {kind: 'enum', values: ['contain', 'cover', 'fill', 'none']},
      height: {kind: 'num', doc: 'Height in UI units.'},
      alt: {kind: 'str'},
    },
  },
  Video: {
    group: 'Buttons',
    doc: 'A video with Blender\'s play/pause button and scrubber when controls=true.',
    props: {
      src: {kind: 'str', required: true},
      autoplay: {kind: 'bool'}, loop: {kind: 'bool'}, controls: {kind: 'bool'},
      poster: {kind: 'str'},
      fit: {kind: 'enum', values: ['contain', 'cover']},
      height: {kind: 'num'},
      action: {kind: 'action', doc: 'Fired when playback ends.'},
    },
  },
  ProgressBar: {
    group: 'Buttons',
    doc: 'Progress bar, 0..1, with optional text.',
    props: {
      value: {kind: 'num', required: true},
      text: {kind: 'str'},
    },
  },
  Separator: {
    group: 'Buttons',
    doc: 'Vertical gap, optionally a line.',
    props: {
      factor: {kind: 'num', doc: 'Gap size in UI units (default 0.5).'},
      line: {kind: 'bool'},
    },
  },
  Spacer: {
    group: 'Buttons',
    doc: 'Pushes the following items to the far side of a Row or Area header.',
    props: {},
  },

  // ------------------------------------------------------------------ views
  ListView: {
    group: 'Views',
    doc: 'Blender UIList: rows with icons, active row, filter and double-click rename. ' + ITEM_DOC,
    props: {
      items: {kind: 'value', required: true},
      icons: {kind: 'strList'},
      rows: {kind: 'num', doc: 'Visible rows (default 5).'},
      selected: {kind: 'num', doc: 'Two-way active row index.'},
      filter: {kind: 'bool', doc: 'Show the filter field under the list.'},
      action: {kind: 'action', doc: 'Fired on activate (click) or rename; context.index, context.item, context.op.'},
    },
  },
  TreeView: {
    group: 'Views',
    doc: 'Outliner-style tree: [{label, icon?, id?, children?, expanded?, toggles?: {column: bool}}].',
    props: {
      items: {kind: 'value', required: true},
      columns: {kind: 'strList', doc: 'Toggle columns on the right: select | hide | viewport | render.'},
      selected: {kind: 'str', doc: 'Two-way id (or label) of the active item.'},
      rows: {kind: 'num'},
      action: {kind: 'action', doc: 'context.op is "select" | "toggle"; context.item, context.column, context.on.'},
    },
  },
  GridView: {
    group: 'Views',
    doc: 'Preview tiles: [{label, color? [r,g,b,a] | css, image?, icon?}].',
    props: {
      tiles: {kind: 'value', required: true},
      tile: {kind: 'num', doc: 'Tile size in UI units (default 4).'},
      selected: {kind: 'str', doc: 'Two-way label of the active tile.'},
      action: {kind: 'action'},
    },
  },
  FileBrowser: {
    group: 'Views',
    doc: 'Blender File Browser: path bar, list or thumbnail view of entries.',
    props: {
      path: {kind: 'str', required: true, doc: 'Two-way current directory.'},
      entries: {kind: 'value', required: true, doc: '[{name, type: "dir"|"file", size?, modified?, icon?, color?}]'},
      view: {kind: 'enum', values: ['list', 'thumbnails']},
      selected: {kind: 'str', doc: 'Two-way selected entry name.'},
      action: {kind: 'action', doc: 'context.op is "open" | "select" | "parent"; context.name.'},
    },
  },

  // ------------------------------------------------------------------ menus
  MenuBar: {
    group: 'Menus',
    doc: 'Blender top bar: menus open on click and switch on hover. menus: [{title, items}]. ' + MENU_ITEM_DOC,
    props: {
      menus: {kind: 'value', required: true},
      right: {kind: 'children', doc: 'Items pushed to the right side.'},
      action: {kind: 'action', doc: 'context.menu, context.item.'},
    },
  },
  PieMenu: {
    group: 'Menus',
    doc: 'Radial pie menu (up to 8 items, W E S N NW NE SW SE order) opened by its button or hotkey.',
    props: {
      title: {kind: 'str'},
      items: {kind: 'value', required: true},
      text: {kind: 'str', doc: 'Label of the button that opens the pie.'},
      icon: {kind: 'str'},
      hotkey: {kind: 'str', doc: 'Single key that opens the pie while the surface is hovered, e.g. "Q".'},
      value: {kind: 'str', doc: 'Two-way last picked item.'},
      action: {kind: 'action'},
    },
  },

  // -------------------------------------------------------- color / editors
  ColorRamp: {
    group: 'Editors',
    doc: 'Color ramp: draggable stops over a gradient, with active stop color and position.',
    props: {
      stops: {kind: 'value', required: true, doc: 'Two-way [{pos 0..1, color [r,g,b,a]}].'},
      interpolation: {kind: 'enum', values: ['Linear', 'Ease', 'Constant', 'B-Spline', 'Cardinal']},
      action: {kind: 'action'},
    },
  },
  CurveMapping: {
    group: 'Editors',
    doc: 'Curve widget with draggable points; optional channel tabs (C R G B).',
    props: {
      curves: {kind: 'value', required: true, doc: 'Two-way [{name, color?, points: [[x, y], ...]}].'},
      current: {kind: 'num', doc: 'Two-way active curve index.'},
      height: {kind: 'num', doc: 'Height in UI units (default 8).'},
      action: {kind: 'action'},
    },
  },
  NormalBall: {
    group: 'Editors',
    doc: 'Shaded sphere; drag to set a direction vector.',
    props: {
      label: {kind: 'str'},
      value: {kind: 'value', required: true, doc: 'Two-way [x, y, z] unit vector.'},
      size: {kind: 'num', doc: 'Diameter in UI units (default 4).'},
      action: {kind: 'action'},
    },
  },
  Histogram: {
    group: 'Editors',
    doc: 'Histogram of bins: an array of numbers, or {r, g, b, luma} arrays for an RGB scope.',
    props: {
      bins: {kind: 'value', required: true},
      mode: {kind: 'enum', values: ['luma', 'rgb', 'bars']},
      height: {kind: 'num', doc: 'Height in UI units (default 5).'},
      labels: {kind: 'strList', doc: 'Optional x-axis labels.'},
    },
  },
  Node: {
    group: 'Editors',
    doc: 'A node for a NodeEditor: header colored by kind, output and input sockets colored by type.',
    props: {
      key: {kind: 'str', required: true, doc: 'Node id used by NodeEditor links.'},
      title: {kind: 'str', required: true},
      kind: {kind: 'str', doc: 'input | output | shader | texture | color | vector | converter | geometry | group | script | filter | layout.'},
      inputs: {kind: 'value', doc: '[{name, type, value?}]; a value draws a field while unlinked.'},
      outputs: {kind: 'value', doc: '[{name, type}]'},
      location: {kind: 'value', doc: 'Two-way [x, y] in editor pixels.'},
      width: {kind: 'num', doc: 'Width in UI units (default 7).'},
      collapsed: {kind: 'bool'},
      preview: {kind: 'str', doc: 'Optional preview image URL drawn in the node.'},
      body: {kind: 'child', doc: 'Optional widget drawn between outputs and inputs (e.g. a ColorRamp or CurveMapping).'},
    },
  },
  NodeEditor: {
    group: 'Editors',
    doc: 'Node editor canvas: Node children, links between sockets, pan, box-select, drag-to-link.',
    props: {
      children: {kind: 'children', required: true, doc: 'Node components.'},
      links: {kind: 'value', doc: 'Two-way [{from, out, to, in}] using node keys and socket indices or names.'},
      height: {kind: 'num', doc: 'Height in UI units (default 16).'},
      action: {kind: 'action', doc: 'Fired when the user links or cuts; context.links.'},
    },
  },
};

for (const c of Object.values(COMPONENTS)) {
  for (const [k, v] of Object.entries(COMMON)) if (!(k in c.props)) c.props[k] = v;
}

export const COMPONENT_NAMES = Object.keys(COMPONENTS);
