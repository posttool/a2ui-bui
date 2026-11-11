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

// Value components: NumberField, NumberSlider, VectorField, TextField,
// TextArea, SearchField, HotkeyField, Checkbox, Toggle, Decorator, PathField.
//
// Number widgets share NumCtl (drag / step / type / wheel / keys, Blender
// interaction rules), which choice.js also uses for the color picker sliders.

import {BuiElement, clamp, drag, fmtNum, html, impl, nothing} from '../base.js';
import {icon} from '../icons.js';

// ------------------------------------------------------------ number math

/** Evaluates a typed number: "2*pi", "90/4", "1e3", "1.5 m", "45°". */
export function evalNumber(text) {
  let s = String(text ?? '').trim().toLowerCase().replace(/,/g, '.');
  s = s.replace(/°|deg|%|\b(mm|cm|km|m|w|s|ms|px|kg|g)\b/g, '');
  s = s.replace(/\bpi\b/g, `(${Math.PI})`).replace(/\btau\b/g, `(${Math.PI * 2})`).replace(/\^/g, '**');
  s = s.replace(/\bsqrt\b/g, 'Math.sqrt').replace(/\b(sin|cos|tan|abs|floor|ceil|round|log|exp)\b/g, 'Math.$1');
  const bare = s.replace(/Math\.[a-z]+/g, '');
  if (!/^[\d+\-*/().e\s]*$/.test(bare) || !s.trim()) return NaN;
  try {
    // eslint-disable-next-line no-new-func
    const v = Function(`"use strict"; return (${s});`)();
    return typeof v === 'number' ? v : NaN;
  } catch {
    return NaN;
  }
}

const DECIMALS = (x) => {
  const s = String(x);
  return s.includes('.') ? s.split('.')[1].length : 0;
};

/** Normalized number options from props. */
export function numOpts(p, extra = {}) {
  const o = {
    min: typeof p.min === 'number' ? p.min : undefined,
    max: typeof p.max === 'number' ? p.max : undefined,
    integer: !!p.integer,
    suffix: typeof p.suffix === 'string' ? p.suffix : '',
    ...extra,
  };
  o.step = typeof p.step === 'number' && p.step > 0 ? p.step : (o.integer ? 1 : (o.suffix === '°' ? 1 : 0.1));
  o.precision = typeof p.precision === 'number' ? p.precision : (o.integer ? 0 : Math.max(3, DECIMALS(o.step)));
  // Blender strips trailing zeros from unit values ("0 m", "1.25 m", "90°").
  o.trim = typeof p.precision !== 'number' && /^(m|mm|cm|km|°|s|ms)$/.test(o.suffix);
  return o;
}

function snapInc(o, fine) {
  let inc;
  if (o.integer) inc = 10;
  else if (o.suffix === '°') inc = 10;
  else if (o.min !== undefined && o.max !== undefined && o.max - o.min <= 2) inc = 0.1;
  else inc = 1;
  if (fine) inc = o.integer ? 1 : inc / 10;
  return inc;
}

function finish(v, o) {
  let n = Number(v);
  if (!Number.isFinite(n)) return n;
  n = clamp(n, o.min, o.max);
  if (o.integer) n = Math.round(n);
  else n = Number(n.toFixed(Math.min(10, (o.precision ?? 3) + 3)));
  return n;
}

// Shared hover target for Blender "keys act on the hovered field" behavior.
let hovered = null;
let clip = null;
document.addEventListener('keydown', (e) => {
  if (!hovered || !hovered.isConnected) return;
  const t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  hovered.hoverKey?.(e);
}, true);

/**
 * Controller for one number widget (field or slider). `update()` re-renders
 * the owner. render(opts) returns the widget template.
 *   opts: {value, label, min, max, step, precision, integer, suffix, slider,
 *          cls, onInput(v), onCommit(v), onReset?(), group?: () => NumCtl[]}
 */
