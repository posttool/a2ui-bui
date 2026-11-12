/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Buttons & feedback: Button, IconButton, Popover, MenuButton, MenuItem,
// Label, Image, Video, ProgressBar, Separator, Spacer.

import {BuiElement, clamp, cssColor, html, impl, nothing, popup} from '../base.js';
import {icon} from '../icons.js';
import {menuList} from './menu_list.js';

/** The shared `.bui-layer` floating layer of the element's `.bui-root`. */
export function layerFor(el) {
  const root = el.closest('.bui-root');
  if (!root) return null;
  let layer = root.querySelector(':scope > .bui-layer');
  if (!layer) {
    layer = document.createElement('div');
    layer.className = 'bui-layer';
    root.appendChild(layer);
  }
  return layer;
}

/**
 * Normalizes raw menu items (strings, {label ...}, {separator}, "-") for
 * menuList(), recursively for submenus.
 */
export function normMenu(items) {
  if (!Array.isArray(items)) return [];
  return items.map((it) => {
    if (it == null) return null;
    if (typeof it !== 'object') {
      const s = String(it);
      return /^-+$/.test(s) ? {separator: true} : {label: s, value: s};
    }
    if (it.separator) return {separator: true};
    const label = String(it.label ?? it.name ?? it.value ?? '');
    const out = {...it, label, value: it.value != null ? String(it.value) : label};
    if (Array.isArray(it.items)) out.items = normMenu(it.items);
    return out;
  }).filter(Boolean);
}

/** Opens a menuList popup under `anchor`; resolves picks through onPick(item). */
export function openMenu(anchor, {title = '', items, onPick, placement = 'below'}) {
  return popup(anchor, (box, close) => menuList(box, {
    title,
    items: normMenu(items),
    onPick: (it) => {
      close();
      onPick?.(it);
    },
  }), {placement});
}

// ------------------------------------------------------------------ Button
class ButtonElement extends BuiElement {
  click(e) {
    if (!this.enabled) return;
    this.fire({});
  }
  render() {
    const p = this.p;
    const emboss = p.emboss !== false;
    const cls = ['bui-w', 'bui-btn', 'bui-center'];
    if (!emboss) cls.push('bui-noemboss');
    if (p.depress) cls.push('bui-sel');
    if (p.alert) cls.push('bui-alert');
    if (p.icon && !p.text) cls.push('bui-btn-icononly');
    return html`<button class=${cls.join(' ')} aria-pressed=${p.depress ? 'true' : 'false'}
        ?disabled=${!this.enabled} @click=${(e) => this.click(e)}>
      ${p.icon ? icon(p.icon) : nothing}
      ${p.text ? html`<span class="bui-txt">${p.text}</span>` : nothing}
    </button>`;
  }
}

class IconButtonElement extends BuiElement {
  render() {
    const p = this.p;
    const emboss = p.emboss === true;
    return html`<button class="bui-w bui-iconbtn bui-center ${emboss ? '' : 'bui-noemboss'}"
        aria-label=${p.description || p.icon || ''} ?disabled=${!this.enabled}
        @click=${() => this.fire({})}>${icon(p.icon)}</button>`;
  }
}

// ----------------------------------------------------------------- Popover
// The panel is rendered by lit inside this element, then moved once into
// the root's floating `.bui-layer` (lit keeps updating the moved node), so
// it is never clipped by overflow:hidden ancestors such as panels or areas.
class PopoverElement extends BuiElement {
  constructor() {
    super();
    this._open = false;
    this._outside = (e) => {
      const panel = this._panel;
      if (!panel || panel.contains(e.target) || this.contains(e.target)) return;
      if (e.target.closest?.('.bui-popup')) return;  // child dropdown menus etc.
      this.close();
    };
    this._esc = (e) => {
      if (e.key === 'Escape' && this._open) {
        if (document.querySelector('.bui-layer .bui-menu:focus-within')) return;
        e.stopPropagation();
        this.close();
      }
    };
    this._place = () => this.place();
  }
  get _panel() {
    return this.__panel || this.querySelector(':scope > .bui-popover-panel');
  }
  toggle() {
    if (this._open) this.close();
    else this.open();
  }
  open() {
    if (!this.enabled) return;
    this._open = true;
    this.requestUpdate();
    setTimeout(() => {
      document.addEventListener('pointerdown', this._outside, true);
      document.addEventListener('keydown', this._esc, true);
      window.addEventListener('resize', this._place);
    }, 0);
  }
  close() {
    if (!this._open) return;
    this._open = false;
    document.removeEventListener('pointerdown', this._outside, true);
    document.removeEventListener('keydown', this._esc, true);
    window.removeEventListener('resize', this._place);
    this.requestUpdate();
  }
  disconnectedCallback() {
    this.close();
    // Bring the portalled panel home so lit's node bookkeeping stays intact.
    if (this.__panel && this.__panel.parentNode !== this) this.appendChild(this.__panel);
    this.__panel = null;
    super.disconnectedCallback();
  }
  place() {
    const panel = this._panel;
    const btn = this.querySelector(':scope > .bui-w');
    const layer = panel?.parentElement;
    if (!panel || !btn || !layer || !this._open) return;
    const ra = btn.getBoundingClientRect();
    const rl = layer.getBoundingClientRect();
    const rb = panel.getBoundingClientRect();
    let x = ra.left - rl.left;
    let y = ra.bottom - rl.top + 2;
    if (y + rb.height > layer.clientHeight - 4 && ra.top - rl.top - rb.height - 2 > 0) y = ra.top - rl.top - rb.height - 2;
    panel.style.left = `${clamp(x, 4, Math.max(4, layer.clientWidth - rb.width - 4))}px`;
    panel.style.top = `${clamp(y, 4, Math.max(4, layer.clientHeight - rb.height - 4))}px`;
  }
  updated(c) {
    super.updated?.(c);
    const panel = this.querySelector(':scope > .bui-popover-panel') || this.__panel;
    if (panel && panel.parentNode === this) {
      const layer = layerFor(this);
      if (layer) {
        layer.appendChild(panel);
        this.__panel = panel;
      }
    }
    if (this._open) {
      this.place();
      requestAnimationFrame(() => this.place());
    }
  }
  render() {
    const p = this.p;
    const open = this._open;
    return html`<button class="bui-w bui-popover-btn ${open ? 'bui-open' : ''}" aria-expanded=${open ? 'true' : 'false'}
        ?disabled=${!this.enabled} @click=${() => this.toggle()}>
      ${p.icon ? icon(p.icon) : nothing}
      ${p.text ? html`<span class="bui-txt">${p.text}</span>` : nothing}
      ${icon('DOWNARROW_HLT', 'bui-caret')}
    </button><div class="bui-popup bui-popover-panel" ?hidden=${!open}>
      <div class="bui-popover-body bui-stack bui-stack-v">${open ? this.kids(p.children) : nothing}</div>
    </div>`;
  }
}

