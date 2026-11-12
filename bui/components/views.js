/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Views: ListView (Blender UIList), TreeView (Outliner), GridView (preview
// tiles), FileBrowser (Blender File Browser).
//
// Every view keeps purely visual state (scroll, expansion, history, sort,
// inline rename) locally and writes data edits through this.set() so a bound
// `items` / `selected` / `path` goes back to the data model.

import {BuiElement, clamp, cssColor, drag, html, impl, nothing, normItems, popup, toRgba, unitPx} from '../base.js';
import {icon} from '../icons.js';
import {menuList} from './menu_list.js';

const clone = (v) => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

/** Small Blender IconButton (emboss off unless `emboss`). */
function iconBtn(name, onClick, {tip = '', emboss = true, pressed = false, disabled = false, cls = ''} = {}) {
  return html`<button class="bui-w bui-center bui-vw-ibtn ${emboss ? '' : 'bui-noemboss'} ${pressed ? 'bui-sel' : ''} ${
      disabled ? 'bui-disabled' : ''} ${cls}" data-tip=${tip} aria-label=${tip} aria-pressed=${pressed ? 'true' : 'false'}
      @click=${(e) => {
        e.stopPropagation();
        onClick(e);
      }}>${icon(name)}</button>`;
}

/** Inline text field used by every view for double-click / F2 renames. */
function renameField(value, onCommit, onCancel) {
  let done = false;
  const finish = (e, ok) => {
    if (done) return;
    done = true;
    ok ? onCommit(e.target.value) : onCancel();
  };
  return html`<input class="bui-input bui-vw-edit" .value=${value}
      @pointerdown=${(e) => e.stopPropagation()} @click=${(e) => e.stopPropagation()}
      @dblclick=${(e) => e.stopPropagation()}
      @keydown=${(e) => {
        e.stopPropagation();
        if (e.key === 'Enter') finish(e, true);
        else if (e.key === 'Escape') finish(e, false);
      }}
      @blur=${(e) => finish(e, true)}>`;
}

/** Focuses + selects a freshly rendered rename field inside `host`. */
function focusEdit(host) {
  const inp = host.querySelector('.bui-vw-edit');
  if (inp && document.activeElement !== inp) {
    inp.focus();
    inp.select();
  }
}

// ===================================================================== ListView

class ListViewElement extends BuiElement {
  constructor() {
    super();
    this._editing = -1;
    this._query = '';
    this._sortAlpha = false;
    this._reverse = false;
    this._rowsOverride = null;
    this._showFilter = null;
  }

  get rawItems() {
    const v = this.val('items', []);
    return Array.isArray(v) ? v : [];
  }

  /** Visible rows: [{it, index}] after filter / sort. */
  visible(items) {
    let out = items.map((it, index) => ({it, index}));
    const q = this._query.trim().toLowerCase();
    if (q) out = out.filter(({it}) => it.label.toLowerCase().includes(q) || String(it.meta ?? '').toLowerCase().includes(q));
    if (this._sortAlpha) out.sort((a, b) => a.it.label.localeCompare(b.it.label, undefined, {numeric: true}));
    if (this._reverse) out.reverse();
    return out;
  }

  get sel() {
    const n = Number(this.val('selected', 0));
    return Number.isFinite(n) ? Math.round(n) : 0;
  }

  select(index, items) {
    if (index < 0 || index >= items.length) return;
    this.set('selected', index);
    this.fire({op: 'select', index, item: items[index].label});
    this.updateComplete.then(() => this.querySelector(`.bui-lv-row[data-i="${index}"]`)?.scrollIntoView({block: 'nearest'}));
  }

  writeItems(next) {
    this.set('items', next);
  }

  rename(index, label) {
    this._editing = -1;
    const raw = this.rawItems;
    const old = raw[index];
    const oldLabel = normItems([old])[0]?.label ?? '';
    label = String(label).trim();
    if (!label || label === oldLabel) return this.requestUpdate();
    const next = raw.slice();
    if (old && typeof old === 'object') {
      const key = old.label != null ? 'label' : old.name != null ? 'name' : 'label';
      next[index] = {...old, [key]: label};
    } else {
      next[index] = label;
    }
    this.writeItems(next);
    this.fire({op: 'rename', index, item: oldLabel, label});
  }

  toggleCheck(index) {
    const raw = this.rawItems;
    const o = raw[index];
    const next = raw.slice();
    const on = !(o && typeof o === 'object' && o.checked);
    next[index] = o && typeof o === 'object' ? {...o, checked: on} : {label: String(o), checked: on};
    this.writeItems(next);
    this.fire({op: 'check', index, item: normItems([o])[0].label, checked: on});
  }

  add() {
    const raw = this.rawItems;
    const items = normItems(raw);
    const base = 'Item';
    let n = raw.length + 1;
    const names = new Set(items.map((i) => i.label));
    let label = `${base}.${String(n).padStart(3, '0')}`;
    while (names.has(label)) label = `${base}.${String(++n).padStart(3, '0')}`;
    const tmpl = raw[this.sel];
    let item = label;
    if (tmpl && typeof tmpl === 'object') {
      item = {label};
      if (tmpl.icon) item.icon = tmpl.icon;
      if ('checked' in tmpl) item.checked = true;
    }
    const at = Math.min(raw.length, this.sel + 1);
    const next = raw.slice();
    next.splice(at, 0, item);
    this.writeItems(next);
    this.set('selected', at);
    this.fire({op: 'add', index: at, item: label});
  }

  remove() {
    const raw = this.rawItems;
    const i = this.sel;
    if (i < 0 || i >= raw.length) return;
    const label = normItems([raw[i]])[0].label;
    const next = raw.slice();
    next.splice(i, 1);
    this.writeItems(next);
    this.set('selected', clamp(i - (i >= next.length ? 1 : 0), 0, Math.max(0, next.length - 1)));
    this.fire({op: 'remove', index: i, item: label});
  }

  move(dir) {
    const raw = this.rawItems;
    const i = this.sel, j = i + dir;
    if (i < 0 || j < 0 || j >= raw.length) return;
    const next = raw.slice();
    [next[i], next[j]] = [next[j], next[i]];
    this.writeItems(next);
    this.set('selected', j);
    this.fire({op: 'move', index: i, to: j, item: normItems([raw[i]])[0].label});
  }

  specials(e) {
    const anchor = e.currentTarget;
    popup(anchor, (box, close) => menuList(box, {
      title: 'Specials',
      search: false,
      items: [
        {label: 'Sort by Name', icon: 'SORTALPHA', value: 'sort', checked: this._sortAlpha},
        {label: 'Reverse Order', icon: 'ARROW_LEFTRIGHT', value: 'reverse', checked: this._reverse},
        {separator: true},
        {label: 'Duplicate', icon: 'DUPLICATE', value: 'duplicate', shortcut: 'Shift D'},
        {label: 'Rename', value: 'rename', shortcut: 'F2'},
        {separator: true},
        {label: 'Remove All', icon: 'X', value: 'clear'},
      ],
      onPick: (it) => {
        close();
        const v = it.value;
        if (v === 'sort') this._sortAlpha = !this._sortAlpha;
        else if (v === 'reverse') this._reverse = !this._reverse;
        else if (v === 'rename') this._editing = this.sel;
        else if (v === 'duplicate') {
          const raw = this.rawItems;
          const o = raw[this.sel];
          if (o === undefined) return;
          const lbl = normItems([o])[0].label + '.001';
          const next = raw.slice();
          next.splice(this.sel + 1, 0, typeof o === 'object' ? {...clone(o), label: lbl} : lbl);
          this.writeItems(next);
          this.set('selected', this.sel + 1);
          this.fire({op: 'add', index: this.sel, item: lbl});
        } else if (v === 'clear') {
          this.writeItems([]);
          this.set('selected', 0);
          this.fire({op: 'clear'});
        }
        this.requestUpdate();
      },
    }), {placement: 'below'});
  }

  onKey(e, items, vis) {
    if (this._editing >= 0) return;
    const pos = vis.findIndex((r) => r.index === this.sel);
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const np = clamp((pos < 0 ? -1 : pos) + (e.key === 'ArrowDown' ? 1 : -1), 0, vis.length - 1);
      if (e.altKey) this.move(e.key === 'ArrowDown' ? 1 : -1);
      else if (vis[np]) this.select(vis[np].index, items);
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault();
      const r = e.key === 'Home' ? vis[0] : vis[vis.length - 1];
      if (r) this.select(r.index, items);
    } else if (e.key === 'F2' || (e.key === 'Enter' && e.ctrlKey)) {
      e.preventDefault();
      if (this.sel >= 0 && this.sel < items.length) {
        this._editing = this.sel;
        this.requestUpdate();
      }
    } else if (e.key === 'Delete' || e.key === 'x' && e.ctrlKey) {
      e.preventDefault();
      this.remove();
    } else if (e.key === ' ' && items[this.sel] && 'checked' in items[this.sel]) {
      e.preventDefault();
      this.toggleCheck(this.sel);
    }
  }

  grip(e) {
    e.preventDefault();
    const u = unitPx(this);
    const start = this._rowsOverride ?? this.rowsProp;
    drag(e, {
      onMove: (dx, dy) => {
        this._rowsOverride = clamp(Math.round(start + dy / u), 1, 60);
        this.requestUpdate();
      },
    });
  }

  get rowsProp() {
    return clamp(Math.round(Number(this.p.rows) || 5), 1, 60);
  }

  updated(c) {
    super.updated?.(c);
    if (this._editing >= 0) focusEdit(this);
  }

  render() {
    const items = normItems(this.rawItems, this.p.icons);
    const vis = this.visible(items);
    const rows = this._rowsOverride ?? this.rowsProp;
    const sel = this.sel;
    const showFilter = this._showFilter ?? !!this.p.filter;
    const hasChecks = items.some((it) => 'checked' in it);
    return html`<div class="bui-lv ${this.enabled ? '' : 'bui-disabled'}">
      <div class="bui-lv-main">
        <div class="bui-lv-box" tabindex="0" role="listbox" aria-activedescendant=${`r${sel}`}
            style="height: calc(var(--bui-u) * ${rows} + 2px)"
            @keydown=${(e) => this.onKey(e, items, vis)}>
          ${vis.map(({it, index}, row) => {
            const active = index === sel;
            const editing = index === this._editing;
            return html`<div class="bui-lv-row ${active ? 'bui-active' : ''} ${row % 2 ? 'bui-alt' : ''}"
                role="option" aria-selected=${active} data-i=${index} id=${`r${index}`} data-tip=${it.description || nothing}
                @click=${() => this.select(index, items)}
                @dblclick=${() => {
                  this._editing = index;
                  this.requestUpdate();
                }}>
              ${it.icon ? icon(it.icon) : nothing}
              ${editing ? html`<span class="bui-lv-editbox">${renameField(it.label, (v) => this.rename(index, v), () => {
                this._editing = -1;
                this.requestUpdate();
              })}</span>` : html`<span class="bui-txt">${it.label}</span>`}
              ${it.meta != null && !editing ? html`<span class="bui-lv-meta">${it.meta}</span>` : nothing}
              ${'checked' in it ? html`<span class="bui-lv-check ${it.checked ? 'on' : ''}" role="checkbox"
                  aria-checked=${!!it.checked} @click=${(e) => {
                    e.stopPropagation();
                    this.toggleCheck(index);
                  }} @dblclick=${(e) => e.stopPropagation()}>${it.checked ? icon('CHECKMARK') : nothing}</span>` :
                  hasChecks ? html`<span class="bui-lv-check-blank"></span>` : nothing}
            </div>`;
          })}
          ${vis.length === 0 ? html`<div class="bui-lv-empty">${this._query ? 'No matches' : ''}</div>` : nothing}
        </div>
        <div class="bui-lv-foot">
          <button class="bui-lv-foot-tri" aria-label="Filter options" data-tip="Filter options"
              @click=${() => {
                this._showFilter = !showFilter;
                this.requestUpdate();
              }}>${icon(showFilter ? 'DISCLOSURE_TRI_DOWN' : 'DISCLOSURE_TRI_RIGHT')}</button>
          <div class="bui-lv-grip" @pointerdown=${(e) => this.grip(e)} data-tip="Drag to resize the list">
            <span></span><span></span><span></span><span></span><span></span>
          </div>
        </div>
        ${showFilter ? html`<div class="bui-lv-filter bui-joined-h">
          <label class="bui-w bui-lv-search">${icon('VIEWZOOM')}<input class="bui-input" placeholder="Filter"
              .value=${this._query} @input=${(e) => {
                this._query = e.target.value;
                this.requestUpdate();
              }} @keydown=${(e) => {
                if (e.key === 'Escape') {
                  this._query = '';
                  e.target.value = '';
                  this.requestUpdate();
                }
              }}></label>
          ${iconBtn('SORTALPHA', () => {
            this._sortAlpha = !this._sortAlpha;
            this.requestUpdate();
          }, {tip: 'Sort items by their name', pressed: this._sortAlpha})}
          ${iconBtn(this._reverse ? 'SORT_DESC' : 'SORT_ASC', () => {
            this._reverse = !this._reverse;
            this.requestUpdate();
          }, {tip: 'Reverse the order of shown items', pressed: this._reverse})}
        </div>` : nothing}
      </div>
      ${!(this.raw('action') || this.isBound('items')) ? nothing : html`<div class="bui-lv-side">
        <div class="bui-joined-v">
          ${iconBtn('ADD', () => this.add(), {tip: 'Add a new item'})}
          ${iconBtn('REMOVE', () => this.remove(), {tip: 'Remove the active item', disabled: !items.length})}
        </div>
        ${iconBtn('DOWNARROW_HLT', (e) => this.specials(e), {tip: 'Specials', emboss: false, cls: 'bui-lv-specials'})}
        <div class="bui-joined-v">
          ${iconBtn('TRIA_UP', () => this.move(-1), {tip: 'Move the active item up', disabled: sel <= 0})}
          ${iconBtn('TRIA_DOWN', () => this.move(1), {tip: 'Move the active item down', disabled: sel >= items.length - 1})}
        </div>
      </div>`}
    </div>`;
  }
}