export class NumCtl {
  constructor(update) {
    this.update = update;
    this.editing = false;
    this.draft = '';
    this.opts = {};
    this.initial = undefined;
    this.el = null;
  }

  get value() {
    return Number(this.opts.value) || 0;
  }

  format(v = this.value) {
    if (!this.opts.trim) return fmtNum(v, this.opts);
    const n = Number(Number(v).toFixed(this.opts.precision));
    return fmtNum(Object.is(n, -0) ? 0 : n, {...this.opts, precision: Math.min(this.opts.precision, DECIMALS(n))});
  }

  input(v) {
    this.opts.onInput?.(finish(v, this.opts));
  }

  commit(v) {
    const n = finish(v, this.opts);
    if (!Number.isFinite(n)) return;
    this.opts.onInput?.(n);
    this.opts.onCommit?.(n);
  }

  stepBy(dir) {
    const o = this.opts;
    this.commit(this.value + dir * o.step);
  }

  startEdit() {
    if (this.opts.disabled) return;
    this.editing = true;
    const v = this.value;
    this.draft = this.opts.integer ? String(Math.round(v)) : String(Number(v.toFixed(this.opts.precision + 3)));
    this.update();
    requestAnimationFrame(() => {
      const inp = this.el?.querySelector('input');
      if (inp) {
        inp.focus();
        inp.select();
      }
    });
  }

  endEdit(apply, inp) {
    if (!this.editing) return;
    this.editing = false;
    if (apply) {
      const n = evalNumber(inp ? inp.value : this.draft);
      if (Number.isFinite(n)) this.commit(n);
    }
    this.update();
  }