// -------------------------------------------------------------- MenuButton
class MenuButtonElement extends BuiElement {
  constructor() {
    super();
    this._open = false;
  }
  open(e) {
    if (!this.enabled || this._open) return;
    const anchor = e.currentTarget;
    this._open = true;
    this.requestUpdate();
    anchor.addEventListener('bui-popup-closed', () => {
      this._open = false;
      this.requestUpdate();
    }, {once: true});
    this._close = openMenu(anchor, {
      title: '',
      items: this.p.items,
      onPick: (it) => this.fire({item: it.value ?? it.label}),
    });
  }
  render() {
    const p = this.p;
    const caret = p.icon && !p.text;
    return html`<button class="bui-w bui-menubtn ${this._open ? 'bui-open' : ''}" aria-haspopup="menu"
        ?disabled=${!this.enabled} @pointerdown=${(e) => {
      if (this._open) {
        this._close?.();
        return;
      }
      this.open(e);
    }}>
      ${p.icon ? icon(p.icon) : nothing}
      ${p.text ? html`<span class="bui-txt">${p.text}</span>` : nothing}
      ${caret ? icon('DOWNARROW_HLT', 'bui-caret') : nothing}
    </button>`;
  }
}

class MenuItemElement extends BuiElement {
  render() {
    const p = this.p;
    const ic = p.checked ? 'CHECKMARK' : p.icon;
    return html`<div class="bui-menu-item bui-menuitem-row ${this.enabled ? '' : 'bui-off'}" role="menuitem"
        tabindex="0" @click=${() => this.fire({})}
        @keydown=${(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), this.fire({}))}>
      ${ic ? icon(ic) : html`<span class="bui-icon-blank"></span>`}
      <span class="bui-txt">${p.label}</span>
      ${p.shortcut ? html`<span class="bui-shortcut">${p.shortcut}</span>` : nothing}
    </div>`;
  }
}

// ------------------------------------------------------------------- Label
const ROLE = {
  muted: 'var(--bui-text-muted)', accent: 'var(--bui-label-accent, var(--bui-accent))',
  red: 'var(--bui-label-red, var(--bui-red))', green: 'var(--bui-label-green, var(--bui-green))',
  yellow: 'var(--bui-label-yellow, var(--bui-yellow))', orange: 'var(--bui-label-orange, var(--bui-orange))',
};
class LabelElement extends BuiElement {
  render() {
    const p = this.p;
    const color = p.color ? (ROLE[p.color] || cssColor(p.color)) : '';
    const size = p.size || 'normal';
    const align = p.align || 'left';
    return html`<div class="bui-label bui-label-${size} bui-label-${align} ${p.bold ? 'bui-bold' : ''}"
        style=${color ? `color: ${color}` : ''}>
      ${p.icon ? icon(p.icon) : nothing}<span class="bui-label-text" style=${color ? `color: ${color}` : ''}>${p.text ?? ''}</span>
    </div>`;
  }
}

// ------------------------------------------------------------- Image/Video
const heightStyle = (h) => typeof h === 'number' && h > 0 ? `height: calc(var(--bui-u) * ${h});` : '';

