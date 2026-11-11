/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// Blender icon names -> Material Symbols Rounded glyphs.
//
// BUI ships all of Blender's SVG icons for its native windows; this web demo
// draws the same icon *names* with Material Symbols so the catalog contract
// (Blender icon names like "MESH_CUBE", "HIDE_OFF") stays identical to BUI's.
// Unknown names fall back to a neutral dot.

import {html, nothing} from '../third_party/a2ui_bundle/a2ui.bundle.js';

const MAP = {
  // objects & data
  OBJECT_DATA: 'deployed_code', OBJECT_DATAMODE: 'deployed_code', MESH_DATA: 'change_history',
  MESH_CUBE: 'deployed_code', MESH_UVSPHERE: 'language', MESH_CYLINDER: 'database',
  MESH_PLANE: 'crop_square', MESH_MONKEY: 'pets', MESH_TORUS: 'donut_large', MESH_CONE: 'change_history',
  MESH_ICOSPHERE: 'hexagon', CURVE_DATA: 'gesture', SURFACE_DATA: 'texture',
  LIGHT: 'lightbulb', LIGHT_DATA: 'lightbulb', LIGHT_SUN: 'wb_sunny', LIGHT_POINT: 'emoji_objects',
  LIGHT_SPOT: 'highlight', LIGHT_AREA: 'rectangle', OUTLINER_OB_LIGHT: 'lightbulb',
  CAMERA_DATA: 'videocam', OUTLINER_OB_CAMERA: 'videocam', CAMERA: 'photo_camera',
  OUTLINER_COLLECTION: 'folder_open', COLLECTION_NEW: 'create_new_folder', GROUP: 'workspaces',
  OUTLINER_OB_MESH: 'change_history', OUTLINER_OB_EMPTY: 'control_camera', EMPTY_AXIS: 'control_camera',
  OUTLINER_OB_ARMATURE: 'accessibility_new', ARMATURE_DATA: 'accessibility_new', BONE_DATA: 'linear_scale',
  MATERIAL: 'circle', MATERIAL_DATA: 'circle', TEXTURE: 'texture', TEXTURE_DATA: 'texture',
  IMAGE_DATA: 'image', IMAGE: 'image', IMAGE_RGB: 'image', IMAGE_RGB_ALPHA: 'image',
  WORLD: 'public', WORLD_DATA: 'public', SCENE_DATA: 'category', SCENE: 'category',
  NODETREE: 'account_tree', NODE: 'account_tree', NODE_MATERIAL: 'bubble_chart', GEOMETRY_NODES: 'hub',
  MODIFIER: 'build', MODIFIER_DATA: 'build', CONSTRAINT: 'link', PHYSICS: 'blur_on',
  PARTICLES: 'grain', PARTICLE_DATA: 'grain', FORCE_WIND: 'air', FORCE_FORCE: 'motion_mode',
  OUTPUT: 'print', RENDER_STILL: 'photo_camera', RENDER_ANIMATION: 'movie', RENDER_RESULT: 'image',
  TOOL_SETTINGS: 'handyman', PREFERENCES: 'settings', SETTINGS: 'settings', VIEW3D: 'view_in_ar',
  SHADING_RENDERED: 'circle', SHADING_SOLID: 'radio_button_checked', SHADING_WIRE: 'language',
  SHADING_TEXTURE: 'blur_circular', OVERLAY: 'layers', XRAY: 'filter_b_and_w',
  FONT_DATA: 'text_fields', SPEAKER: 'volume_up', SOUND: 'graphic_eq', MUTE_IPO_OFF: 'volume_up',
  FILE_SOUND: 'audio_file', PLAY_SOUND: 'music_note',
  // editors
  NODE_EDITOR: 'account_tree', SHADER: 'bubble_chart', IMAGE_EDITOR: 'image', UV: 'grid_on',
  SEQUENCE: 'view_timeline', TIME: 'schedule', GRAPH: 'show_chart', ACTION: 'animation',
  TEXT: 'description', CONSOLE: 'terminal', INFO: 'info', PROPERTIES: 'tune', FILEBROWSER: 'folder',
  OUTLINER: 'list', SPREADSHEET: 'table_chart', ASSET_MANAGER: 'inventory_2', CLIP: 'movie_filter',
  // file
  FILE: 'draft', FILE_NEW: 'note_add', FILE_FOLDER: 'folder', FILE_PARENT: 'drive_folder_upload',
  FILE_REFRESH: 'refresh', FILE_BLEND: 'deployed_code', FILE_IMAGE: 'image', FILE_MOVIE: 'movie',
  FILE_TEXT: 'description', FILE_SCRIPT: 'code', FILE_FONT: 'font_download', FILE_3D: 'view_in_ar',
  FILE_ARCHIVE: 'folder_zip', FILE_CACHE: 'cached', FILE_BACKUP: 'history', FILE_TICK: 'task',
  FILEBROWSER_FOLDER: 'folder', FOLDER_REDIRECT: 'folder_special', DISK_DRIVE: 'hard_drive',
  BOOKMARKS: 'bookmarks', RECOVER_LAST: 'history', EXPORT: 'upload', IMPORT: 'download',
  // ui
  ADD: 'add', REMOVE: 'remove', X: 'close', CANCEL: 'close', PANEL_CLOSE: 'close', CHECKMARK: 'check',
  TRASH: 'delete', DUPLICATE: 'content_copy', COPYDOWN: 'content_copy', PASTEDOWN: 'content_paste',
  SEARCH: 'search', VIEWZOOM: 'search', ZOOM_IN: 'zoom_in', ZOOM_OUT: 'zoom_out', FULLSCREEN_ENTER: 'fullscreen',
  FULLSCREEN_EXIT: 'fullscreen_exit', MENU_PANEL: 'menu', COLLAPSEMENU: 'menu', DOWNARROW_HLT: 'arrow_drop_down',
  TRIA_DOWN: 'arrow_drop_down', TRIA_RIGHT: 'arrow_right', TRIA_LEFT: 'arrow_left', TRIA_UP: 'arrow_drop_up',
  DISCLOSURE_TRI_DOWN: 'arrow_drop_down', DISCLOSURE_TRI_RIGHT: 'arrow_right', RIGHTARROW: 'chevron_right',
  BACK: 'arrow_back', FORWARD: 'arrow_forward', LOOP_BACK: 'undo', LOOP_FORWARDS: 'redo',
  HIDE_OFF: 'visibility', HIDE_ON: 'visibility_off', RESTRICT_VIEW_OFF: 'visibility', RESTRICT_VIEW_ON: 'visibility_off',
  RESTRICT_RENDER_OFF: 'photo_camera', RESTRICT_RENDER_ON: 'no_photography', RESTRICT_SELECT_OFF: 'arrow_selector_tool',
  RESTRICT_SELECT_ON: 'block', LOCKED: 'lock', UNLOCKED: 'lock_open', PINNED: 'push_pin', UNPINNED: 'push_pin',
  FAKE_USER_OFF: 'shield', FAKE_USER_ON: 'shield', LINKED: 'link', UNLINKED: 'link_off', LIBRARY_DATA_DIRECT: 'link',
  KEYFRAME: 'diamond', KEYFRAME_HLT: 'diamond', DECORATE: 'circle', DECORATE_KEYFRAME: 'diamond',
  DECORATE_ANIMATE: 'diamond', DECORATE_DRIVER: 'directions_car', DRIVER: 'directions_car',
  PLAY: 'play_arrow', PAUSE: 'pause', PLAY_REVERSE: 'play_arrow', FF: 'fast_forward', REW: 'fast_rewind',
  NEXT_KEYFRAME: 'skip_next', PREV_KEYFRAME: 'skip_previous', REC: 'fiber_manual_record',
  INFO_LARGE: 'info', ERROR: 'error', CANCEL_LARGE: 'cancel', QUESTION: 'help', HELP: 'help',
  WARNING: 'warning', CHECKBOX_HLT: 'check_box', CHECKBOX_DEHLT: 'check_box_outline_blank',
  SORTALPHA: 'sort_by_alpha', SORTTIME: 'schedule', SORTSIZE: 'sort', FILTER: 'filter_alt',
  THREE_DOTS: 'more_horiz', GRIP: 'drag_indicator', OPTIONS: 'more_vert', EYEDROPPER: 'colorize',
  COLOR: 'palette', COLOR_RED: 'circle', COLOR_GREEN: 'circle', COLOR_BLUE: 'circle', BRUSH_DATA: 'brush',
  RESTRICT_COLOR_ON: 'palette', SNAP_ON: 'grid_on', SNAP_OFF: 'grid_off', PROP_ON: 'adjust',
  ORIENTATION_GLOBAL: 'public', ORIENTATION_LOCAL: 'my_location', PIVOT_BOUNDBOX: 'crop_free',
  TRANSFORM_ORIGINS: 'center_focus_strong', OBJECT_ORIGIN: 'adjust', CURSOR: 'my_location',
  ORIENTATION_CURSOR: 'my_location', ARROW_LEFTRIGHT: 'swap_horiz', HAND: 'pan_tool', MOUSE_LMB: 'mouse',
  EDITMODE_HLT: 'edit', SCULPTMODE_HLT: 'brush', WPAINT_HLT: 'format_paint', VPAINT_HLT: 'format_color_fill',
  TPAINT_HLT: 'imagesearch_roller', POSE_HLT: 'accessibility_new', PARTICLEMODE: 'grain',
  VERTEXSEL: 'scatter_plot', EDGESEL: 'timeline', FACESEL: 'square',
  UV_SYNC_SELECT: 'sync', WORKSPACE: 'dashboard', WINDOW: 'web_asset', SCREEN_BACK: 'arrow_back',
  BLENDER: 'circle', URL: 'link', HOME: 'home', USER: 'person', COMMUNITY: 'groups',
  TIME_CLOCK: 'schedule', PREVIEW_RANGE: 'date_range', STATUSBAR: 'bottom_navigation',
  EXPERIMENTAL: 'science', SYSTEM: 'memory', MEMORY: 'memory', NETWORK_DRIVE: 'lan',
  SEQ_HISTOGRAM: 'bar_chart', SEQ_LUMA_WAVEFORM: 'show_chart', SEQ_CHROMA_SCOPE: 'donut_small',
  NORMALIZE_FCURVES: 'show_chart', IPO_EASE_IN_OUT: 'timeline', IPO_LINEAR: 'trending_up',
  IPO_CONSTANT: 'horizontal_rule', IPO_BEZIER: 'gesture', SMOOTHCURVE: 'gesture', SPHERECURVE: 'circle',
  LINCURVE: 'trending_up', SHARPCURVE: 'change_history', ROOTCURVE: 'gesture', NOCURVE: 'horizontal_rule',
  MOD_SUBSURF: 'blur_circular', MOD_BEVEL: 'rounded_corner', MOD_ARRAY: 'view_module', MOD_MIRROR: 'flip',
  MOD_SOLIDIFY: 'layers', MOD_BOOLEAN: 'join', MOD_SMOOTH: 'water', MOD_WAVE: 'waves', MOD_NOISE: 'grain',
  MOD_DISPLACE: 'terrain', MOD_REMESH: 'grid_4x4', MOD_DECIM: 'filter_center_focus', MOD_CLOTH: 'checkroom',
  MOD_FLUIDSIM: 'water_drop', MOD_OCEAN: 'waves', MOD_SCREW: 'rotate_right', MOD_LATTICE: 'grid_on',
  MOD_TIME: 'schedule', MOD_PHYSICS: 'blur_on', MOD_PARTICLES: 'grain', SHADERFX: 'auto_awesome',
  OUTLINER_DATA_GP_LAYER: 'layers', GREASEPENCIL: 'draw', STROKE: 'draw', OUTLINER_OB_GREASEPENCIL: 'draw',
  RENDERLAYERS: 'layers', LAYER_ACTIVE: 'radio_button_checked', LAYER_USED: 'radio_button_unchecked',
  EVENT_CTRL: 'keyboard_control_key', EVENT_SHIFT: 'shift', EVENT_ALT: 'keyboard_option_key', KEYINGSET: 'key',
  // generic non-Blender helpers for app-style showcases
  BOOKMARK: 'bookmark', STAR: 'star', HEART: 'favorite', CLOUD: 'cloud', SUN: 'wb_sunny', MOON: 'dark_mode',
  RAIN: 'rainy', SNOW: 'ac_unit', THERMOMETER: 'thermostat', WIND: 'air', HUMIDITY: 'humidity_percentage',
  CHART: 'bar_chart', MONEY: 'payments', CART: 'shopping_cart', MAIL: 'mail', CALENDAR: 'calendar_month',
  PHONE: 'call', MAP: 'map', PIN: 'location_on', ROCKET: 'rocket_launch', BUG: 'bug_report',
  BRANCH: 'call_split', COMMIT: 'commit', SERVER: 'dns', DATABASE: 'database', CPU: 'memory',
  GPU: 'developer_board', BATTERY: 'battery_full', WIFI: 'wifi', BLUETOOTH: 'bluetooth', DRONE: 'flight',
  CAR: 'directions_car', BOLT: 'bolt', PLUG: 'power', HOUSE: 'home', DOOR: 'door_front', SOFA: 'chair',
  KITCHEN: 'kitchen', BED: 'bed', TV: 'tv', SPEAKER_GROUP: 'speaker_group', MIC: 'mic', HEADPHONES: 'headphones',
  WAVE: 'graphic_eq', PIANO: 'piano', TUNE: 'tune', FLASK: 'science', ATOM: 'atom', LEAF: 'eco',
  WATER: 'water_drop', FIRE: 'local_fire_department', SHIELD: 'shield', KEY: 'key', PERSON: 'person',
  TEAM: 'group', CHAT: 'chat', TASK: 'task_alt', FLAG: 'flag', TAG: 'sell', CLOCK: 'schedule',
  TIMER: 'timer', SPEED: 'speed', ROUTE: 'route', GAME: 'sports_esports', SWORD: 'swords', POTION: 'science',
  // views group (list / outliner / file browser)
  LONGDISPLAY: 'view_list', SHORTDISPLAY: 'view_headline', IMGDISPLAY: 'grid_view', NEWFOLDER: 'create_new_folder',
  SORT_ASC: 'arrow_upward', SORT_DESC: 'arrow_downward', FILE_HIDDEN: 'visibility_off', FILE_VOLUME: 'deployed_code',
  OUTLINER_OB_CURVE: 'gesture', OUTLINER_OB_FONT: 'title', OUTLINER_OB_LIGHTPROBE: 'radar',
  OUTLINER_OB_VOLUME: 'cloud', OUTLINER_OB_POINTCLOUD: 'scatter_plot', OUTLINER_DATA_MESH: 'change_history',
  OUTLINER_DATA_LIGHT: 'lightbulb', OUTLINER_DATA_CAMERA: 'videocam', OUTLINER_DATA_CURVE: 'gesture',
  OUTLINER_DATA_EMPTY: 'control_camera', OUTLINER_DATA_ARMATURE: 'accessibility_new', DESKTOP: 'desktop_windows',
  GROUP_UVS: 'texture', GROUP_VCOL: 'palette', GROUP_VERTEX: 'scatter_plot',
  // showcases (snap targets, text editor toggles, mouse hints, misc)
  ORPHAN_DATA: 'link_off', APPEND_BLEND: 'add_link', QUIT: 'power_settings_new', PLUGIN: 'extension', PRESET: 'tune',
  SNAP_INCREMENT: 'grid_on', SNAP_VERTEX: 'scatter_plot', SNAP_EDGE: 'timeline', SNAP_FACE: 'square',
  SNAP_VOLUME: 'deployed_code', PROP_OFF: 'adjust', MOUSE_MMB: 'mouse', MOUSE_RMB: 'mouse',
  LINENUMBERS_OFF: 'format_list_numbered', LINENUMBERS_ON: 'format_list_numbered', WORDWRAP_OFF: 'wrap_text',
  WORDWRAP_ON: 'wrap_text', SYNTAX_OFF: 'code', SYNTAX_ON: 'code', SPLIT: 'vertical_split',
};

