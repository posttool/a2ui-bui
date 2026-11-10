// Layout components: Column, Row, Split, Grid, Box, Panel, Tabs, SideTabs,
// ScrollView, Area.

import {BuiElement, html, impl, nothing, normItems, popup} from '../base.js';
import {icon} from '../icons.js';
import {menuList} from './menu_list.js';

const SPACING = {none: '0', small: 'calc(var(--bui-gap) * 1)', normal: 'calc(var(--bui-gap) * 2)', large: 'calc(var(--bui-gap) * 5)'};

class StackElement extends BuiElement {
  static dir = 'v';
  willUpdate(c) {
    super.willUpdate(c);
    const p = this.p;
    const joined = !!this.val('align', false);
    const d = this.constructor.dir;
    this.classList.add('bui-stack', `bui-stack-${d}`);
    this.classList.toggle(`bui-joined-${d}`, joined);
    this.style.gap = joined ? '0' : SPACING[p.spacing || 'normal'];
    if (typeof p.padding === 'number') this.style.padding = `calc(var(--bui-u) * ${p.padding})`;
    else this.style.removeProperty('padding');
    const J = {start: 'flex-start', center: 'center', end: 'flex-end', spaceBetween: 'space-between'};
    if (p.justify) this.style.justifyContent = J[p.justify] || 'flex-start';
    else this.style.removeProperty('justify-content');
  }
  render() {
    return html`${this.kids(this.p.children)}`;
  }
}
class ColumnElement extends StackElement {
  static dir = 'v';
}
class RowElement extends StackElement {
  static dir = 'h';
}

class SplitElement extends BuiElement {
  render() {
    const f = typeof this.p.factor === 'number' ? this.p.factor : 0.4;
    return html`<div class="bui-split">
      <div class="bui-split-l" style="flex: 0 0 ${f * 100}%">${this.kids(this.p.left)}</div>
      <div class="bui-split-r">${this.kids(this.p.right)}</div>
    </div>`;
  }
}

class GridElement extends BuiElement {
  render() {
    const n = Math.max(1, Math.round(this.p.columns || 2));
    return html`<div class="bui-grid ${this.p.align ? 'bui-grid-joined' : ''}"
        style="grid-template-columns: repeat(${n}, minmax(0, 1fr))">${this.kids(this.p.children)}</div>`;
  }
}

class BoxElement extends BuiElement {
  render() {
    return html`<div class="bui-box bui-stack bui-stack-v ${this.p.align ? 'bui-joined-v' : ''}">${
        this.kids(this.p.children)}</div>`;
  }
}

class PanelElement extends BuiElement {
  toggle(e) {
    if (e.target.closest('.bui-panel-hdr-widgets')) return;
    const solo = e.ctrlKey || e.metaKey;
    const next = !this.val('collapsed', false);
    if (solo) {
      // Ctrl+click: open this panel, collapse its siblings (Blender solo).
      const parent = this.parentElement;
      if (parent) {
        for (const sib of parent.children) {
          if (sib !== this && sib.tagName === this.tagName) sib.set('collapsed', true);
        }
      }
      this.set('collapsed', false);
      return;
    }
    this.set('collapsed', next);
  }
  render() {
    const p = this.p;
    const collapsed = !!this.val('collapsed', false);
    const hdr = p.header;
    return html`<section class="bui-panel ${p.sub ? 'bui-panel-sub' : ''} ${collapsed ? 'bui-collapsed' : ''}">
      <header class="bui-panel-hdr" @click=${(e) => this.toggle(e)}>
        <span class="bui-panel-tri">${icon(collapsed ? 'DISCLOSURE_TRI_RIGHT' : 'DISCLOSURE_TRI_DOWN')}</span>
        ${hdr ? html`<span class="bui-panel-hdr-widgets">${this.kids(hdr)}</span>` : nothing}
        ${icon(p.icon)}
        <span class="bui-panel-title">${p.title}</span>
        <span class="bui-panel-grip">${icon('GRIP')}</span>
      </header>
      <div class="bui-panel-body bui-stack bui-stack-v">${collapsed ? nothing : this.kids(p.children)}</div>
    </section>`;
  }
}