// ===================================================================== TreeView

const COLUMN_ICONS = {
  select: ['RESTRICT_SELECT_OFF', 'RESTRICT_SELECT_ON', 'Disable selection in viewport'],
  hide: ['HIDE_OFF', 'HIDE_ON', 'Hide in viewport (H)'],
  viewport: ['RESTRICT_VIEW_OFF', 'RESTRICT_VIEW_ON', 'Globally disable in viewports'],
  render: ['RESTRICT_RENDER_OFF', 'RESTRICT_RENDER_ON', 'Globally disable in renders'],
};

class TreeViewElement extends BuiElement {
  constructor() {
    super();
    this._open = new Map();     // key -> expanded
    this._editing = null;       // key
    this._pending = null;       // working copy during a toggle drag
  }

  get rawItems() {
    const v = this._pending ?? this.val('items', []);
    return Array.isArray(v) ? v : [];
  }

  keyOf(it, path) {
    return it && typeof it === 'object' && it.id != null ? String(it.id) : path.join('/');
  }

  refOf(it) {
    return it && typeof it === 'object' ? String(it.id ?? it.label ?? it.name ?? '') : String(it);
  }

  isOpen(key, it) {
    if (this._open.has(key)) return this._open.get(key);
    return it.expanded !== false;
  }

