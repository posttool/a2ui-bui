/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Choice components: Dropdown, EnumRow, ColorSwatch (+ popup color picker),
// IDSelector (Blender template_ID).

import {LitElement} from '../../third_party/a2ui_bundle/a2ui.bundle.js';
import {BuiElement, clamp, cssColor, drag, html, impl, nothing, normItems, popup, toHex, toRgba} from '../base.js';
import {icon} from '../icons.js';
import {menuList} from './menu_list.js';
import {NumCtl, labeled} from './values.js';

/** Marks the menu row for the current value (Blender opens enum menus on the active item). */
function markActive(menu, items, cur) {
  const i = items.findIndex((it) => it.value === cur || it.label === cur);
  if (i < 0) return;
  const rows = menu.querySelectorAll('.bui-menu-item');
  rows[i]?.classList.add('bui-active-item');
}

const findItem = (items, v) => items.find((it) => it.value === v || it.label === v);

// ---------------------------------------------------------------- Dropdown

class DropdownElement extends BuiElement {
  open(e) {
    if (!this.enabled) return;
    const btn = e.currentTarget;
    const items = normItems(this.p.items, this.p.icons);
    const cur = this.val('value', '');
    const curValue = findItem(items, cur)?.value;
    btn.classList.add('bui-open');
    btn.addEventListener('bui-popup-closed', () => btn.classList.remove('bui-open'), {once: true});
    popup(btn, (box, close) => {
      box.style.minWidth = `${btn.getBoundingClientRect().width}px`;
      const menu = menuList(box, {
        title: this.p.label || '',
        items,
        onPick: (it) => {
          close();
          this.set('value', it.value);
          this.fire({value: it.value, label: it.label});
        },
      });
      markActive(menu, items, curValue);
    });
  }
  render() {
    const p = this.p;
    const items = normItems(p.items, p.icons);
    const cur = this.val('value', items[0]?.value ?? '');
    const it = findItem(items, cur) || {label: String(cur ?? ''), icon: ''};
    const iconOnly = !!p.iconOnly;
    const btn = html`<button class="bui-w bui-dropdown ${iconOnly ? 'bui-icon-only' : ''}" aria-haspopup="menu"
        aria-label=${p.label || it.label} @click=${(e) => this.open(e)}
        @keydown=${(e) => this.key(e, items, cur)}>
      ${icon(it.icon)}
      ${iconOnly ? nothing : html`<span class="bui-txt">${it.label}</span>`}
      ${icon('DOWNARROW_HLT', 'bui-caret')}
    </button>`;
    return iconOnly ? btn : labeled(p.label, btn);
  }
  key(e, items, cur) {
    // Ctrl+Wheel / arrows cycle (Blender ctrl-scroll over enum buttons).
    if (!(e.key === 'ArrowDown' || e.key === 'ArrowUp') || !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    this.cycle(items, cur, e.key === 'ArrowDown' ? 1 : -1);
  }
  cycle(items, cur, d) {
    if (!items.length) return;
    const i = Math.max(0, items.findIndex((x) => x.value === cur || x.label === cur));
    const n = items[clamp(i + d, 0, items.length - 1)];
    if (n.value === cur) return;
    this.set('value', n.value);
    this.fire({value: n.value, label: n.label});
  }
  firstUpdated() {
    this.addEventListener('wheel', (e) => {
      if (!(e.ctrlKey || e.metaKey) || !this.enabled) return;
      e.preventDefault();
      const items = normItems(this.p.items, this.p.icons);
      const cur = this.val('value', items[0]?.value ?? '');
      this.cycle(items, findItem(items, cur)?.value ?? cur, e.deltaY > 0 ? 1 : -1);
    }, {passive: false});
  }
}

// ---------------------------------------------------------------- EnumRow

class EnumRowElement extends BuiElement {
  pick(it) {
    if (!this.enabled) return;
    this.set('value', it.value);
    this.fire({value: it.value, label: it.label});
  }
  render() {
    const p = this.p;
    const items = normItems(p.items, p.icons);
    const cur = this.val('value', items[0]?.value ?? '');
    const curValue = findItem(items, cur)?.value;
    const vertical = !!p.vertical;
    const row = html`<div class="bui-enumrow ${vertical ? 'bui-enumrow-v bui-joined-v' : 'bui-joined-h'}" role="radiogroup"
        aria-label=${p.label || nothing}>
      ${items.map((it) => {
        const on = it.value === curValue;
        return html`<button class="bui-w bui-radio ${on ? 'bui-on' : ''} ${p.iconOnly ? 'bui-icon-only' : ''} ${vertical ? '' : 'bui-center'}"
            role="radio" aria-checked=${on} data-tip=${it.description || (p.iconOnly ? it.label : '') || nothing}
            aria-label=${it.label} @click=${() => this.pick(it)}>
          ${icon(it.icon)}${p.iconOnly && it.icon ? nothing : html`<span class="bui-txt">${it.label}</span>`}
        </button>`;
      })}
    </div>`;
    if (!p.label) return row;
    if (vertical) return html`<div class="bui-enumrow-wrap"><div class="bui-vec-label">${p.label}:</div>${row}</div>`;
    return labeled(p.label, row);
  }
}

// ---------------------------------------------------------------- color math

export function rgb2hsv(r, g, b) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let h = 0;
  if (d > 1e-9) {
    if (mx === r) h = ((g - b) / d) % 6;
    else if (mx === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
    if (h < 0) h += 1;
  }
  return [h, mx > 1e-9 ? d / mx : 0, mx];
}

export function hsv2rgb(h, s, v) {
  h = ((h % 1) + 1) % 1;
  const i = Math.floor(h * 6), f = h * 6 - i;
  const p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i % 6];
}

