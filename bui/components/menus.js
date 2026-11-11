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

// Menus: MenuBar (Blender top bar) and PieMenu (radial pie).

import {svg} from '../../third_party/a2ui_bundle/a2ui.bundle.js';
import {BuiElement, html, impl, nothing, normItems} from '../base.js';
import {icon} from '../icons.js';
import {layerFor, openMenu} from './buttons.js';

// ----------------------------------------------------------------- MenuBar
class MenuBarElement extends BuiElement {
  constructor() {
    super();
    this._openIdx = -1;
    this._close = null;
  }
  get menus() {
    return Array.isArray(this.p.menus) ? this.p.menus : [];
  }
  openAt(i, anchor) {
    if (this._openIdx === i) return;
    this._close?.();
    const m = this.menus[i];
    if (!m || !this.enabled) return;
    this._openIdx = i;
    this.requestUpdate();
    anchor.addEventListener('bui-popup-closed', () => {
      if (this._openIdx === i) {
        this._openIdx = -1;
        this._close = null;
        this.requestUpdate();
      }
    }, {once: true});
    const title = String(m.title ?? m.label ?? '');
    this._close = openMenu(anchor, {
      items: m.items,
      onPick: (it) => this.fire({menu: title, item: it.value ?? it.label}),
    });
  }
  press(i, e) {
    if (this._openIdx === i) {
      this._close?.();
      return;
    }
    this.openAt(i, e.currentTarget);
  }
  hover(i, e) {
    // Blender: while a menu is open, hovering another title switches menus.
    if (this._openIdx >= 0 && this._openIdx !== i) this.openAt(i, e.currentTarget);
  }
  disconnectedCallback() {
    this._close?.();
    super.disconnectedCallback();
  }
  render() {
    const p = this.p;
    return html`<div class="bui-menubar" role="menubar">
      ${this.menus.map((m, i) => html`<button class="bui-menubar-title ${this._openIdx === i ? 'bui-open' : ''}"
          role="menuitem" aria-haspopup="menu" aria-expanded=${this._openIdx === i ? 'true' : 'false'}
          @pointerdown=${(e) => this.press(i, e)} @pointerenter=${(e) => this.hover(i, e)}>
        ${m.icon ? icon(m.icon) : nothing}<span>${m.title ?? m.label ?? ''}</span></button>`)}
      <span class="bui-menubar-fill"></span>
      ${p.right ? html`<div class="bui-menubar-right">${this.kids(p.right)}</div>` : nothing}
    </div>`;
  }
}

// ----------------------------------------------------------------- PieMenu
// Blender's item order and their direction angles (degrees, 0 = east, CCW).
const DIRS8 = [['W', 180], ['E', 0], ['S', 270], ['N', 90], ['NW', 135], ['NE', 45], ['SW', 225], ['SE', 315]];
const NUMPAD = {4: 'W', 6: 'E', 2: 'S', 8: 'N', 7: 'NW', 9: 'NE', 1: 'SW', 3: 'SE'};

// Last pointer position on the page (pies opened by hotkey center on it).
const pointer = {x: 0, y: 0};
document.addEventListener('pointermove', (e) => {
  pointer.x = e.clientX;
  pointer.y = e.clientY;
}, {capture: true, passive: true});

const isTyping = (t) => t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));