  /** Flattens visible rows with tree-guide info. */
  flatten() {
    const rows = [];
    const walk = (list, depth, path, guides, offAnc) => {
      list.forEach((raw, i) => {
        const it = raw && typeof raw === 'object' ? raw : {label: String(raw)};
        const p = [...path, i];
        const key = this.keyOf(it, p);
        const kids = Array.isArray(it.children) ? it.children : [];
        const last = i === list.length - 1;
        const open = kids.length > 0 && this.isOpen(key, it);
        rows.push({it, raw, key, path: p, depth, kids: kids.length, open, last, guides, offAnc,
          label: String(it.label ?? it.name ?? '')});
        if (open) {
          const off = {...offAnc};
          for (const [c, v] of Object.entries(it.toggles || {})) if (v === false) off[c] = true;
          walk(kids, depth + 1, p, [...guides, !last], off);
        }
      });
    };
    walk(this.rawItems, 0, [], [], {});
    return rows;
  }

  get selKey() {
    return String(this.val('selected', '') ?? '');
  }

  isSel(row) {
    const s = this.selKey;
    return !!s && (s === row.key || s === String(row.it.id ?? '') || (row.it.id == null && s === row.label));
  }

  select(row) {
    const ref = row.it.id != null ? String(row.it.id) : row.label;
    this.set('selected', ref);
    this.fire({op: 'select', item: ref});
    this.updateComplete.then(() => this.querySelector(`.bui-tv-row[data-k="${CSS.escape(row.key)}"]`)?.scrollIntoView({block: 'nearest'}));
  }