const COLORED = {COLOR_RED: '#e05252', COLOR_GREEN: '#5bb85b', COLOR_BLUE: '#5285e0'};
const FILLED = new Set(['KEYFRAME_HLT', 'DECORATE_KEYFRAME', 'FAKE_USER_ON', 'PINNED', 'REC', 'LAYER_ACTIVE',
  'STAR', 'HEART', 'MATERIAL', 'MATERIAL_DATA', 'COLOR_RED', 'COLOR_GREEN', 'COLOR_BLUE', 'SHADING_RENDERED']);

export function iconGlyph(name) {
  if (!name) return '';
  const key = String(name).toUpperCase();
  if (MAP[key]) return MAP[key];
  if (/^[a-z_]+$/.test(name)) return name;  // already a Material Symbols ligature
  return 'radio_button_unchecked';
}

/** <span class="bui-icon"> for a Blender icon name (nothing when empty). */
export function icon(name, cls = '') {
  if (!name) return nothing;
  const key = String(name).toUpperCase();
  const style = [COLORED[key] ? `color:${COLORED[key]}` : '', FILLED.has(key) ? `font-variation-settings:'FILL' 1` : '']
                    .filter(Boolean).join(';');
  return html`<span class="bui-icon ${cls}" style=${style} aria-hidden="true">${iconGlyph(name)}</span>`;
}

export const ICON_NAMES = Object.keys(MAP);