class PieMenuElement extends BuiElement {
  constructor() {
    super();
    this._pie = null;  // {cx, cy, angle, hot, dist, by}
    this._key = (e) => this.onKey(e);
    this._keyUp = (e) => this.onKeyUp(e);
  }
  connectedCallback() {
    super.connectedCallback();
    document.addEventListener('keydown', this._key);
    document.addEventListener('keyup', this._keyUp);
  }
  disconnectedCallback() {
    document.removeEventListener('keydown', this._key);
    document.removeEventListener('keyup', this._keyUp);
    this.close();
    if (this.__overlay && this.__overlay.parentNode !== this) this.appendChild(this.__overlay);
    this.__overlay = null;
    super.disconnectedCallback();
  }
  get items() {
    const list = normItems(this.p.items).slice(0, 8);
    const dirs = list.length <= 4 ? DIRS8.slice(0, 4) : DIRS8;
    return list.map((it, i) => ({...it, dir: dirs[i][0], angle: dirs[i][1]}));
  }
  get unit() {
    return parseFloat(getComputedStyle(this).getPropertyValue('--bui-u')) || 25;
  }
  // ---- open / close
  open(clientX, clientY, by) {
    if (!this.enabled || !this.items.length) return;
    const layer = layerFor(this);
    if (!layer) return;
    const rl = layer.getBoundingClientRect();
    this._pie = {cx: clientX - rl.left, cy: clientY - rl.top, angle: null, hot: null, by, t0: performance.now(),
      x0: clientX, y0: clientY, moved: false};
    this.requestUpdate();
  }
  openFromButton(e) {
    if (this._pie) {
      this.close();
      return;
    }
    const r = e.currentTarget.getBoundingClientRect();
    this.open(r.left + r.width / 2, r.top + r.height / 2, 'button');
    // Press-drag-release picks like Blender's click-drag pies.
    const up = (ev) => {
      window.removeEventListener('pointerup', up, true);
      if (this._pie && this._pie.moved && this._pie.hot) {
        ev.stopPropagation();
        this.pick(this._pie.hot);
      }
    };
    window.addEventListener('pointerup', up, true);
  }
  close() {
    if (!this._pie) return;
    this._pie = null;
    this.requestUpdate();
  }
  pick(it) {
    if (!it || it.enabled === false) return;
    this.close();
    this.set('value', it.value);
    this.fire({item: it.value});
  }
  // ---- keyboard
  onKey(e) {
    if (this._pie) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        this.close();
      } else if (NUMPAD[e.key] && !e.repeat) {
        const it = this.items.find((x) => x.dir === NUMPAD[e.key]);
        if (it) {
          e.preventDefault();
          this.pick(it);
        }
      } else if (e.key === 'Enter' && this._pie.hot) {
        e.preventDefault();
        this.pick(this._pie.hot);
      }
      return;
    }
    const hk = String(this.p.hotkey || '');
    if (!hk || e.repeat || e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return;
    if (e.key.toLowerCase() !== hk.toLowerCase()) return;
    const root = this.closest('.bui-root');
    const rr = root?.getBoundingClientRect();
    const inside = rr && pointer.x >= rr.left && pointer.x <= rr.right && pointer.y >= rr.top && pointer.y <= rr.bottom;
    if (!root || !inside || document.querySelector('.bui-popup:not([hidden]) .bui-menu')) return;
    e.preventDefault();
    this.open(pointer.x, pointer.y, 'key');
  }
  onKeyUp(e) {
    const pie = this._pie;
    if (!pie || pie.by !== 'key') return;
    if (e.key.toLowerCase() !== String(this.p.hotkey || '').toLowerCase()) return;
    // Held key + drag: release picks the highlighted item; a quick tap keeps it open.
    if (pie.hot && (pie.moved || performance.now() - pie.t0 > 300)) this.pick(pie.hot);
  }
  // ---- pointer tracking inside the overlay
  track(e) {
    const pie = this._pie;
    if (!pie) return;
    const rl = e.currentTarget.getBoundingClientRect();
    const dx = e.clientX - rl.left - pie.cx;
    const dy = e.clientY - rl.top - pie.cy;
    const dist = Math.hypot(dx, dy);
    if (Math.hypot(e.clientX - pie.x0, e.clientY - pie.y0) > 6) pie.moved = true;
    const ang = (Math.atan2(-dy, dx) * 180 / Math.PI + 360) % 360;
    const dead = this.unit * 0.65;
    let hot = null;
    if (dist > dead) {
      let best = 999;
      for (const it of this.items) {
        if (it.enabled === false) continue;
        const d = Math.abs(((ang - it.angle + 540) % 360) - 180);
        if (d < best) {
          best = d;
          hot = it;
        }
      }
    }
    pie.angle = dist > dead ? ang : null;
    pie.hot = hot;
    this.requestUpdate();  // the direction arc follows the pointer
  }
  clickOverlay(e) {
    const pie = this._pie;
    if (!pie) return;
    const itemEl = e.target.closest('.bui-pie-item');
    if (itemEl) {
      const it = this.items[Number(itemEl.dataset.i)];
      return this.pick(it);
    }
    if (pie.hot) this.pick(pie.hot);
    else this.close();
  }
  // ---- render
  updated(c) {
    super.updated?.(c);
    const ov = this.querySelector(':scope > .bui-pie-overlay') || this.__overlay;
    if (ov && ov.parentNode === this) {
      const layer = layerFor(this);
      if (layer) {
        layer.appendChild(ov);
        this.__overlay = ov;
      }
    }
    // Keep the whole pie inside the surface (Blender shifts pies at window edges).
    const pie = this._pie;
    if (pie && ov && !pie.fitted) {
      pie.fitted = true;
      const ro = ov.getBoundingClientRect();
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const el of ov.querySelectorAll('.bui-pie-item, .bui-pie-title')) {
        const r = el.getBoundingClientRect();
        minX = Math.min(minX, r.left - ro.left);
        minY = Math.min(minY, r.top - ro.top);
        maxX = Math.max(maxX, r.right - ro.left);
        maxY = Math.max(maxY, r.bottom - ro.top);
      }
      if (Number.isFinite(minX)) {
        const pad = 6;
        let sx = 0, sy = 0;
        if (minX < pad) sx = pad - minX;
        else if (maxX > ro.width - pad) sx = Math.max(pad - minX, ro.width - pad - maxX);
        if (minY < pad) sy = pad - minY;
        else if (maxY > ro.height - pad) sy = Math.max(pad - minY, ro.height - pad - maxY);
        if (sx || sy) {
          pie.cx += sx;
          pie.cy += sy;
          this.requestUpdate();
        }
      }
    }
  }
  renderPie() {
    const pie = this._pie;
    if (!pie) return nothing;
    const p = this.p;
    const items = this.items;
    const cur = this.val('value', '');
    const ring = svg`<svg class="bui-pie-ring" viewBox="-50 -50 100 100" aria-hidden="true">
      <circle class="bui-pie-ring-bg" r="46"></circle>
      <circle class="bui-pie-ring-track" r="31" fill="none"></circle>
      ${pie.angle != null ? svg`<path class="bui-pie-ring-dir" transform="rotate(${-pie.angle})"
          d="M ${31 * Math.cos(-0.4)} ${31 * Math.sin(-0.4)} A 31 31 0 0 1 ${31 * Math.cos(0.4)} ${31 * Math.sin(0.4)}"></path>` : nothing}
    </svg>`;
    return html`<div class="bui-pie" style="left: ${pie.cx}px; top: ${pie.cy}px">
      ${ring}
      ${p.title ? html`<div class="bui-pie-title">${p.title}</div>` : nothing}
      ${items.map((it, i) => {
      const a = it.angle * Math.PI / 180;
      const x = Math.cos(a), y = -Math.sin(a);
      const ax = Math.abs(x) < 0.01 ? 'c' : x < 0 ? 'r' : 'l';
      const ay = Math.abs(y) < 0.01 ? 'c' : y < 0 ? 'b' : 't';
      // Horizontal neighbours hang from the circle edge; N/S sit centred.
      const anchor = ay !== 'c' && ax === 'c' ? `bui-pie-${ay === 'b' ? 'n' : 's'}` : `bui-pie-${ax === 'r' ? 'w' : 'e'}`;
      const hot = pie.hot && pie.hot.value === it.value;
      return html`<button class="bui-pie-item ${anchor} ${hot ? 'bui-hot' : ''} ${it.value === cur ? 'bui-cur' : ''}
          ${it.enabled === false ? 'bui-off' : ''}" data-i=${i} data-dir=${it.dir}
          style="--x: ${x.toFixed(4)}; --y: ${y.toFixed(4)}; --d: ${i * 12}ms" data-tip=${it.description || nothing}>
        ${it.icon ? icon(it.icon) : html`<span class="bui-icon-blank"></span>`}
        <span class="bui-txt">${it.label}</span>
      </button>`;
    })}
    </div>`;
  }
  render() {
    const p = this.p;
    const open = !!this._pie;
    const text = p.text ?? p.title ?? '';
    return html`<button class="bui-w bui-center bui-piebtn ${open ? 'bui-open' : ''}" ?disabled=${!this.enabled}
        aria-haspopup="menu" aria-expanded=${open ? 'true' : 'false'} @pointerdown=${(e) => this.openFromButton(e)}>
      ${p.icon ? icon(p.icon) : nothing}
      ${text ? html`<span class="bui-txt">${text}</span>` : nothing}
      ${p.hotkey ? html`<span class="bui-piebtn-key">${String(p.hotkey).toUpperCase()}</span>` : nothing}
    </button><div class="bui-pie-overlay" ?hidden=${!open} @pointermove=${(e) => this.track(e)}
        @click=${(e) => this.clickOverlay(e)} @contextmenu=${(e) => {
      e.preventDefault();
      this.close();
    }}>${this.renderPie()}</div>`;
  }
}

export const IMPLS = [
  impl('MenuBar', MenuBarElement),
  impl('PieMenu', PieMenuElement),
];