  setOpen(row, open, recursive = false) {
    const visit = (it, path) => {
      this._open.set(this.keyOf(it, path), open);
      if (recursive) (it.children || []).forEach((c, i) => c && typeof c === 'object' && visit(c, [...path, i]));
    };
    visit(row.it, row.path);
    this.requestUpdate();
  }

  /** Returns the node at `path` inside `items` (a deep copy). */
  nodeAt(items, path) {
    let list = items, node;
    for (const i of path) {
      node = list[i];
      if (node && typeof node !== 'object') node = list[i] = {label: String(node)};
      list = node?.children || [];
    }
    return node;
  }

  /** Toggle press: flips the cell, then dragging down/up the column sets others. */
  togglePress(e, row, col) {
    if (!this.enabled) return;
    e.preventDefault();
    e.stopPropagation();
    const work = clone(this.val('items', []));
    const cur = row.it.toggles?.[col] !== false;
    const on = !cur;
    const touched = new Map();
    const apply = (r) => {
      const n = this.nodeAt(work, r.path);
      if (!n) return;
      n.toggles = {...(n.toggles || {}), [col]: on};
      touched.set(r.key, r);
      this._pending = work;
      this.requestUpdate();
    };
    apply(row);
    const move = (ev) => {
      const cell = document.elementFromPoint(ev.clientX, ev.clientY)?.closest?.('.bui-tv-tog');
      if (!cell || !this.contains(cell) || cell.dataset.col !== col) return;
      const k = cell.closest('.bui-tv-row')?.dataset.k;
      if (k == null || touched.has(k)) return;
      const r = this.flatten().find((x) => x.key === k);
      if (r) apply(r);
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
      this._pending = null;
      this.set('items', work);
      for (const r of touched.values()) this.fire({op: 'toggle', item: this.refOf(r.it), column: col, on});
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
  }

  rename(row, label) {
    this._editing = null;
    label = String(label).trim();
    if (!label || label === row.label) return this.requestUpdate();
    const work = clone(this.val('items', []));
    const n = this.nodeAt(work, row.path);
    if (!n) return;
    n[n.label == null && n.name != null ? 'name' : 'label'] = label;
    this.set('items', work);
    if (row.it.id == null && this.isSel(row)) this.set('selected', label);
    this.fire({op: 'rename', item: this.refOf(row.it), label});
  }

  onKey(e, rows) {
    if (this._editing != null) return;
    let i = rows.findIndex((r) => this.isSel(r));
    const row = rows[i];
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      i = clamp(i + (e.key === 'ArrowDown' ? 1 : -1), 0, rows.length - 1);
      if (rows[i]) this.select(rows[i]);
    } else if (e.key === 'ArrowRight' && row) {
      e.preventDefault();
      if (row.kids && !row.open) this.setOpen(row, true, e.shiftKey);
      else if (row.kids) this.select(rows[i + 1]);
    } else if (e.key === 'ArrowLeft' && row) {
      e.preventDefault();
      if (row.kids && row.open) this.setOpen(row, false, e.shiftKey);
      else if (row.depth > 0) {
        const parent = rows.slice(0, i).reverse().find((r) => r.depth === row.depth - 1);
        if (parent) this.select(parent);
      }
    } else if ((e.key === 'F2' || e.key === 'Enter' && e.ctrlKey) && row) {
      e.preventDefault();
      this._editing = row.key;
      this.requestUpdate();
    } else if ((e.key === '+' || e.key === '-') && row?.kids) {
      this.setOpen(row, e.key === '+', true);
    } else if (e.key === 'h' && row && (this.p.columns || []).includes('hide')) {
      const work = clone(this.val('items', []));
      const n = this.nodeAt(work, row.path);
      const on = !(row.it.toggles?.hide !== false);
      n.toggles = {...(n.toggles || {}), hide: on};
      this.set('items', work);
      this.fire({op: 'toggle', item: this.refOf(row.it), column: 'hide', on});
    }
  }

  updated(c) {
    super.updated?.(c);
    if (this._editing != null) focusEdit(this);
  }

  renderGuides(row) {
    // One cell per ancestor level: a full line when that ancestor has more
    // children below, nothing otherwise; the own level draws an elbow.
    const cells = [];
    for (let l = 0; l < row.depth; l++) {
      const own = l === row.depth - 1;
      let cls = '';
      if (own) cls = row.last ? 'bui-tv-g-end' : 'bui-tv-g-mid';
      else if (row.guides[l + 1]) cls = 'bui-tv-g-line';
      cells.push(html`<span class="bui-tv-g ${cls}"></span>`);
    }
    return cells;
  }