function hsv2hsl(h, s, v) {
  const l = v * (1 - s / 2);
  const sl = l <= 1e-9 || l >= 1 - 1e-9 ? 0 : (v - l) / Math.min(l, 1 - l);
  return [h, sl, l];
}

function hsl2hsv(h, s, l) {
  const v = l + s * Math.min(l, 1 - l);
  return [h, v <= 1e-9 ? 0 : 2 * (1 - l / v), v];
}

const css3 = (rgb, a = 1) => cssColor([...rgb, a]);

// The popup picker is rendered by a tiny light-DOM LitElement so it can use
// lit templates outside the A2UI tree.
class PopHost extends LitElement {
  createRenderRoot() {
    return this;
  }
  render() {
    return this.tpl ? this.tpl() : nothing;
  }
}
if (!customElements.get('bui-x-pop-host')) customElements.define('bui-x-pop-host', PopHost);

const MODES = ['RGB', 'HSV', 'HSL'];
let lastMode = 'HSV';

class ColorPicker {
  constructor(swatch, close) {
    this.swatch = swatch;
    this.close = close;
    const [r, g, b, a] = toRgba(swatch.val('value', [0.5, 0.5, 0.5, 1]));
    this.hsv = rgb2hsv(r, g, b);
    this.a = a;
    this.mode = lastMode;
    this.ctls = Array.from({length: 4}, () => new NumCtl(() => this.draw()));
    this.hexDraft = null;
  }
  get rgb() {
    return hsv2rgb(...this.hsv);
  }
  mount(box) {
    this.host = document.createElement('bui-x-pop-host');
    this.host.tpl = () => this.tpl();
    box.appendChild(this.host);
  }
  draw() {
    this.host?.requestUpdate();
  }
  push(commit) {
    this.swatch.writeColor([...this.rgb, this.a], commit);
    this.draw();
  }
  setRgb(rgb) {
    const [h, s, v] = rgb2hsv(...rgb);
    // Keep hue (and saturation) when they become undefined at grey / black.
    this.hsv = [s > 1e-6 && v > 1e-6 ? h : this.hsv[0], v > 1e-6 ? s : this.hsv[1], v];
  }
  // --- wheel / square / strips: absolute pointer mapping
  areaDrag(e, kind) {
    if (e.button !== 0) return;
    e.preventDefault();
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    const apply = (x, y, fine) => {
      void fine;
      const fx = clamp((x - r.left) / r.width, 0, 1);
      const fy = clamp((y - r.top) / r.height, 0, 1);
      let [h, s, v] = this.hsv;
      if (kind === 'wheel') {
        const dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2);
        const rad = r.width / 2;
        s = clamp(Math.hypot(dx, dy) / rad, 0, 1);
        const ang = Math.atan2(dx, -dy) * 180 / Math.PI;  // clockwise from top
        h = (((ang - 180) % 360) + 360) % 360 / 360;
      } else if (kind === 'sv') {
        s = fx;
        v = 1 - fy;
      } else if (kind === 'value') {
        v = 1 - fy;
      } else if (kind === 'hue') {
        h = Math.min(0.9999, 1 - fy);
      }
      this.hsv = [h, s, v];
      this.push(false);
    };
    const x0 = e.clientX, y0 = e.clientY;
    apply(x0, y0);
    drag(e, {
      onMove: (dx, dy, ev) => apply(x0 + dx, y0 + dy, ev.shiftKey),
      onEnd: () => this.push(true),
    });
  }
  sliders() {
    const [h, s, v] = this.hsv;
    const rgb = this.rgb;
    let rows;
    if (this.mode === 'RGB') {
      rows = ['R', 'G', 'B'].map((l, i) => ({label: l, value: rgb[i], set: (n) => {
        const c = [...this.rgb];
        c[i] = n;
        this.setRgb(c);
      }}));
    } else if (this.mode === 'HSV') {
      rows = ['H', 'S', 'V'].map((l, i) => ({label: l, value: [h, s, v][i], set: (n) => {
        const c = [...this.hsv];
        c[i] = i === 0 ? Math.min(n, 0.9999) : n;
        this.hsv = c;
      }}));
    } else {
      const hsl = hsv2hsl(h, s, v);
      rows = ['H', 'S', 'L'].map((l, i) => ({label: l, value: hsl[i], set: (n) => {
        const c = [...hsv2hsl(...this.hsv)];
        c[i] = i === 0 ? Math.min(n, 0.9999) : n;
        const nv = hsl2hsv(...c);
        this.hsv = [nv[0], nv[2] > 1e-6 ? nv[1] : this.hsv[1], nv[2]];
      }}));
    }
    if (this.swatch.p.alpha) rows.push({label: 'A', value: this.a, set: (n) => (this.a = n)});
    return html`<div class="bui-cp-sliders">${rows.map((row, i) => this.ctls[i].render({
      value: row.value, label: row.label, min: 0, max: 1, step: 0.01, precision: 3, slider: true,
      onInput: (n) => {
        row.set(n);
        this.push(false);
      },
      onCommit: () => this.push(true),
    }))}</div>`;
  }
  tpl() {
    const [h, s, v] = this.hsv;
    const rgb = this.rgb;
    const hue = css3(hsv2rgb(h, 1, 1));
    const circle = (this.swatch.p.picker || 'circle') !== 'square';
    let area, strip;
    if (circle) {
      const ang = (180 + h * 360) * Math.PI / 180;
      const cx = 50 + 50 * s * Math.sin(ang), cy = 50 - 50 * s * Math.cos(ang);
      area = html`<div class="bui-cp-wheel" @pointerdown=${(e) => this.areaDrag(e, 'wheel')}>
        <div class="bui-cp-wheel-dim" style="opacity:${((1 - v) * 0.55).toFixed(3)}"></div>
        <span class="bui-cp-cursor" style="left:${cx}%;top:${cy}%;background:${css3(hsv2rgb(h, s, Math.max(v, .5)))}"></span>
      </div>`;
      strip = html`<div class="bui-cp-strip" style="background:linear-gradient(to top, #000, ${css3(hsv2rgb(h, s, 1))})"
          @pointerdown=${(e) => this.areaDrag(e, 'value')}>
        <span class="bui-cp-cursor" style="left:50%;top:${(1 - v) * 100}%;background:${css3(rgb)}"></span>
      </div>`;
    } else {
      area = html`<div class="bui-cp-square" style="background-color:${hue}" @pointerdown=${(e) => this.areaDrag(e, 'sv')}>
        <span class="bui-cp-cursor" style="left:${s * 100}%;top:${(1 - v) * 100}%;background:${css3(rgb)}"></span>
      </div>`;
      strip = html`<div class="bui-cp-strip bui-cp-hue" @pointerdown=${(e) => this.areaDrag(e, 'hue')}>
        <span class="bui-cp-cursor" style="left:50%;top:${(1 - h) * 100}%;background:${hue}"></span>
      </div>`;
    }
    const hex = toHex([...rgb, 1]);
    return html`<div class="bui-cp" @pointerdown=${(e) => e.stopPropagation()}>
      <div class="bui-cp-top">${area}${strip}</div>
      <div class="bui-cp-tabs bui-joined-h" role="tablist">${MODES.map((m) => html`
        <button class="bui-w bui-radio bui-center ${m === this.mode ? 'bui-on' : ''}" role="tab" aria-selected=${m === this.mode}
            @click=${() => {
              this.mode = lastMode = m;
              this.draw();
            }}><span class="bui-txt">${m}</span></button>`)}
      </div>
      ${this.sliders()}
      <div class="bui-cp-hexrow">
        <label class="bui-w bui-textw bui-cp-hex">
          <span class="bui-cp-hex-l">Hex:</span>
          <input class="bui-input" .value=${this.hexDraft ?? hex} spellcheck="false" maxlength="9"
              @focus=${(e) => e.target.select()}
              @input=${(e) => (this.hexDraft = e.target.value)}
              @keydown=${(e) => {
                e.stopPropagation();
                if (e.key === 'Enter') e.target.blur();
                else if (e.key === 'Escape') {
                  this.hexDraft = null;
                  e.target.value = hex;
                  e.target.blur();
                }
              }}
              @blur=${(e) => {
                const t = e.target.value.trim().replace(/^#?/, '#');
                this.hexDraft = null;
                if (/^#[0-9a-f]{3}$/i.test(t)) {
                  const x = t.slice(1).split('').map((c) => c + c).join('');
                  this.setRgb(toRgba('#' + x).slice(0, 3));
                  this.push(true);
                } else if (/^#[0-9a-f]{6}([0-9a-f]{2})?$/i.test(t)) {
                  const c = toRgba(t);
                  this.setRgb(c.slice(0, 3));
                  if (t.length === 9 && this.swatch.p.alpha) this.a = c[3];
                  this.push(true);
                } else {
                  this.draw();
                }
              }}>
        </label>
        <button class="bui-w bui-cp-eye" aria-label="Eyedropper" data-tip="Sample a color from the screen"
            ?disabled=${!('EyeDropper' in window)} @click=${() => this.eyedrop()}>${icon('EYEDROPPER')}</button>
      </div>
    </div>`;
  }
  async eyedrop() {
    try {
      const res = await new window.EyeDropper().open();
      this.setRgb(toRgba(res.sRGBHex).slice(0, 3));
      this.push(true);
    } catch {
      // cancelled
    }
  }
}