class TabsElement extends BuiElement {
  render() {
    const tabs = Array.isArray(this.p.tabs) ? this.p.tabs : [];
    const cur = Math.min(tabs.length - 1, Math.max(0, Math.round(this.val('current', 0))));
    return html`<div class="bui-tabs">
      <div class="bui-tabs-row" role="tablist">${tabs.map((t, i) => html`
        <button class="bui-tab ${i === cur ? 'bui-sel' : ''}" role="tab" aria-selected=${i === cur}
            @click=${() => this.set('current', i)}>${icon(t.icon)}<span>${t.title ?? ''}</span></button>`)}
      </div>
      <div class="bui-tabs-body">${tabs[cur] ? this.kids(tabs[cur].child) : nothing}</div>
    </div>`;
  }
}

class SideTabsElement extends BuiElement {
  render() {
    const tabs = Array.isArray(this.p.tabs) ? this.p.tabs : [];
    const cur = Math.min(tabs.length - 1, Math.max(0, Math.round(this.val('current', 0))));
    return html`<div class="bui-sidetabs">
      <nav class="bui-sidetabs-rail" role="tablist">${tabs.map((t, i) => html`
        <button class="bui-sidetab ${i === cur ? 'bui-sel' : ''}" role="tab" aria-selected=${i === cur}
            data-tip=${t.title ?? ''} @click=${() => this.set('current', i)}>${icon(t.icon || 'PROPERTIES')}</button>`)}
      </nav>
      <div class="bui-sidetabs-body">
        ${tabs[cur] ? html`<div class="bui-sidetabs-title">${icon(tabs[cur].icon)}<span>${tabs[cur].title ?? ''}</span></div>` : nothing}
        ${tabs[cur] ? this.kids(tabs[cur].child) : nothing}
      </div>
    </div>`;
  }
}

class ScrollViewElement extends BuiElement {
  render() {
    const rows = typeof this.p.rows === 'number' ? this.p.rows : 8;
    return html`<div class="bui-scroll" style="max-height: calc(var(--bui-u) * ${rows} + var(--bui-gap) * ${rows})">${
        this.kids(this.p.child)}</div>`;
  }
}

const DEFAULT_EDITORS = [
  {label: '3D Viewport', icon: 'VIEW3D'}, {label: 'Image Editor', icon: 'IMAGE'}, {label: 'Shader Editor', icon: 'NODE_MATERIAL'},
  {label: 'Geometry Node Editor', icon: 'GEOMETRY_NODES'}, {label: 'Outliner', icon: 'OUTLINER'},
  {label: 'Properties', icon: 'PROPERTIES'}, {label: 'File Browser', icon: 'FILEBROWSER'},
  {label: 'Spreadsheet', icon: 'SPREADSHEET'}, {label: 'Text Editor', icon: 'TEXT'}, {label: 'Timeline', icon: 'TIME'},
];

class AreaElement extends BuiElement {
  openEditors(e) {
    const items = normItems(Array.isArray(this.p.editors) && this.p.editors.length ? this.p.editors : DEFAULT_EDITORS);
    const cur = this.val('editor', '');
    popup(e.currentTarget, (box, close) => menuList(box, {
      title: 'Editor Type',
      items: items.map((it) => ({...it, checked: it.label === cur})),
      onPick: (it) => {
        close();
        this.set('editor', it.label);
        this.fire({editor: it.label});
      },
    }));
  }
  render() {
    const p = this.p;
    const editor = this.val('editor', '');
    const items = normItems(Array.isArray(p.editors) && p.editors.length ? p.editors : DEFAULT_EDITORS);
    const ic = p.icon || items.find((i) => i.label === editor)?.icon || 'WINDOW';
    const h = typeof p.height === 'number' ? `height: calc(var(--bui-u) * ${p.height})` : '';
    return html`<div class="bui-area" style=${h}>
      <div class="bui-area-hdr bui-stack bui-stack-h">
        <button class="bui-w bui-area-type" data-tip=${editor} @click=${(e) => this.openEditors(e)}>
          ${icon(ic)}${icon('DOWNARROW_HLT', 'bui-caret')}
        </button>
        ${this.kids(p.header)}
      </div>
      <div class="bui-area-body">${this.kids(p.child)}</div>
    </div>`;
  }
}

export const IMPLS = [
  impl('Column', ColumnElement),
  impl('Row', RowElement),
  impl('Split', SplitElement),
  impl('Grid', GridElement),
  impl('Box', BoxElement),
  impl('Panel', PanelElement),
  impl('Tabs', TabsElement),
  impl('SideTabs', SideTabsElement),
  impl('ScrollView', ScrollViewElement),
  impl('Area', AreaElement),
];