  render() {
    const rows = this.flatten();
    const cols = (Array.isArray(this.p.columns) ? this.p.columns : []).filter((c) => COLUMN_ICONS[c]);
    const maxRows = Number(this.p.rows);
    const style = maxRows > 0 ? `max-height: calc(var(--bui-u) * ${maxRows} + 2px)` : '';
    return html`<div class="bui-tv ${this.enabled ? '' : 'bui-disabled'}" tabindex="0" role="tree" style=${style}
        @keydown=${(e) => this.onKey(e, rows)}>
      ${rows.map((row, ri) => {
        const sel = this.isSel(row);
        const editing = this._editing === row.key;
        const it = row.it;
        const ico = it.icon || (row.kids ? 'OUTLINER_COLLECTION' : '');
        const anyOff = cols.some((c) => it.toggles?.[c] === false && (c === 'hide' || c === 'viewport'));
        return html`<div class="bui-tv-row ${sel ? 'bui-active' : ''} ${ri % 2 ? 'bui-alt' : ''} ${anyOff ? 'bui-tv-off' : ''}"
            role="treeitem" aria-level=${row.depth + 1} aria-expanded=${row.kids ? String(row.open) : nothing}
            aria-selected=${sel} data-k=${row.key} data-tip=${it.description || nothing}
            @click=${() => this.select(row)}
            @dblclick=${(e) => {
              if (e.target.closest('.bui-tv-tri, .bui-tv-tog')) return;
              this._editing = row.key;
              this.requestUpdate();
            }}>
          <span class="bui-tv-guides">${this.renderGuides(row)}</span>
          ${row.kids ? html`<span class="bui-tv-tri" @click=${(e) => {
            e.stopPropagation();
            this.setOpen(row, !row.open, e.shiftKey);
          }} @dblclick=${(e) => e.stopPropagation()}>${icon(row.open ? 'DISCLOSURE_TRI_DOWN' : 'DISCLOSURE_TRI_RIGHT')}</span>` :
              html`<span class="bui-tv-tri bui-tv-tri-none"></span>`}
          ${ico ? html`<span class="bui-tv-ico">${icon(ico)}</span>` : nothing}
          ${editing ? html`<span class="bui-tv-editbox">${renameField(row.label, (v) => this.rename(row, v), () => {
            this._editing = null;
            this.requestUpdate();
          })}</span>` : html`<span class="bui-txt">${row.label}</span>`}
          ${it.meta != null && !editing ? html`<span class="bui-tv-meta">${it.meta}</span>` : nothing}
          ${cols.length ? html`<span class="bui-tv-cols">${cols.map((c) => {
            const on = it.toggles?.[c] !== false;
            const [onIco, offIco, tip] = COLUMN_ICONS[c];
            return html`<span class="bui-tv-tog ${on ? 'on' : 'off'} ${row.offAnc[c] ? 'bui-tv-inh' : ''}" data-col=${c}
                data-tip=${tip} role="switch" aria-checked=${on} aria-label=${c}
                @pointerdown=${(e) => this.togglePress(e, row, c)} @click=${(e) => e.stopPropagation()}
                @dblclick=${(e) => e.stopPropagation()}>${icon(on ? onIco : offIco)}</span>`;
          })}</span>` : nothing}
        </div>`;
      })}
    </div>`;
  }
}

// ===================================================================== GridView

/** Preview art for a tile: material ball for colors, image, or big icon. */
function previewArt(t, {ball = true} = {}) {
  if (t.image) return html`<img class="bui-gv-img" src=${t.image} alt="" draggable="false">`;
  if (t.color != null) {
    const c = cssColor(t.color);
    if (!ball) return html`<span class="bui-gv-flat" style="background:${c}"></span>`;
    const [r, g, b] = toRgba(t.color);
    const mix = (k, w) => `rgb(${[r, g, b].map((x) => Math.round(clamp(x * (1 - w) + k * w, 0, 1) * 255)).join(',')})`;
    const style = `background: radial-gradient(circle at 34% 30%, ${mix(1, .75)} 0%, ${mix(1, .25)} 14%, ${c} 42%, ${
        mix(0, .55)} 82%, ${mix(0, .8)} 100%)`;
    return html`<span class="bui-gv-ball" style=${style}></span>`;
  }
  return html`<span class="bui-gv-bigicon">${icon(t.icon || 'MATERIAL')}</span>`;
}

class GridViewElement extends BuiElement {
  get tiles() {
    return normItems(this.val('tiles', []));
  }

  select(t, i) {
    this.set('selected', t.label);
    this.fire({op: 'select', label: t.label, index: i});
  }

  onKey(e, tiles) {
    const keys = {ArrowRight: 1, ArrowLeft: -1, ArrowDown: 'down', ArrowUp: 'up'};
    if (!(e.key in keys) && e.key !== 'Enter') return;
    e.preventDefault();
    let i = tiles.findIndex((t) => t.label === this.val('selected', ''));
    if (e.key === 'Enter') {
      if (tiles[i]) this.fire({op: 'activate', label: tiles[i].label, index: i});
      return;
    }
    const cells = [...this.querySelectorAll('.bui-gv-tile')];
    let per = 1;
    if (cells.length > 1) {
      const top = cells[0].offsetTop;
      per = cells.findIndex((c) => c.offsetTop !== top);
      if (per <= 0) per = cells.length;
    }
    const d = keys[e.key];
    i = i < 0 ? 0 : clamp(i + (d === 'down' ? per : d === 'up' ? -per : d), 0, tiles.length - 1);
    if (tiles[i]) {
      this.select(tiles[i], i);
      this.updateComplete.then(() => this.querySelectorAll('.bui-gv-tile')[i]?.scrollIntoView({block: 'nearest'}));
    }
  }

  render() {
    const tiles = this.tiles;
    const size = clamp(Number(this.p.tile) || 4, 1.5, 20);
    const sel = this.val('selected', '');
    return html`<div class="bui-gv ${this.enabled ? '' : 'bui-disabled'}" tabindex="0" role="listbox"
        style="--gv-tile: calc(var(--bui-u) * ${size})" @keydown=${(e) => this.onKey(e, tiles)}>
      ${tiles.map((t, i) => html`<div class="bui-gv-tile ${t.label === sel ? 'bui-active' : ''}" role="option"
          aria-selected=${t.label === sel} data-tip=${t.description || t.label}
          @click=${() => this.select(t, i)} @dblclick=${() => this.fire({op: 'activate', label: t.label, index: i})}>
        <span class="bui-gv-prev ${t.color != null && !t.image ? 'bui-gv-checker' : ''}">${previewArt(t)}</span>
        <span class="bui-gv-label">${t.label}</span>
      </div>`)}
    </div>`;
  }
}