class ColorSwatchElement extends BuiElement {
  writeColor(rgba, commit) {
    const raw = this.val('value', [0.5, 0.5, 0.5, 1]);
    const alpha = !!this.p.alpha;
    let out;
    if (typeof raw === 'string') {
      out = toHex(rgba);
      if (alpha || raw.replace('#', '').length === 8) {
        out += Math.round(clamp(rgba[3], 0, 1) * 255).toString(16).padStart(2, '0').toUpperCase();
      }
    } else {
      const r = (x) => Number(x.toFixed(4));
      out = rgba.map(r);
      if (Array.isArray(raw) && raw.length === 3 && !alpha) out = out.slice(0, 3);
    }
    this.set('value', out);
    if (commit) this.fire({value: out, hex: toHex(rgba)});
  }
  open(e) {
    if (!this.enabled) return;
    const btn = e.currentTarget;
    popup(btn, (box, close) => {
      box.classList.add('bui-cp-pop');
      new ColorPicker(this, close).mount(box);
    }, {placement: 'below'});
  }
  render() {
    const p = this.p;
    const c = toRgba(this.val('value', [0.5, 0.5, 0.5, 1]));
    const opaque = css3(c.slice(0, 3));
    const showAlpha = !!p.alpha && c[3] < 0.999;
    const btn = html`<button class="bui-w bui-swatch" aria-label=${(p.label ? p.label + ' ' : '') + toHex(c)}
        @click=${(e) => this.open(e)}>
      <span class="bui-swatch-solid" style="background:${opaque}"></span>
      ${showAlpha ? html`<span class="bui-swatch-alpha"><span style="background:${cssColor(c)}"></span></span>` : nothing}
    </button>`;
    return labeled(p.label, btn);
  }
}