  hoverKey(e) {
    const o = this.opts;
    if (this.editing || o.disabled) return;
    const mod = e.ctrlKey || e.metaKey;
    if (e.key === 'Backspace' || e.key === 'Delete') {
      e.preventDefault();
      if (o.onReset) o.onReset();
      else this.commit(this.initial ?? 0);
    } else if (e.key === '-' && !mod) {
      e.preventDefault();
      this.commit(-this.value);
    } else if (mod && e.key.toLowerCase() === 'c') {
      clip = this.value;
      navigator.clipboard?.writeText(String(this.value)).catch(() => {});
    } else if (mod && e.key.toLowerCase() === 'v') {
      e.preventDefault();
      const apply = (t) => {
        const n = evalNumber(t);
        if (Number.isFinite(n)) this.commit(n);
      };
      if (navigator.clipboard?.readText) {
        navigator.clipboard.readText().then(apply, () => clip != null && apply(String(clip)));
      } else if (clip != null) {
        apply(String(clip));
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      this.startEdit();
    }
  }

  onWheel(e) {
    if (!(e.ctrlKey || e.metaKey) || this.editing || this.opts.disabled) return;
    e.preventDefault();
    this.stepBy(e.deltaY < 0 ? 1 : -1);
  }

  onDown(e) {
    const o = this.opts;
    if (this.editing || e.button !== 0 || o.disabled) return;
    e.preventDefault();
    const box = e.currentTarget;
    box.focus?.({preventScroll: true});
    const rect = box.getBoundingClientRect();
    const u = rect.height;
    const v0 = this.value;
    const group = (e.altKey && o.group) ? o.group() : [this];
    const starts = group.map((c) => c.value);
    let cancelled = false;
    let last = v0;
    const esc = (ev) => {
      if (ev.key !== 'Escape') return;
      cancelled = true;
      group.forEach((c, i) => c.input(starts[i]));
    };
    window.addEventListener('keydown', esc, true);
    box.classList.add('bui-dragging');
    const valueFor = (dx, ev) => {
      if (o.slider && o.min !== undefined && o.max !== undefined) {
        const range = o.max - o.min;
        const w = Math.max(1, rect.width);
        return v0 + (dx / w) * range * (ev.shiftKey ? 0.05 : 1);
      }
      // Blender: about one click step per few pixels; Shift = 1/10.
      const perPx = o.integer ? o.step / 4 : o.step / 10;
      let v = v0 + dx * perPx * (ev.shiftKey ? 0.1 : 1);
      if (ev.ctrlKey || ev.metaKey) {
        const inc = snapInc(o, ev.shiftKey);
        v = Math.round(v / inc) * inc;
      }
      return v;
    };
    drag(e, {
      onMove: (dx, dy, ev) => {
        if (cancelled) return;
        let v = valueFor(dx, ev);
        if (o.slider && (ev.ctrlKey || ev.metaKey)) {
          const inc = snapInc(o, ev.shiftKey);
          v = Math.round(v / inc) * inc;
        }
        last = finish(v, o);
        const delta = last - v0;
        group.forEach((c, i) => (c === this ? c.input(last) : c.input(starts[i] + delta)));
      },
      onEnd: (moved, ev) => {
        window.removeEventListener('keydown', esc, true);
        box.classList.remove('bui-dragging');
        if (cancelled) return;
        if (moved) {
          const delta = last - v0;
          group.forEach((c, i) => (c === this ? c.commit(last) : c.commit(starts[i] + delta)));
          return;
        }
        // Click: arrows step, elsewhere type a value (Blender click-to-edit).
        const x = ev.clientX - rect.left;
        if (!o.slider && x < u * 0.75) this.stepBy(-1);
        else if (!o.slider && x > rect.width - u * 0.75) this.stepBy(1);
        else this.startEdit();
      },
    });
  }

  render(opts) {
    this.opts = {...opts};
    if (this.initial === undefined && Number.isFinite(Number(opts.value))) this.initial = Number(opts.value);
    const o = this.opts;
    const label = o.label ?? '';
    const cls = `bui-w bui-num ${o.slider ? 'bui-numslider' : ''} ${label ? 'bui-has-label' : ''} ${o.cls || ''}`;
    if (this.editing) {
      return html`<div class="${cls} bui-num-editing">
        <input class="bui-input" .value=${this.draft} spellcheck="false"
            @input=${(e) => (this.draft = e.target.value)}
            @keydown=${(e) => {
              e.stopPropagation();
              if (e.key === 'Enter') this.endEdit(true, e.target);
              else if (e.key === 'Escape') this.endEdit(false, e.target);
              else if (e.key === 'Tab') {
                e.preventDefault();
                this.endEdit(true, e.target);
                this.opts.onTab?.(e.shiftKey ? -1 : 1);
              }
            }}
            @blur=${(e) => this.endEdit(true, e.target)}>
      </div>`;
    }
    let fill = nothing;
    if (o.slider && o.min !== undefined && o.max !== undefined && o.max > o.min) {
      const f = clamp((this.value - o.min) / (o.max - o.min), 0, 1);
      fill = html`<span class="bui-numslider-fill" style="width:${(f * 100).toFixed(3)}%"></span>`;
    }
    const val = this.format();
    return html`<div class=${cls} tabindex=${o.disabled ? -1 : 0} role="spinbutton"
        aria-valuenow=${this.value} aria-label=${label || nothing}
        @pointerdown=${(e) => this.onDown(e)}
        @pointerenter=${() => (hovered = this)}
        @pointerleave=${() => hovered === this && (hovered = null)}
        @wheel=${(e) => this.onWheel(e)}
        @dblclick=${() => this.startEdit()}
        @keydown=${(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this.startEdit();
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault();
            this.stepBy(-1);
          } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault();
            this.stepBy(1);
          }
        }}>
      ${fill}
      ${o.slider ? nothing : html`<span class="bui-num-arrow bui-num-arrow-l">${icon('TRIA_LEFT')}</span>`}
      ${label ? html`<span class="bui-num-l">${label}</span><span class="bui-num-colon">:</span>` : nothing}
      <span class="bui-num-v">${val}</span>
      ${o.slider ? nothing : html`<span class="bui-num-arrow bui-num-arrow-r">${icon('TRIA_RIGHT')}</span>`}
    </div>`;
  }
}

/** Grabs the rendered widget element after each update. */
function bindEl(host, ctl, sel) {
  ctl.el = host.querySelector(sel);
}

// --------------------------------------------------------------- NumberField

class NumberFieldElement extends BuiElement {
  constructor() {
    super();
    this.ctl = new NumCtl(() => this.requestUpdate());
  }
  render() {
    const p = this.p;
    return this.ctl.render({
      ...numOpts(p),
      value: this.val('value', 0),
      label: p.label,
      disabled: !this.enabled,
      onInput: (v) => this.set('value', v),
      onCommit: (v) => this.fire({value: v}),
    });
  }
  updated() {
    bindEl(this, this.ctl, '.bui-num');
  }
}

class NumberSliderElement extends BuiElement {
  constructor() {
    super();
    this.ctl = new NumCtl(() => this.requestUpdate());
  }
  render() {
    const p = this.p;
    const o = numOpts(p);
    if (o.min === undefined) o.min = 0;
    if (o.max === undefined) o.max = 1;
    if (typeof p.precision !== 'number') o.precision = 3;
    return this.ctl.render({
      ...o,
      slider: true,
      value: this.val('value', 0),
      label: p.label,
      disabled: !this.enabled,
      onInput: (v) => this.set('value', v),
      onCommit: (v) => this.fire({value: v}),
    });
  }
  updated() {
    bindEl(this, this.ctl, '.bui-num');
  }
}

// --------------------------------------------------------------- Decorator

const DECOR_STATES = ['none', 'animated', 'keyframe', 'driven', 'changed'];

/** The decorator glyph for a keyframe state (inline SVG, Blender shapes). */
export function decorGlyph(state) {
  const s = DECOR_STATES.includes(state) ? state : 'none';
  if (s === 'none') {
    return html`<svg class="bui-decor-svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="2.2" class="bui-decor-dot"/></svg>`;
  }
  if (s === 'driven') {
    return html`<svg class="bui-decor-svg" viewBox="0 0 16 16"><path d="M8 3.2 12.8 8 8 12.8 3.2 8Z" class="bui-decor-shape"/><circle cx="8" cy="8" r="1.4" class="bui-decor-hole"/></svg>`;
  }
  return html`<svg class="bui-decor-svg" viewBox="0 0 16 16"><path d="M8 3 13 8 8 13 3 8Z" class="bui-decor-shape"/></svg>`;
}

/** Next state when the decorator is clicked (insert / delete keyframe). */
export function decorNext(state) {
  if (state === 'driven') return 'driven';
  return state === 'keyframe' ? 'none' : 'keyframe';
}

class DecoratorElement extends BuiElement {
  state() {
    const s = this.val('state', undefined) ?? this._localState ?? this.p.value ?? 'none';
    return DECOR_STATES.includes(s) ? s : 'none';
  }
  click() {
    const next = decorNext(this.state());
    if (this.raw('state') !== undefined) this.set('state', next);
    else this._localState = next;
    this.requestUpdate();
    this.fire({state: next});
  }
  render() {
    const s = this.state();
    const tip = this.p.label ? `${this.p.label}: ${s === 'none' ? 'Insert Keyframe' : s}` : nothing;
    const btn = html`<button class="bui-decor bui-decor-${s}" aria-label=${tip}
        data-tip=${this.p.description ? nothing : tip} @click=${() => this.click()}>${decorGlyph(s)}</button>`;
    if (!this.p.label) return btn;
    return html`<span class="bui-decor-row"><span class="bui-label-text">${this.p.label}</span>${btn}</span>`;
  }
}

// --------------------------------------------------------------- VectorField

class VectorFieldElement extends BuiElement {
  constructor() {
    super();
    this.ctls = [];
    this.decor = [];
  }
  vec() {
    const v = this.val('value', [0, 0, 0]);
    return Array.isArray(v) ? v.map((x) => Number(x) || 0) : [0, 0, 0];
  }
  setAxis(i, n) {
    const v = this.vec();
    v[i] = n;
    this.set('value', v);
    return v;
  }
  render() {
    const p = this.p;
    const v = this.vec();
    const axes = (typeof p.axes === 'string' && p.axes ? p.axes : 'XYZW').split('');
    while (this.ctls.length < v.length) this.ctls.push(new NumCtl(() => this.requestUpdate()));
    while (this.decor.length < v.length) this.decor.push('none');
    const o = numOpts(p);
    const colors = {X: 'x', Y: 'y', Z: 'z', W: 'w'};
    return html`<div class="bui-vec">
      ${p.label ? html`<div class="bui-vec-label">${p.label}:</div>` : nothing}
      <div class="bui-vec-body">
        <div class="bui-vec-col bui-joined-v">${v.map((x, i) => this.ctls[i].render({
          ...o,
          value: x,
          label: axes[i] ?? String(i),
          disabled: !this.enabled,
          cls: `bui-vec-f bui-axis-${colors[axes[i]] || 'n'} ${p.decorators ? `bui-anim-${this.decor[i]}` : ''}`,
          group: () => this.ctls.slice(0, v.length),
          onInput: (n) => this.setAxis(i, n),
          onCommit: () => this.fire({value: this.vec(), index: i}),
          onTab: (d) => this.ctls[(i + d + v.length) % v.length].startEdit(),
        }))}</div>
        ${p.decorators ? html`<div class="bui-vec-decor">${v.map((_, i) => html`
          <button class="bui-decor bui-decor-${this.decor[i]}" @click=${() => {
            this.decor[i] = decorNext(this.decor[i]);
            this.requestUpdate();
            this.fire({index: i, state: this.decor[i], value: this.vec()});
          }}>${decorGlyph(this.decor[i])}</button>`)}</div>` : nothing}
      </div>
    </div>`;
  }
  updated() {
    const els = this.querySelectorAll('.bui-vec-col > .bui-num');
    this.ctls.forEach((c, i) => (c.el = els[i] || null));
  }
}

// --------------------------------------------------------------- text fields

export function labeled(label, body, cls = '') {
  if (!label) return body;
  return html`<div class="bui-vlabeled ${cls}"><span class="bui-vlabel">${label}</span><div class="bui-vlabeled-f">${body}</div></div>`;
}

class TextFieldElement extends BuiElement {
  commit(inp, fire) {
    const v = inp.value;
    if (v !== this.val('value', '')) this.set('value', v);
    if (fire) this.fire({value: v});
  }
  render() {
    const p = this.p;
    const v = this.val('value', '');
    return labeled(p.label, html`<label class="bui-w bui-textw">
      ${icon(p.icon)}
      <input class="bui-input" .value=${String(v ?? '')} placeholder=${p.placeholder ?? ''} spellcheck="false"
          ?disabled=${!this.enabled}
          @keydown=${(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') {
              this.commit(e.target, true);
              e.target.blur();
            } else if (e.key === 'Escape') {
              e.target.value = String(this.val('value', '') ?? '');
              e.target.blur();
            }
          }}
          @blur=${(e) => this.commit(e.target, false)}>
    </label>`);
  }
}

class TextAreaElement extends BuiElement {
  render() {
    const p = this.p;
    const rows = typeof p.rows === 'number' ? Math.max(1, Math.round(p.rows)) : 4;
    return html`<div class="bui-textarea-wrap">
      ${p.label ? html`<div class="bui-vec-label">${p.label}:</div>` : nothing}
      <textarea class="bui-textarea ${p.monospace ? 'bui-mono' : ''}" rows=${rows} spellcheck="false"
          ?disabled=${!this.enabled}
          style="height: calc(${rows} * 1.45em + var(--bui-u) * .5)"
          .value=${String(this.val('value', '') ?? '')}
          @keydown=${(e) => {
            e.stopPropagation();
            if (e.key === 'Tab') {
              e.preventDefault();
              const t = e.target, s = t.selectionStart;
              t.setRangeText('    ', s, t.selectionEnd, 'end');
            }
          }}
          @change=${(e) => this.set('value', e.target.value)}></textarea>
    </div>`;
  }
}

class SearchFieldElement extends BuiElement {
  render() {
    const p = this.p;
    const v = String(this.val('value', '') ?? '');
    return html`<label class="bui-w bui-textw bui-search">
      ${icon('VIEWZOOM', 'bui-search-ic')}
      <input class="bui-input" .value=${v} placeholder=${p.placeholder ?? 'Search'} spellcheck="false"
          ?disabled=${!this.enabled}
          @input=${(e) => this.set('value', e.target.value)}
          @keydown=${(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') this.fire({value: e.target.value});
            else if (e.key === 'Escape') {
              this.set('value', '');
              e.target.blur();
              this.fire({value: ''});
            }
          }}>
      ${v ? html`<button class="bui-search-x" aria-label="Clear" @click=${(e) => {
        e.preventDefault();
        this.set('value', '');
        this.fire({value: ''});
      }}>${icon('PANEL_CLOSE')}</button>` : nothing}
    </label>`;
  }
}

const KEYNAMES = {' ': 'Space', 'ArrowUp': 'Up Arrow', 'ArrowDown': 'Down Arrow', 'ArrowLeft': 'Left Arrow',
  'ArrowRight': 'Right Arrow', 'Escape': 'Esc', 'Backspace': 'Backspace', 'Delete': 'Delete', 'Enter': 'Return',
  'Tab': 'Tab', 'PageUp': 'Page Up', 'PageDown': 'Page Down'};

class HotkeyFieldElement extends BuiElement {
  record(e) {
    if (!this.enabled) return;
    this.recording = true;
    this.requestUpdate();
    const btn = e.currentTarget;
    const onKey = (ev) => {
      if (['Control', 'Shift', 'Alt', 'Meta', 'OS'].includes(ev.key)) return;
      ev.preventDefault();
      ev.stopPropagation();
      stop();
      if (ev.key === 'Escape' && !ev.ctrlKey && !ev.shiftKey && !ev.altKey) return;
      const parts = [];
      if (ev.ctrlKey) parts.push('Ctrl');
      if (ev.shiftKey) parts.push('Shift');
      if (ev.altKey) parts.push('Alt');
      if (ev.metaKey) parts.push('OS');
      let k = KEYNAMES[ev.key] || (ev.code.startsWith('Key') ? ev.code.slice(3) :
          ev.code.startsWith('Digit') ? ev.code.slice(5) : ev.key.length === 1 ? ev.key.toUpperCase() : ev.key);
      if (ev.code.startsWith('Numpad')) k = 'Numpad ' + ev.code.slice(6);
      parts.push(k);
      const v = parts.join(' ');
      this.set('value', v);
      this.fire({value: v});
    };
    const onDown = (ev) => {
      if (btn.contains(ev.target)) return;
      stop();
    };
    const stop = () => {
      this.recording = false;
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener('pointerdown', onDown, true);
      this.requestUpdate();
    };
    window.addEventListener('keydown', onKey, true);
    setTimeout(() => window.addEventListener('pointerdown', onDown, true), 0);
  }
  render() {
    const p = this.p;
    const v = String(this.val('value', '') ?? '');
    return labeled(p.label, html`<button class="bui-w bui-center bui-hotkey ${this.recording ? 'bui-sel' : ''}"
        @click=${(e) => !this.recording && this.record(e)}>
      <span class="bui-txt">${this.recording ? 'Press a key' : (v || 'None')}</span>
    </button>`);
  }
}

class PathFieldElement extends BuiElement {
  commit(inp) {
    if (inp.value !== this.val('value', '')) this.set('value', inp.value);
  }
  render() {
    const p = this.p;
    const v = String(this.val('value', '') ?? '');
    return labeled(p.label, html`<div class="bui-path bui-joined-h">
      <label class="bui-w bui-textw">
        <input class="bui-input" .value=${v} spellcheck="false" ?disabled=${!this.enabled}
            placeholder=${p.directory ? '//' : ''}
            @keydown=${(e) => {
              e.stopPropagation();
              if (e.key === 'Enter') {
                this.commit(e.target);
                e.target.blur();
              } else if (e.key === 'Escape') {
                e.target.value = v;
                e.target.blur();
              }
            }}
            @blur=${(e) => this.commit(e.target)}>
      </label>
      <button class="bui-w bui-path-btn" aria-label=${p.directory ? 'Browse folder' : 'Browse file'}
          data-tip=${p.directory ? 'Open a directory browser' : 'Open a file browser'}
          @click=${() => this.fire({value: this.val('value', ''), op: 'browse'})}>
        ${icon('FILE_FOLDER')}
      </button>
    </div>`);
  }
}

// --------------------------------------------------- Checkbox and Toggle

// Drag across several checkboxes / toggles to set them all (Blender).
function startDragToggle(e, el, target) {
  const seen = new Set([el]);
  const move = (ev) => {
    const hit = document.elementFromPoint(ev.clientX, ev.clientY)?.closest?.('bui-checkbox, bui-toggle');
    if (!hit || seen.has(hit) || typeof hit.applyDrag !== 'function') return;
    seen.add(hit);
    hit.applyDrag(target);
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

class BoolElement extends BuiElement {
  applyDrag(v) {
    if (!this.enabled || !!this.val('value', false) === v) return;
    this.set('value', v);
    this.fire({value: v});
  }
  down(e) {
    if (e.button !== 0 || !this.enabled) return;
    e.preventDefault();
    const v = !this.val('value', false);
    this.set('value', v);
    this.fire({value: v});
    startDragToggle(e, this, v);
  }
  key(e) {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      this.applyDrag(!this.val('value', false));
    }
  }
}

class CheckboxElement extends BoolElement {
  render() {
    const on = !!this.val('value', false);
    const label = this.p.label;
    return html`<div class="bui-check ${on ? 'bui-on' : ''}" role="checkbox" aria-checked=${on} tabindex="0"
        @pointerdown=${(e) => this.down(e)} @keydown=${(e) => this.key(e)}>
      <span class="bui-check-box">${on ? html`<svg viewBox="0 0 16 16" class="bui-check-mark"><path d="M3.6 8.4 6.6 11.3 12.4 4.9"/></svg>` : nothing}</span>
      ${label ? html`<span class="bui-check-l">${label}</span>` : nothing}
    </div>`;
  }
}

class ToggleElement extends BoolElement {
  render() {
    const p = this.p;
    const on = !!this.val('value', false);
    const ic = on && p.iconOn ? p.iconOn : p.icon;
    const emboss = p.emboss !== false;
    const iconOnly = !p.label;
    return html`<div class="bui-w bui-toggle ${on ? 'bui-on' : ''} ${emboss ? '' : 'bui-noemboss'} ${iconOnly ? 'bui-icon-only' : ''} bui-center"
        role="switch" aria-pressed=${on} aria-checked=${on} tabindex="0"
        @pointerdown=${(e) => this.down(e)} @keydown=${(e) => this.key(e)}>
      ${icon(ic)}${p.label ? html`<span class="bui-txt">${p.label}</span>` : nothing}
    </div>`;
  }
}

export const IMPLS = [
  impl('NumberField', NumberFieldElement),
  impl('NumberSlider', NumberSliderElement),
  impl('VectorField', VectorFieldElement),
  impl('TextField', TextFieldElement),
  impl('TextArea', TextAreaElement),
  impl('SearchField', SearchFieldElement),
  impl('HotkeyField', HotkeyFieldElement),
  impl('Checkbox', CheckboxElement),
  impl('Toggle', ToggleElement),
  impl('Decorator', DecoratorElement),
  impl('PathField', PathFieldElement),
];