// ===================================================================== FileBrowser

const EXT_ICON = [
  [/\.blend\d*$/i, 'FILE_BLEND'],
  [/\.(png|jpe?g|exr|hdr|tiff?|tga|bmp|webp|gif|psd|dds|svg|avif)$/i, 'FILE_IMAGE'],
  [/\.(mp4|mov|avi|mkv|webm|mpe?g|m4v|flv)$/i, 'FILE_MOVIE'],
  [/\.(py|js|ts|osl|glsl|c|cc|cpp|h|rs|go|sh|lua)$/i, 'FILE_SCRIPT'],
  [/\.(txt|md|json|xml|csv|ini|cfg|toml|yaml|yml|log|rtf|pdf)$/i, 'FILE_TEXT'],
  [/\.(zip|7z|rar|tar|gz|tgz|bz2|xz)$/i, 'FILE_ARCHIVE'],
  [/\.(wav|mp3|ogg|flac|aac|m4a|aiff?)$/i, 'FILE_SOUND'],
  [/\.(ttf|otf|woff2?|pfb)$/i, 'FILE_FONT'],
  [/\.(obj|fbx|gltf|glb|stl|ply|abc|usd[acz]?|dae|3ds|x3d)$/i, 'FILE_3D'],
  [/\.(vdb)$/i, 'FILE_VOLUME'],
  [/\.blend\d+$/i, 'FILE_BACKUP'],
];
const IMAGE_RE = /\.(png|jpe?g|exr|hdr|tiff?|tga|bmp|webp|gif|psd|dds|svg|avif)$/i;

function fileIcon(e) {
  if (e.icon) return e.icon;
  if (e.type === 'dir') return 'FILE_FOLDER';
  if (/\.blend\d+$/i.test(e.name)) return 'FILE_BACKUP';
  for (const [re, ic] of EXT_ICON) if (re.test(e.name)) return ic;
  return 'FILE';
}