// ---------------------------------------------------------------- IDSelector

class IDSelectorElement extends BuiElement {
  constructor() {
    super();
    this.extra = [];
  }
  items() {
    const base = Array.isArray(this.p.items) ? this.p.items.map(String) : [];
    return [...base, ...this.extra.filter((x) => !base.includes(x))];
  }
  browse(e) {
    if (!this.enabled) return;
    const btn = e.currentTarget;
    const ic = this.p.icon || 'MESH_DATA';
    const items = this.items().map((n) => ({label: n, value: n, icon: ic}));
    const cur = this.val('value', '');
    popup(btn, (box, close) => {
      const menu = menuList(box, {
        title: '',
        items,
        onPick: (it) => {
          close();
          this.usersOverride = undefined;
          this.set('value', it.value);
          this.fire({op: 'select', value: it.value});
        },
      });
      menu.classList.add('bui-id-menu');
      const hint = document.createElement('div');
      hint.className = 'bui-id-search';
      hint.innerHTML = '<span class="bui-icon">search</span><span>Type to search…</span>';
      menu.prepend(hint);
      markActive(menu, items, cur);
    });
  }
  newName() {
    const all = this.items();
    const cur = this.val('value', '') || this.items()[0] || 'Data';
    const stem = cur.replace(/\.\d{3}$/, '');
    for (let i = 1; i < 1000; i++) {
      const n = `${stem}.${String(i).padStart(3, '0')}`;
      if (!all.includes(n)) return n;
    }
    return `${stem}.new`;
  }
  doNew() {
    const n = this.newName();
    this.extra.push(n);
    this.usersOverride = 1;
    this.set('value', n);
    this.fire({op: 'new', value: n});
  }
  rename(inp) {
    const old = this.val('value', '');
    const n = inp.value.trim();
    if (!n || n === old) {
      inp.value = old;
      return;
    }
    const i = this.extra.indexOf(old);
    if (i >= 0) this.extra[i] = n;
    else this.extra.push(n);
    this.set('value', n);
    this.fire({op: 'rename', value: n, previous: old});
  }
  render() {
    const p = this.p;
    const ic = p.icon || 'MESH_DATA';
    const cur = String(this.val('value', '') ?? '');
    const fake = !!this.val('fakeUser', false);
    const users = (this.usersOverride ?? (typeof p.users === 'number' ? p.users : 1)) + (fake ? 1 : 0);
    const browse = html`<button class="bui-w bui-id-browse" aria-haspopup="menu" data-tip="Browse data to be linked"
        @click=${(e) => this.browse(e)}>${icon(ic)}${icon('DOWNARROW_HLT', 'bui-caret')}</button>`;
    if (!cur) {
      return html`<div class="bui-idsel bui-joined-h">
        ${browse}
        <button class="bui-w bui-center bui-id-new bui-id-newtext" @click=${() => this.doNew()}>
          ${icon('ADD')}<span class="bui-txt">New</span></button>
      </div>`;
    }
    return html`<div class="bui-idsel bui-joined-h">
      ${browse}
      <label class="bui-w bui-id-name">
        <input class="bui-input" .value=${cur} spellcheck="false" ?disabled=${!this.enabled}
            @keydown=${(e) => {
              e.stopPropagation();
              if (e.key === 'Enter') e.target.blur();
              else if (e.key === 'Escape') {
                e.target.value = cur;
                e.target.blur();
              }
            }}
            @blur=${(e) => this.rename(e.target)}>
      </label>
      ${users > 1 ? html`<button class="bui-w bui-center bui-id-users" data-tip="Display number of users of this data (click to make a single-user copy)"
          @click=${() => this.doNew()}><span class="bui-txt">${users}</span></button>` : nothing}
      <button class="bui-w bui-center bui-id-fake ${fake ? 'bui-on' : ''}" aria-pressed=${fake}
          data-tip="Fake User: save this data-block even if it has no users"
          @click=${() => {
            this.set('fakeUser', !fake);
            this.fire({op: 'fake_user', value: cur, fakeUser: !fake});
          }}>${icon(fake ? 'FAKE_USER_ON' : 'FAKE_USER_OFF')}</button>
      <button class="bui-w bui-center bui-id-new" data-tip="New: duplicate the data-block" @click=${() => this.doNew()}>
        ${icon('DUPLICATE')}</button>
      <button class="bui-w bui-center bui-id-x" data-tip="Unlink data-block" @click=${() => {
        this.set('value', '');
        this.fire({op: 'unlink', value: cur});
      }}>${icon('PANEL_CLOSE')}</button>
    </div>`;
  }
}

export const IMPLS = [
  impl('Dropdown', DropdownElement),
  impl('EnumRow', EnumRowElement),
  impl('ColorSwatch', ColorSwatchElement),
  impl('IDSelector', IDSelectorElement),
];