class ImageElement extends BuiElement {
  render() {
    const p = this.p;
    const fit = p.fit || 'contain';
    return html`<div class="bui-image ${typeof p.height === 'number' ? 'bui-fixed-h' : ''}" style=${heightStyle(p.height)}>
      <img src=${p.src || ''} alt=${p.alt || ''} draggable="false" style="object-fit: ${fit}"
          @error=${(e) => e.target.classList.add('bui-broken')}>
    </div>`;
  }
}

const fmtTime = (s) => {
  if (!Number.isFinite(s)) return '0:00';
  s = Math.max(0, Math.floor(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

class VideoElement extends BuiElement {
  get video() {
    return this.querySelector('video');
  }
  togglePlay() {
    const v = this.video;
    if (!v) return;
    if (v.paused || v.ended) v.play().catch(() => {});
    else v.pause();
  }
  seek(e) {
    const bar = e.currentTarget;
    const v = this.video;
    if (!v || !Number.isFinite(v.duration)) return;
    const go = (ev) => {
      const r = bar.getBoundingClientRect();
      v.currentTime = clamp((ev.clientX - r.left) / r.width, 0, 1) * v.duration;
      this.requestUpdate();
    };
    go(e);
    try {
      bar.setPointerCapture(e.pointerId);
    } catch {
    }
    const move = (ev) => go(ev);
    const up = () => {
      bar.removeEventListener('pointermove', move);
      bar.removeEventListener('pointerup', up);
      bar.removeEventListener('pointercancel', up);
    };
    bar.addEventListener('pointermove', move);
    bar.addEventListener('pointerup', up);
    bar.addEventListener('pointercancel', up);
  }
  render() {
    const p = this.p;
    const v = this.video;
    const playing = v && !v.paused && !v.ended;
    const dur = v && Number.isFinite(v.duration) ? v.duration : 0;
    const t = v ? v.currentTime : 0;
    const frac = dur ? t / dur : 0;
    const upd = () => this.requestUpdate();
    return html`<div class="bui-video">
      <div class="bui-video-frame ${typeof p.height === 'number' ? 'bui-fixed-h' : ''}" style=${heightStyle(p.height)}
          @click=${() => p.controls && this.togglePlay()}>
        <video src=${p.src || ''} poster=${p.poster || nothing} ?autoplay=${!!p.autoplay} ?loop=${!!p.loop}
            .muted=${!!p.autoplay} playsinline preload="metadata" style="object-fit: ${p.fit || 'contain'}"
            @play=${upd} @pause=${upd} @timeupdate=${upd} @loadedmetadata=${upd} @durationchange=${upd}
            @ended=${() => {
      upd();
      this.fire({});
    }}></video>
        ${p.controls && !playing ? html`<span class="bui-video-big">${icon('PLAY')}</span>` : nothing}
      </div>
      ${p.controls ? html`<div class="bui-video-ctl">
        <button class="bui-w bui-center bui-video-play" aria-label=${playing ? 'Pause' : 'Play'}
            @click=${() => this.togglePlay()}>${icon(playing ? 'PAUSE' : 'PLAY')}</button>
        <div class="bui-video-bar" role="slider" aria-valuemin="0" aria-valuemax=${Math.round(dur)}
            aria-valuenow=${Math.round(t)} @pointerdown=${(e) => this.seek(e)}>
          <div class="bui-video-fill" style="width: ${frac * 100}%"></div>
          <div class="bui-video-head" style="left: ${frac * 100}%"></div>
        </div>
        <span class="bui-video-time">${fmtTime(t)} / ${fmtTime(dur)}</span>
      </div>` : nothing}
    </div>`;
  }
}

// ------------------------------------------------------------ ProgressBar
class ProgressBarElement extends BuiElement {
  render() {
    const p = this.p;
    const v = clamp(Number(p.value) || 0, 0, 1);
    const text = p.text ?? `${Math.round(v * 100)}%`;
    return html`<div class="bui-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100"
        aria-valuenow=${Math.round(v * 100)}>
      <div class="bui-progress-fill" style="width: ${v * 100}%"></div>
      <span class="bui-progress-text">${text}</span>
    </div>`;
  }
}

class SeparatorElement extends BuiElement {
  willUpdate(c) {
    super.willUpdate(c);
    const f = typeof this.p.factor === 'number' ? this.p.factor : 0.5;
    this.style.setProperty('--bui-sep', `calc(var(--bui-u) * ${Math.max(0, f)})`);
    this.classList.toggle('bui-sep-line', !!this.p.line);
  }
  render() {
    return html`<div class="bui-sep-rule"></div>`;
  }
}

class SpacerElement extends BuiElement {
  render() {
    return nothing;
  }
}

export const IMPLS = [
  impl('Button', ButtonElement),
  impl('IconButton', IconButtonElement),
  impl('Popover', PopoverElement),
  impl('MenuButton', MenuButtonElement),
  impl('MenuItem', MenuItemElement),
  impl('Label', LabelElement),
  impl('Image', ImageElement),
  impl('Video', VideoElement),
  impl('ProgressBar', ProgressBarElement),
  impl('Separator', SeparatorElement),
  impl('Spacer', SpacerElement),
];