function fmtSize(s, isDir) {
  if (isDir) return '';
  if (s == null || s === '') return '';
  if (typeof s === 'string' && !/^\d+(\.\d+)?$/.test(s)) return s;
  let n = Number(s);
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let u = 0;
  while (n >= 1000 && u < units.length - 1) {
    n /= 1000;
    u++;
  }
  return u === 0 ? `${n} B` : `${n.toFixed(n < 10 ? 1 : 0)} ${units[u]}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function fmtDate(m) {
  if (m == null || m === '') return '';
  if (typeof m === 'string' && !/^\d{4}-\d\d-\d\d/.test(m) && !/^\d+$/.test(m)) return m;
  const d = new Date(/^\d+$/.test(String(m)) ? Number(m) * (Number(m) < 1e11 ? 1000 : 1) : m);
  if (Number.isNaN(d.getTime())) return String(m);
  const p = (x) => String(x).padStart(2, '0');
  const now = new Date();
  const time = `${p(d.getHours())}:${p(d.getMinutes())}`;
  const sameDay = (a, b) => a.toDateString() === b.toDateString();
  if (sameDay(d, now)) return `Today ${time}`;
  if (sameDay(d, new Date(now.getTime() - 864e5))) return `Yesterday ${time}`;
  return `${p(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()} ${time}`;
}

function sortStamp(m) {
  const t = new Date(/^\d+$/.test(String(m ?? '')) ? Number(m) * 1000 : m).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function sizeNum(s) {
  if (typeof s === 'number') return s;
  const m = /^([\d.]+)\s*([KMGT]?)i?B?/i.exec(String(s ?? ''));
  if (!m) return 0;
  return Number(m[1]) * ({'': 1, K: 1e3, M: 1e6, G: 1e9, T: 1e12}[m[2].toUpperCase()] || 1);
}

const sepOf = (p) => (p.includes('\\') && !p.includes('/') ? '\\' : '/');
function joinPath(path, name) {
  const s = sepOf(path || '/');
  const base = path ? (path.endsWith(s) ? path : path + s) : s;
  return base + name + s;
}
function parentPath(path) {
  const s = sepOf(path || '/');
  let p = String(path || '');
  const prefix = p.startsWith('//') ? '//' : '';
  const stripped = p.replace(/[\\/]+$/, '');
  if (!stripped || stripped === prefix.replace(/\/$/, '') || /^[A-Za-z]:$/.test(stripped)) return p || s;
  const i = Math.max(stripped.lastIndexOf('/'), stripped.lastIndexOf('\\'));
  if (i < 0) return prefix || s;
  const out = stripped.slice(0, i + 1);
  return out.length < prefix.length ? prefix : out || s;
}

class FileBrowserElement extends BuiElement {
  constructor() {
    super();
    this._back = [];
    this._fwd = [];
    this._query = '';
    this._sort = {key: 'name', desc: false};
    this._editPath = null;
    this._lastPath = undefined;
  }

  get path() {
    return String(this.val('path', '/') ?? '/');
  }

  get entries() {
    const v = this.val('entries', []);
    return (Array.isArray(v) ? v : []).map((e) => (e && typeof e === 'object' ? e : {name: String(e), type: 'file'}))
        .map((e) => ({...e, name: String(e.name ?? e.label ?? ''), type: e.type === 'dir' || e.type === 'folder' ? 'dir' : 'file'}));
  }

  shown() {
    const q = this._query.trim().toLowerCase();
    let list = this.entries.filter((e) => !q || e.name.toLowerCase().includes(q));
    const {key, desc} = this._sort;
    const cmp = {
      name: (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true, sensitivity: 'base'}),
      modified: (a, b) => sortStamp(a.modified) - sortStamp(b.modified),
      size: (a, b) => sizeNum(a.size) - sizeNum(b.size),
    }[key];
    list.sort((a, b) => (a.type === b.type ? 0 : a.type === 'dir' ? -1 : 1) || (desc ? -cmp(a, b) : cmp(a, b)));
    return list;
  }

  go(path, op, extra = {}) {
    const cur = this.path;
    if (path !== cur) {
      if (op !== 'back' && op !== 'forward') {
        this._back.push(cur);
        this._fwd = [];
      }
      this.set('path', path);
      this.set('selected', '');
    }
    this.fire({op, path, ...extra});
  }

  open(e) {
    if (e.type === 'dir') this.go(joinPath(this.path, e.name), 'open', {name: e.name});
    else this.fire({op: 'open', name: e.name, path: this.path, file: this.path.replace(/[\\/]?$/, sepOf(this.path)) + e.name});
  }

  parent() {
    this.go(parentPath(this.path), 'parent');
  }

  back() {
    if (!this._back.length) return;
    this._fwd.push(this.path);
    this.go(this._back.pop(), 'back');
  }

  forward() {
    if (!this._fwd.length) return;
    this._back.push(this.path);
    this.go(this._fwd.pop(), 'forward');
  }

  select(e) {
    this.set('selected', e.name);
    this.fire({op: 'select', name: e.name, path: this.path});
  }

  onKey(ev, list) {
    if (ev.target.closest('input')) return;
    const sel = this.val('selected', '');
    let i = list.findIndex((e) => e.name === sel);
    const thumbs = this.val('view', 'list') === 'thumbnails';
    let step = 0;
    if (ev.key === 'ArrowDown') step = thumbs ? this.perRow() : 1;
    else if (ev.key === 'ArrowUp') step = thumbs ? -this.perRow() : -1;
    else if (ev.key === 'ArrowRight' && thumbs) step = 1;
    else if (ev.key === 'ArrowLeft' && thumbs) step = -1;
    if (step) {
      ev.preventDefault();
      i = clamp(i < 0 ? 0 : i + step, 0, list.length - 1);
      if (list[i]) {
        this.select(list[i]);
        this.updateComplete.then(() => this.querySelector(`[data-name="${CSS.escape(list[i].name)}"]`)?.scrollIntoView({block: 'nearest'}));
      }
    } else if (ev.key === 'Enter' && list[i]) {
      ev.preventDefault();
      this.open(list[i]);
    } else if (ev.key === 'Backspace' || (ev.key === 'p' && ev.ctrlKey)) {
      ev.preventDefault();
      this.parent();
    } else if (ev.key === 'Home' || ev.key === 'End') {
      ev.preventDefault();
      const e = ev.key === 'Home' ? list[0] : list[list.length - 1];
      if (e) this.select(e);
    }
  }

  perRow() {
    const cells = [...this.querySelectorAll('.bui-fb-thumb')];
    if (cells.length < 2) return 1;
    const top = cells[0].offsetTop;
    const n = cells.findIndex((c) => c.offsetTop !== top);
    return n <= 0 ? cells.length : n;
  }

  sortBy(key) {
    this._sort = this._sort.key === key ? {key, desc: !this._sort.desc} : {key, desc: key !== 'name'};
    this.requestUpdate();
  }

  willUpdate(c) {
    super.willUpdate(c);
    // External path changes (agent navigated) also feed the history.
    const p = this.path;
    if (this._lastPath !== undefined && p !== this._lastPath && this._back[this._back.length - 1] !== this._lastPath &&
        this._fwd[this._fwd.length - 1] !== this._lastPath) {
      this._back.push(this._lastPath);
    }
    this._lastPath = p;
  }

  renderHeaderCell(key, label, cls = '') {
    const on = this._sort.key === key;
    return html`<div class="bui-fb-hcell ${cls} ${on ? 'bui-on' : ''}" @click=${() => this.sortBy(key)}
        data-tip=${`Sort by ${label.toLowerCase()}`}><span class="bui-txt">${label}</span>${
        on ? icon(this._sort.desc ? 'TRIA_DOWN' : 'TRIA_UP', 'bui-fb-sorticon') : nothing}</div>`;
  }

  renderList(list, sel) {
    const atRoot = parentPath(this.path) === this.path;
    return html`<div class="bui-fb-table">
      <div class="bui-fb-hrow">
        ${this.renderHeaderCell('name', 'Name', 'bui-fb-cname')}
        ${this.renderHeaderCell('modified', 'Date Modified', 'bui-fb-cdate')}
        ${this.renderHeaderCell('size', 'Size', 'bui-fb-csize')}
      </div>
      <div class="bui-fb-rows">
        ${atRoot ? nothing : html`<div class="bui-fb-row bui-fb-up" @dblclick=${() => this.parent()}
            data-tip="Parent directory (double-click)">
          <span class="bui-fb-cname">${icon('FILE_PARENT')}<span class="bui-txt">..</span></span>
          <span class="bui-fb-cdate"></span><span class="bui-fb-csize"></span></div>`}
        ${list.map((e, i) => html`<div class="bui-fb-row ${(i + (atRoot ? 0 : 1)) % 2 ? 'bui-alt' : ''} ${
            e.name === sel ? 'bui-active' : ''} ${e.name.startsWith('.') ? 'bui-fb-hidden' : ''}"
            data-name=${e.name} role="option" aria-selected=${e.name === sel}
            @click=${() => this.select(e)} @dblclick=${() => this.open(e)}>
          <span class="bui-fb-cname">${icon(fileIcon(e), e.type === 'dir' ? 'bui-fb-dir' : '')}<span class="bui-txt">${
            e.name}</span></span>
          <span class="bui-fb-cdate">${fmtDate(e.modified)}</span>
          <span class="bui-fb-csize">${fmtSize(e.size, e.type === 'dir')}</span>
        </div>`)}
      </div>
    </div>`;
  }

  renderThumbs(list, sel) {
    return html`<div class="bui-fb-grid">
      ${list.map((e) => {
        const ic = fileIcon(e);
        const isImg = e.image || (e.color != null && (IMAGE_RE.test(e.name) || e.type !== 'dir'));
        return html`<div class="bui-fb-thumb ${e.name === sel ? 'bui-active' : ''}" data-name=${e.name} role="option"
            aria-selected=${e.name === sel} data-tip=${e.name}
            @click=${() => this.select(e)} @dblclick=${() => this.open(e)}>
          <span class="bui-fb-art ${isImg ? 'bui-fb-art-img' : ''}">${
            e.image ? html`<img src=${e.image} alt="" draggable="false">` :
            e.color != null ? html`<span class="bui-fb-swatch" style="background:${cssColor(e.color)}">${
              IMAGE_RE.test(e.name) ? nothing : icon(ic)}</span>` :
            html`<span class="bui-fb-bigicon ${e.type === 'dir' ? 'bui-fb-dir' : ''}">${icon(ic)}</span>`}</span>
          <span class="bui-fb-tname">${e.name}</span>
        </div>`;
      })}
    </div>`;
  }

  updated(c) {
    super.updated?.(c);
    if (this._editPath != null) {
      const inp = this.querySelector('.bui-fb-path input');
      if (inp && document.activeElement !== inp) {
        inp.focus();
        inp.select();
      }
    }
  }

  render() {
    const list = this.shown();
    const sel = this.val('selected', '');
    const view = this.val('view', 'list') === 'thumbnails' ? 'thumbnails' : 'list';
    const path = this.path;
    return html`<div class="bui-fb ${this.enabled ? '' : 'bui-disabled'}">
      <div class="bui-fb-bar">
        <div class="bui-joined-h">
          ${iconBtn('BACK', () => this.back(), {tip: 'Move to previous folder (Backspace)', disabled: !this._back.length})}
          ${iconBtn('FORWARD', () => this.forward(), {tip: 'Move to next folder (Shift Backspace)', disabled: !this._fwd.length})}
          ${iconBtn('FILE_PARENT', () => this.parent(), {tip: 'Move to parent directory (P)',
            disabled: parentPath(path) === path})}
          ${iconBtn('FILE_REFRESH', () => this.fire({op: 'refresh', path}), {tip: 'Refresh the file list (R)'})}
        </div>
        ${iconBtn('NEWFOLDER', () => this.fire({op: 'newfolder', path}), {tip: 'Create a new directory', emboss: false})}
        <label class="bui-w bui-fb-path">
          <input class="bui-input" spellcheck="false" .value=${this._editPath ?? path}
              @focus=${(e) => {
                this._editPath = e.target.value;
              }}
              @input=${(e) => {
                this._editPath = e.target.value;
              }}
              @keydown=${(e) => {
                e.stopPropagation();
                if (e.key === 'Enter') {
                  const v = e.target.value.trim();
                  this._editPath = null;
                  e.target.blur();
                  if (v) this.go(v, 'open', {name: ''});
                } else if (e.key === 'Escape') {
                  this._editPath = null;
                  e.target.value = path;
                  e.target.blur();
                }
              }}
              @blur=${(e) => {
                this._editPath = null;
                e.target.value = this.path;
              }}>
        </label>
        <div class="bui-joined-h">
          ${iconBtn('LONGDISPLAY', () => this.set('view', 'list'), {tip: 'Vertical List', pressed: view === 'list'})}
          ${iconBtn('IMGDISPLAY', () => this.set('view', 'thumbnails'), {tip: 'Thumbnails', pressed: view === 'thumbnails'})}
        </div>
        <label class="bui-w bui-fb-search">${icon('VIEWZOOM')}<input class="bui-input" placeholder="" spellcheck="false"
            .value=${this._query} @input=${(e) => {
              this._query = e.target.value;
              this.requestUpdate();
            }} @keydown=${(e) => {
              e.stopPropagation();
              if (e.key === 'Escape') {
                this._query = '';
                e.target.value = '';
                this.requestUpdate();
              }
            }}>${this._query ? html`<span class="bui-fb-clear" @click=${() => {
              this._query = '';
              this.requestUpdate();
            }}>${icon('PANEL_CLOSE')}</span>` : nothing}</label>
      </div>
      <div class="bui-fb-body" tabindex="0" role="listbox" @keydown=${(e) => this.onKey(e, list)}>
        ${view === 'list' ? this.renderList(list, sel) : this.renderThumbs(list, sel)}
        ${list.length === 0 && this._query ? html`<div class="bui-fb-empty">No items match “${this._query}”</div>` : nothing}
      </div>
    </div>`;
  }
}

export const IMPLS = [
  impl('ListView', ListViewElement),
  impl('TreeView', TreeViewElement),
  impl('GridView', GridViewElement),
  impl('FileBrowser', FileBrowserElement),
];
