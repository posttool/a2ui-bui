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

// Editor widgets: ColorRamp, CurveMapping, NormalBall, Histogram.
//
// Canvas-drawn widgets share CanvasElement (device-pixel canvas sized by a
// ResizeObserver, redrawn on theme/scale changes of the enclosing .bui-root).
// numField() is a small Blender number field used here and by nodes.js.

import {BuiElement, clamp, cssColor, drag, fmtNum, html, impl, nothing, popup, toRgba} from '../base.js';
import {icon} from '../icons.js';
import {menuList} from './menu_list.js';

/**
 * UI unit in px. (base.js unitPx() parses `--bui-u`, which computes to the
 * unresolved "calc(...)" token string, so derive it from --bui-scale.)
 */
export function unitPx(el) {
  const cs = getComputedStyle(el);
  const u = parseFloat(cs.getPropertyValue('--bui-u'));
  if (u && !/calc|var/.test(cs.getPropertyValue('--bui-u'))) return u;
  return 20 * (parseFloat(cs.getPropertyValue('--bui-scale')) || 1);
}

/** Reads a CSS custom property from an element. */
export const themeVar = (el, name, fb = '') => getComputedStyle(el).getPropertyValue(name).trim() || fb;

/* ------------------------------------------------------------ numField */

/** Replaces a field's content with a text input; commit(parsed) on Enter/blur. */
export function editText(field, text, commit, {numeric = true} = {}) {
  if (field.querySelector('input.bui-ed-edit')) return;
  const inp = document.createElement('input');
  inp.className = 'bui-ed-edit';
  inp.value = text;
  field.classList.add('bui-ed-editing');
  field.appendChild(inp);
  inp.focus();
  inp.select();
  let done = false;
  const finish = (ok) => {
    if (done) return;
    done = true;
    field.classList.remove('bui-ed-editing');
    const v = inp.value;
    inp.remove();
    if (!ok) return;
    if (!numeric) return commit(v);
    let n = Number(v);
    if (!Number.isFinite(n)) {
      try {
        // Blender accepts simple expressions in number fields.
        if (/^[\d\s.+\-*/()e]+$/i.test(v)) n = Number(Function(`"use strict";return (${v})`)());
      } catch {
      }
    }
    if (Number.isFinite(n)) commit(n);
  };
  inp.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Enter') finish(true);
    else if (e.key === 'Escape') finish(false);
  });
  inp.addEventListener('blur', () => finish(true));
  inp.addEventListener('pointerdown', (e) => e.stopPropagation());
}

/**
 * A Blender number field (label left, value right; optional slider fill).
 * Drag horizontally to change (Shift fine, Ctrl snap), click to type,
 * Ctrl+wheel to step, Escape during drag cancels.
 */
export function numField({label = '', value = 0, min, max, step, precision, integer = false, slider = false,
                          onLive, onCommit, cls = '', disabled = false}) {
  const lo = typeof min === 'number' ? min : -Infinity;
  const hi = typeof max === 'number' ? max : Infinity;
  const prec = integer ? 0 : (typeof precision === 'number' ? precision : 3);
  const st = typeof step === 'number' ? step : (integer ? 1 : 0.01);
  const fix = (v) => {
    v = clamp(v, lo, hi);
    return integer ? Math.round(v) : Number(v.toFixed(Math.max(prec, 4)));
  };
  const hasRange = Number.isFinite(lo) && Number.isFinite(hi) && hi > lo;
  const frac = slider && hasRange ? clamp((value - lo) / (hi - lo), 0, 1) : 0;
  const down = (e) => {
    if (disabled || e.button !== 0) return;
    e.stopPropagation();
    const field = e.currentTarget;
    const w = field.getBoundingClientRect().width || 100;
    const v0 = Number(value) || 0;
    let cur = v0;
    let cancelled = false;
    const esc = (ev) => {
      if (ev.key === 'Escape') {
        cancelled = true;
        onLive?.(v0);
      }
    };
    window.addEventListener('keydown', esc, true);
    drag(e, {
      onMove: (dx, dy, ev) => {
        if (cancelled) return;
        let per = slider && hasRange ? (hi - lo) / w : (integer ? 1 / 6 : st / 2);
        if (ev.shiftKey) per *= 0.1;
        let v = v0 + dx * per;
        if (ev.ctrlKey) {
          const snap = slider && hasRange ? (hi - lo) / 10 : st * 10;
          v = Math.round(v / snap) * snap;
        }
        cur = fix(v);
        onLive?.(cur);
      },
      onEnd: (moved) => {
        window.removeEventListener('keydown', esc, true);
        if (cancelled) return;
        if (moved) onCommit?.(cur);
        else editText(field, fmtNum(v0, {precision: prec, integer}), (n) => onCommit?.(fix(n)));
      },
    });
  };
  const wheel = (e) => {
    if (disabled || !e.ctrlKey) return;
    e.preventDefault();
    e.stopPropagation();
    onCommit?.(fix((Number(value) || 0) + (e.deltaY < 0 ? 1 : -1) * st * (integer ? 1 : 10)));
  };
  return html`<div class="bui-w bui-ed-num ${slider ? 'bui-ed-slider' : ''} ${cls}" @pointerdown=${down}
      @wheel=${wheel}>
    ${slider && hasRange ? html`<span class="bui-ed-fill" style="width:${frac * 100}%"></span>` : nothing}
    ${label ? html`<span class="bui-ed-num-l">${label}</span>` : nothing}
    <span class="bui-ed-num-v">${fmtNum(value, {precision: prec, integer})}</span>
  </div>`;
}

/* -------------------------------------------------------- canvas base */

class CanvasElement extends BuiElement {
  connectedCallback() {
    super.connectedCallback();
    this._ro = new ResizeObserver(() => this.schedule());
    const root = this.closest('.bui-root');
    if (root) {
      this._mo = new MutationObserver(() => this.schedule());
      this._mo.observe(root, {attributes: true, attributeFilter: ['class', 'style']});
    }
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._ro?.disconnect();
    this._mo?.disconnect();
  }
  updated(c) {
    super.updated?.(c);
    const cv = this.querySelector('canvas.bui-ed-canvas');
    if (cv && cv !== this._observed) {
      if (this._observed) this._ro.unobserve(this._observed);
      this._ro.observe(cv);
      this._observed = cv;
    }
    this.schedule();
  }
  schedule() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = 0;
      const cv = this.querySelector('canvas.bui-ed-canvas');
      if (!cv) return;
      const r = cv.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const dpr = window.devicePixelRatio || 1;
      const W = Math.round(r.width * dpr), H = Math.round(r.height * dpr);
      if (cv.width !== W || cv.height !== H) {
        cv.width = W;
        cv.height = H;
      }
      const ctx = cv.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, r.width, r.height);
      this.draw(ctx, r.width, r.height);
    });
  }
  draw() {}
}

const isLight = (el) => !!el.closest('.bui-theme-light');

/* ----------------------------------------------------------- ColorRamp */

const INTERP = ['Linear', 'Ease', 'Constant', 'B-Spline', 'Cardinal'];

function sortStops(stops) {
  return (Array.isArray(stops) ? stops : [])
      .map((s) => ({pos: clamp(Number(s?.pos) || 0, 0, 1), color: toRgba(s?.color)}));
}

const mix = (a, b, f) => a.map((x, i) => x + (b[i] - x) * f);

/** Evaluates a color ramp at t (Blender BKE_colorband_evaluate, approximated). */
export function evalRamp(stops, t, mode = 'Linear') {
  const s = [...stops].sort((a, b) => a.pos - b.pos);
  if (!s.length) return [0, 0, 0, 1];
  if (t <= s[0].pos) return s[0].color;
  if (t >= s[s.length - 1].pos) return s[s.length - 1].color;
  let i = 0;
  while (i < s.length - 1 && t > s[i + 1].pos) i++;
  const a = s[i], b = s[i + 1];
  const span = b.pos - a.pos;
  let f = span > 1e-6 ? (t - a.pos) / span : 0;
  if (mode === 'Constant') return a.color;
  if (mode === 'Ease') return mix(a.color, b.color, f * f * (3 - 2 * f));
  if (mode === 'Linear') return mix(a.color, b.color, f);
  const p0 = (s[i - 1] || a).color, p3 = (s[i + 2] || b).color;
  let w;
  if (mode === 'B-Spline') {
    const f2 = f * f, f3 = f2 * f;
    w = [(1 - f) ** 3 / 6, (3 * f3 - 6 * f2 + 4) / 6, (-3 * f3 + 3 * f2 + 3 * f + 1) / 6, f3 / 6];
  } else {  // Cardinal (Catmull-Rom)
    const f2 = f * f, f3 = f2 * f;
    w = [-0.5 * f3 + f2 - 0.5 * f, 1.5 * f3 - 2.5 * f2 + 1, -1.5 * f3 + 2 * f2 + 0.5 * f, 0.5 * f3 - 0.5 * f2];
  }
  return a.color.map((_, k) => clamp(w[0] * p0[k] + w[1] * a.color[k] + w[2] * b.color[k] + w[3] * p3[k], 0, 1));
}

function drawChecker(ctx, w, h, size, light) {
  ctx.fillStyle = light ? '#cccccc' : '#666666';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = light ? '#ffffff' : '#999999';
  for (let y = 0, r = 0; y < h; y += size, r++) {
    for (let x = (r % 2) * size; x < w; x += size * 2) ctx.fillRect(x, y, size, size);
  }
}

class ColorRampElement extends CanvasElement {
  constructor() {
    super();
    this._active = 0;
    this._live = null;
  }
  stops() {
    return this._live || sortStops(this.val('stops', []));
  }
  interp() {
    const v = this.val('interpolation', 'Linear');
    return INTERP.includes(v) ? v : 'Linear';
  }
  commit(stops) {
    this._live = null;
    const out = stops.map((s) => ({pos: Number(s.pos.toFixed(4)), color: s.color.map((x) => Number(x.toFixed(4)))}));
    this.set('stops', out);
    this.fire({stops: out, interpolation: this.interp()});
  }
  draw(ctx, w, h) {
    const u = unitPx(this);
    drawChecker(ctx, w, h, Math.max(4, Math.round(u * 0.3)), isLight(this));
    const stops = this.stops();
    const mode = this.interp();
    for (let x = 0; x < w; x++) {
      ctx.fillStyle = cssColor(evalRamp(stops, (x + 0.5) / w, mode));
      ctx.fillRect(x, 0, 1.5, h);
    }
  }
  barPos(e) {
    const r = this.querySelector('.bui-cr-bar').getBoundingClientRect();
    return clamp((e.clientX - r.left) / r.width, 0, 1);
  }
  dragStop(e, idx) {
    if (!this.enabled) return;
    const base = this.stops().map((s) => ({...s}));
    this._active = idx;
    const p0 = base[idx].pos;
    const x0 = this.barPos(e);
    this.requestUpdate();
    drag(e, {
      onMove: (dx, dy, ev) => {
        const next = base.map((s) => ({...s}));
        const d = this.barPos(ev) - x0;
        next[idx].pos = clamp(p0 + (ev.shiftKey ? d * 0.1 : d), 0, 1);
        this._live = next;
        this.requestUpdate();
      },
      onEnd: (moved) => {
        if (moved && this._live) this.commit(this._live);
      },
    });
  }
  barDown(e) {
    if (e.button !== 0 || !this.enabled) return;
    e.preventDefault();
    const t = this.barPos(e);
    const stops = this.stops();
    if (e.ctrlKey) {  // Ctrl+click adds a stop (Blender)
      const next = [...stops, {pos: t, color: evalRamp(stops, t, this.interp())}];
      this._active = next.length - 1;
      this.commit(next);
      return;
    }
    let best = 0;
    stops.forEach((s, i) => {
      if (Math.abs(s.pos - t) < Math.abs(stops[best].pos - t)) best = i;
    });
    this.dragStop(e, best);
  }
  add() {
    const stops = this.stops();
    const sorted = [...stops].sort((a, b) => a.pos - b.pos);
    const cur = stops[this._active] || sorted[0];
    const j = sorted.indexOf(cur);
    const nb = sorted[j + 1] || sorted[j - 1];
    const pos = nb ? (cur.pos + nb.pos) / 2 : clamp(cur ? cur.pos + 0.1 : 0.5, 0, 1);
    const next = [...stops, {pos, color: evalRamp(stops, pos, this.interp())}];
    this._active = next.length - 1;
    this.commit(next);
  }
  remove() {
    const stops = this.stops();
    if (stops.length <= 1) return;
    const next = stops.filter((_, i) => i !== this._active);
    this._active = clamp(this._active - 1, 0, next.length - 1);
    this.commit(next);
  }
  specials(e) {
    popup(e.currentTarget, (box, close) => menuList(box, {
      items: [
        {label: 'Flip Color Ramp', value: 'flip'},
        {label: 'Distribute Stops from Left', value: 'left'},
        {label: 'Distribute Stops Evenly', value: 'even'},
        {separator: true},
        {label: 'Reset Color Ramp', value: 'reset'},
      ],
      onPick: (it) => {
        close();
        const sorted = [...this.stops()].sort((a, b) => a.pos - b.pos);
        const n = sorted.length;
        let next = sorted;
        if (it.value === 'flip') next = sorted.map((s) => ({...s, pos: 1 - s.pos})).reverse();
        if (it.value === 'left') next = sorted.map((s, i) => ({...s, pos: n > 1 ? i / n : 0}));
        if (it.value === 'even') next = sorted.map((s, i) => ({...s, pos: n > 1 ? i / (n - 1) : 0}));
        if (it.value === 'reset') next = [{pos: 0, color: [0, 0, 0, 1]}, {pos: 1, color: [1, 1, 1, 1]}];
        this._active = 0;
        this.commit(next);
      },
    }));
  }
  pickInterp(e) {
    const cur = this.interp();
    popup(e.currentTarget, (box, close) => menuList(box, {
      title: 'Interpolation',
      items: INTERP.map((l) => ({label: l, checked: l === cur})),
      search: false,
      onPick: (it) => {
        close();
        this.set('interpolation', it.label);
        this.fire({stops: this.val('stops', []), interpolation: it.label});
      },
    }));
  }
  setActivePos(v, live) {
    const next = this.stops().map((s) => ({...s}));
    if (!next[this._active]) return;
    next[this._active].pos = clamp(v, 0, 1);
    if (live) {
      this._live = next;
      this.requestUpdate();
    } else {
      this.commit(next);
    }
  }
  render() {
    const stops = this.stops();
    this._active = clamp(this._active, 0, Math.max(0, stops.length - 1));
    const act = stops[this._active];
    return html`<div class="bui-cr">
      <div class="bui-cr-top">
        <div class="bui-cr-btns bui-joined-h">
          <button class="bui-w bui-cr-ib" data-tip="Add a new color stop to the color ramp" @click=${() => this.add()}>${icon('ADD')}</button>
          <button class="bui-w bui-cr-ib" data-tip="Delete the active position" @click=${() => this.remove()}>${icon('REMOVE')}</button>
        </div>
        <button class="bui-w bui-cr-ib bui-cr-menu" data-tip="Color ramp specials" @click=${(e) => this.specials(e)}>${icon('TRIA_DOWN')}</button>
        <span class="bui-cr-sp"></span>
        <button class="bui-w bui-cr-enum" data-tip="Set interpolation between color stops" @click=${(e) => this.pickInterp(e)}>
          <span class="bui-txt">${this.interp()}</span>${icon('TRIA_DOWN', 'bui-caret')}
        </button>
      </div>
      <div class="bui-cr-bar" @pointerdown=${(e) => this.barDown(e)}>
        <canvas class="bui-ed-canvas"></canvas>
        ${stops.map((s, i) => html`<div class="bui-cr-stop ${i === this._active ? 'bui-cr-active' : ''}"
            style="left:${s.pos * 100}%"><i></i><b style="--c:${cssColor([...s.color.slice(0, 3), 1])}"></b></div>`)}
      </div>
      <div class="bui-cr-row">
        ${numField({value: this._active, integer: true, min: 0, max: stops.length - 1, cls: 'bui-cr-idx',
                    onLive: (v) => { this._active = v; this.requestUpdate(); },
                    onCommit: (v) => { this._active = v; this.requestUpdate(); }})}
        ${numField({label: 'Pos', value: act ? act.pos : 0, min: 0, max: 1, slider: false, cls: 'bui-cr-pos',
                    onLive: (v) => this.setActivePos(v, true), onCommit: (v) => this.setActivePos(v, false)})}
        <span class="bui-w bui-cr-swatch" data-tip=${act ? cssColor(act.color) : ''}>
          <span style="background:${act ? cssColor([...act.color.slice(0, 3), 1]) : 'transparent'}"></span>
          <span style="background:${act ? cssColor(act.color) : 'transparent'}"></span>
        </span>
      </div>
    </div>`;
  }
}

/* -------------------------------------------------------- CurveMapping */

/** Monotone cubic (Fritsch-Carlson) evaluator through sorted points. */
export function monotone(pts) {
  const n = pts.length;
  if (n === 0) return () => 0;
  if (n === 1) return () => pts[0][1];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const d = [], m = new Array(n);
  for (let i = 0; i < n - 1; i++) d.push((ys[i + 1] - ys[i]) / Math.max(1e-6, xs[i + 1] - xs[i]));
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) {
      m[i] = m[i + 1] = 0;
      continue;
    }
    const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * d[i];
      m[i + 1] = t * b * d[i];
    }
  }
  return (x) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = 0;
    while (i < n - 2 && x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i], t = (x - xs[i]) / h, t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] +
        (t3 - t2) * h * m[i + 1];
  };
}

const CHANNEL_COLORS = {C: null, R: '#ff5050', G: '#50e050', B: '#5a8cff', A: null};

class CurveMappingElement extends CanvasElement {
  constructor() {
    super();
    this._sel = new Set();
    this._live = null;
  }
  curves() {
    if (this._live) return this._live;
    const v = this.val('curves', []);
    return (Array.isArray(v) ? v : []).map((c, i) => ({
      name: c?.name ?? String(i),
      color: c?.color,
      points: (Array.isArray(c?.points) ? c.points : [[0, 0], [1, 1]])
                  .map((p) => [clamp(Number(p[0]) || 0, 0, 1), clamp(Number(p[1]) || 0, 0, 1)])
                  .sort((a, b) => a[0] - b[0]),
    }));
  }
  cur() {
    const n = this.curves().length;
    return clamp(Math.round(this.val('current', 0)), 0, Math.max(0, n - 1));
  }
  curveColor(c) {
    if (c?.color) return cssColor(c.color);
    const k = String(c?.name || '').toUpperCase();
    return CHANNEL_COLORS[k] || themeVar(this, '--bui-text', '#e6e6e6');
  }
  commit(curves) {
    this._live = null;
    const out = curves.map((c) => ({
      name: c.name, ...(c.color ? {color: c.color} : {}),
      points: c.points.map((p) => [Number(p[0].toFixed(4)), Number(p[1].toFixed(4))]),
    }));
    this.set('curves', out);
    this.fire({curves: out, current: this.cur()});
  }
  geom() {
    const cv = this.querySelector('canvas.bui-ed-canvas');
    const r = cv.getBoundingClientRect();
    const pad = unitPx(this) * 0.35;
    return {r, pad, w: r.width - pad * 2, h: r.height - pad * 2};
  }
  toScreen(p, g) {
    return [g.pad + p[0] * g.w, g.pad + (1 - p[1]) * g.h];
  }
  draw(ctx, W, H) {
    const light = isLight(this);
    const g = {pad: unitPx(this) * 0.35, w: W - unitPx(this) * 0.7, h: H - unitPx(this) * 0.7};
    ctx.fillStyle = light ? '#b8b8b8' : '#232323';
    ctx.fillRect(0, 0, W, H);
    // Grid: 0.25 lines, 0.125 minor.
    ctx.lineWidth = 1;
    for (let i = 0; i <= 8; i++) {
      const major = i % 2 === 0;
      ctx.strokeStyle = light ? (major ? 'rgba(0,0,0,.22)' : 'rgba(0,0,0,.09)')
                              : (major ? 'rgba(255,255,255,.13)' : 'rgba(255,255,255,.05)');
      const x = Math.round(g.pad + (i / 8) * g.w) + 0.5, y = Math.round(g.pad + (i / 8) * g.h) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
    // Unit box.
    ctx.strokeStyle = light ? 'rgba(0,0,0,.35)' : 'rgba(255,255,255,.22)';
    ctx.strokeRect(Math.round(g.pad) + 0.5, Math.round(g.pad) + 0.5, Math.round(g.w), Math.round(g.h));
    const curves = this.curves();
    const ci = this.cur();
    const c = curves[ci];
    if (!c) return;
    const f = monotone(c.points);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, W, H);
    ctx.clip();
    ctx.beginPath();
    const steps = Math.max(64, Math.round(g.w));
    for (let i = 0; i <= steps; i++) {
      const x = i / steps;
      const [sx, sy] = this.toScreen([x, clamp(f(x), 0, 1)], g);
      if (i === 0) {
        ctx.moveTo(0, sy);
        ctx.lineTo(sx, sy);
      } else {
        ctx.lineTo(sx, sy);
      }
    }
    ctx.lineTo(W, this.toScreen([1, clamp(f(1), 0, 1)], g)[1]);
    ctx.strokeStyle = light ? 'rgba(0,0,0,.5)' : 'rgba(0,0,0,.6)';
    ctx.lineWidth = 3.2;
    ctx.stroke();
    ctx.strokeStyle = this.curveColor(c);
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();
    const rad = Math.max(3, unitPx(this) * 0.17);
    c.points.forEach((p, i) => {
      const [x, y] = this.toScreen(p, g);
      ctx.beginPath();
      ctx.arc(x, y, rad, 0, Math.PI * 2);
      const sel = this._sel.has(i);
      ctx.fillStyle = sel ? '#ffffff' : '#000000';
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = sel ? '#000000' : 'rgba(255,255,255,.55)';
      ctx.stroke();
    });
  }
  down(e) {
    if (e.button !== 0 || !this.enabled) return;
    e.preventDefault();
    e.currentTarget.focus({preventScroll: true});
    const g = this.geom();
    const curves = this.curves().map((c) => ({...c, points: c.points.map((p) => [...p])}));
    const ci = this.cur();
    const c = curves[ci];
    if (!c) return;
    const lx = e.clientX - g.r.left, ly = e.clientY - g.r.top;
    const toCurve = (cx, cy) => [clamp((cx - g.r.left - g.pad) / g.w, 0, 1), clamp(1 - (cy - g.r.top - g.pad) / g.h, 0, 1)];
    const hitR = unitPx(this) * 0.45;
    let hit = -1, best = Infinity;
    c.points.forEach((p, i) => {
      const [x, y] = this.toScreen(p, g);
      const d = Math.hypot(x - lx, y - ly);
      if (d < hitR && d < best) {
        best = d;
        hit = i;
      }
    });
    if (hit < 0) {
      // Click on empty space adds a point there (Blender).
      const np = toCurve(e.clientX, e.clientY);
      c.points.push(np);
      c.points.sort((a, b) => a[0] - b[0]);
      hit = c.points.indexOf(np);
      this._sel = new Set([hit]);
      this._live = curves;
      this.requestUpdate();
    } else if (e.shiftKey) {
      if (this._sel.has(hit)) this._sel.delete(hit);
      else this._sel.add(hit);
    } else if (!this._sel.has(hit)) {
      this._sel = new Set([hit]);
    }
    this.schedule();
    const added = !!this._live;
    const start = c.points.map((p) => [...p]);
    const sel = [...this._sel];
    drag(e, {
      onMove: (dx, dy, ev) => {
        const k = ev.shiftKey ? 0.1 : 1;
        const pts = start.map((p) => [...p]);
        for (const i of sel) {
          if (!pts[i]) continue;
          let x = start[i][0] + (dx * k) / g.w, y = start[i][1] - (dy * k) / g.h;
          if (ev.ctrlKey) {
            x = Math.round(x * 8) / 8;
            y = Math.round(y * 8) / 8;
          }
          const lo = i > 0 ? start[i - 1][0] + 0.001 : 0, hi = i < start.length - 1 ? start[i + 1][0] - 0.001 : 1;
          pts[i] = [clamp(x, Math.max(0, lo), Math.min(1, hi)), clamp(y, 0, 1)];
        }
        curves[ci] = {...c, points: pts};
        this._live = curves;
        this.schedule();
      },
      onEnd: (moved) => {
        if (moved || added) this.commit(this._live || curves);
        else this.schedule();
      },
    });
  }
  key(e) {
    if ((e.key === 'Delete' || e.key === 'x' || e.key === 'X') && this._sel.size) {
      const curves = this.curves().map((c) => ({...c, points: c.points.map((p) => [...p])}));
      const c = curves[this.cur()];
      if (!c) return;
      const keep = c.points.filter((_, i) => !this._sel.has(i));
      if (keep.length < 2) return;
      c.points = keep;
      this._sel = new Set();
      e.preventDefault();
      this.commit(curves);
    } else if (e.key === 'a' && !e.ctrlKey) {
      const c = this.curves()[this.cur()];
      this._sel = e.altKey ? new Set() : new Set(c ? c.points.map((_, i) => i) : []);
      e.preventDefault();
      this.schedule();
    }
  }
  pickTab(i) {
    this._sel = new Set();
    this.set('current', i);
    this.fire({curves: this.val('curves', []), current: i});
  }
  reset(e) {
    popup(e.currentTarget, (box, close) => menuList(box, {
      items: [{label: 'Reset Curve', value: 'reset'}, {label: 'Reset All Curves', value: 'all'}],
      search: false,
      onPick: (it) => {
        close();
        const ci = this.cur();
        const curves = this.curves().map((c, i) =>
            it.value === 'all' || i === ci ? {...c, points: [[0, 0], [1, 1]]} : c);
        this._sel = new Set();
        this.commit(curves);
      },
    }));
  }
  render() {
    const curves = this.curves();
    const ci = this.cur();
    const h = typeof this.p.height === 'number' ? this.p.height : 8;
    return html`<div class="bui-cm">
      <div class="bui-cm-top">
        ${curves.length > 1 ? html`<div class="bui-cm-tabs bui-joined-h">${curves.map((c, i) => html`
          <button class="bui-w bui-cm-tab ${i === ci ? 'bui-sel' : ''}" @click=${() => this.pickTab(i)}>${c.name}</button>`)}
        </div>` : nothing}
        <span class="bui-cr-sp"></span>
        <button class="bui-w bui-cr-ib bui-noemboss" data-tip="Curve tools" @click=${(e) => this.reset(e)}>${icon('TRIA_DOWN')}</button>
      </div>
      <canvas class="bui-ed-canvas bui-cm-canvas" tabindex="0" style="height: calc(var(--bui-u) * ${h})"
          @pointerdown=${(e) => this.down(e)} @keydown=${(e) => this.key(e)}></canvas>
    </div>`;
  }
}

/* ---------------------------------------------------------- NormalBall */

function normalize(v) {
  const [x = 0, y = 0, z = 1] = (Array.isArray(v) ? v : []).map(Number);
  const l = Math.hypot(x, y, z) || 1;
  return [x / l, y / l, z / l];
}

class NormalBallElement extends CanvasElement {
  vec() {
    return this._live || normalize(this.val('value', [0, 0, 1]));
  }
  draw(ctx, W, H) {
    const light = isLight(this);
    const dpr = window.devicePixelRatio || 1;
    const R = Math.min(W, H) / 2 - 1.5;
    const cx = W / 2, cy = H / 2;
    const [lx, ly, lz] = this.vec();
    const pw = Math.round(W * dpr), ph = Math.round(H * dpr);
    const img = ctx.createImageData(pw, ph);
    const d = img.data;
    const hv = normalize([lx, ly, lz + 1]);  // half vector for a soft highlight
    for (let py = 0; py < ph; py++) {
      for (let px = 0; px < pw; px++) {
        const x = (px / dpr - cx) / R, y = -(py / dpr - cy) / R;
        const rr = x * x + y * y;
        if (rr > 1) continue;
        const z = Math.sqrt(1 - rr);
        const diff = Math.max(0, x * lx + y * ly + z * lz);
        const spec = Math.pow(Math.max(0, x * hv[0] + y * hv[1] + z * hv[2]), 40) * 0.35;
        const c = clamp((light ? 0.32 : 0.12) + diff * 0.78 + spec, 0, 1) * 255;
        const edge = clamp((1 - Math.sqrt(rr)) * R * dpr, 0, 1);  // antialias rim
        const o = (py * pw + px) * 4;
        d[o] = d[o + 1] = d[o + 2] = c;
        d[o + 3] = edge * 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    ctx.beginPath();
    ctx.arc(cx, cy, R + 0.5, 0, Math.PI * 2);
    ctx.strokeStyle = light ? 'rgba(0,0,0,.45)' : 'rgba(0,0,0,.7)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  down(e) {
    if (e.button !== 0 || !this.enabled) return;
    e.preventDefault();
    const cv = e.currentTarget;
    const size = cv.getBoundingClientRect().width || 80;
    const v0 = this.vec();
    drag(e, {
      onMove: (dx, dy, ev) => {
        const k = (Math.PI / size) * (ev.shiftKey ? 0.2 : 1);
        const ay = dx * k, ax = dy * k;
        // Trackball: rotate about the screen Y axis (dx), then the X axis (dy).
        let [x, y, z] = v0;
        [x, z] = [x * Math.cos(ay) + z * Math.sin(ay), -x * Math.sin(ay) + z * Math.cos(ay)];
        [y, z] = [y * Math.cos(ax) - z * Math.sin(ax), y * Math.sin(ax) + z * Math.cos(ax)];
        this._live = normalize([x, y, z]);
        this.requestUpdate();
      },
      onEnd: (moved) => {
        if (!moved || !this._live) return;
        const v = this._live.map((n) => Number(n.toFixed(4)));
        this._live = null;
        this.set('value', v);
        this.fire({value: v});
      },
    });
  }
  render() {
    const s = typeof this.p.size === 'number' ? this.p.size : 4;
    const v = this.vec();
    const lab = this.p.label;
    return html`<div class="bui-nb">
      <canvas class="bui-ed-canvas bui-nb-ball" style="width: calc(var(--bui-u) * ${s}); height: calc(var(--bui-u) * ${s})"
          @pointerdown=${(e) => this.down(e)}></canvas>
      ${lab ? html`<div class="bui-nb-label">${lab}</div>` : nothing}
      <div class="bui-nb-read">${['X', 'Y', 'Z'].map((a, i) => html`
        <span class="bui-nb-ax"><b class="bui-nb-${a.toLowerCase()}">${a}</b>${fmtNum(v[i], {precision: 3})}</span>`)}
      </div>
    </div>`;
  }
}

/* ----------------------------------------------------------- Histogram */

class HistogramElement extends CanvasElement {
  draw(ctx, W, H) {
    // Scopes keep Blender's dark backdrop in every theme (additive channels need it).
    const light = false;
    const bins = this.p.bins;
    const mode = this.p.mode || (bins && !Array.isArray(bins) && typeof bins === 'object' ? 'rgb' : 'luma');
    ctx.fillStyle = light ? '#a8a8a8' : '#1d1d1d';
    ctx.fillRect(0, 0, W, H);
    ctx.lineWidth = 1;
    ctx.strokeStyle = light ? 'rgba(0,0,0,.14)' : 'rgba(255,255,255,.07)';
    ctx.beginPath();
    for (let i = 1; i < 4; i++) {
      const y = Math.round((i / 4) * H) + 0.5, x = Math.round((i / 4) * W) + 0.5;
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
    }
    ctx.stroke();
    const top = 3;
    const area = (arr, max, fill, line) => {
      if (!arr.length) return;
      const n = arr.length;
      ctx.beginPath();
      ctx.moveTo(0, H);
      arr.forEach((v, i) => ctx.lineTo((i / Math.max(1, n - 1)) * W, H - (clamp(v, 0, max) / max) * (H - top)));
      ctx.lineTo(W, H);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (line) {
        ctx.beginPath();
        arr.forEach((v, i) => {
          const x = (i / Math.max(1, n - 1)) * W, y = H - (clamp(v, 0, max) / max) * (H - top);
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.strokeStyle = line;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    };
    const nums = (a) => (Array.isArray(a) ? a.map((x) => Number(x) || 0) : []);
    if (mode === 'rgb' && bins && !Array.isArray(bins)) {
      const ch = {r: nums(bins.r), g: nums(bins.g), b: nums(bins.b), luma: nums(bins.luma)};
      const max = Math.max(1e-9, ...ch.r, ...ch.g, ...ch.b, ...ch.luma);
      if (ch.luma.length) area(ch.luma, max, light ? 'rgba(255,255,255,.35)' : 'rgba(255,255,255,.12)', light ? 'rgba(255,255,255,.8)' : 'rgba(255,255,255,.45)');
      ctx.save();
      ctx.globalCompositeOperation = light ? 'multiply' : 'lighter';
      const A = light ? 0.55 : 0.5;
      area(ch.r, max, `rgba(255,40,40,${A})`, 'rgba(255,90,90,.9)');
      area(ch.g, max, `rgba(40,255,40,${A})`, 'rgba(90,255,90,.9)');
      area(ch.b, max, `rgba(50,90,255,${A})`, 'rgba(110,140,255,.9)');
      ctx.restore();
      return;
    }
    const arr = nums(Array.isArray(bins) ? bins : bins?.luma);
    const max = Math.max(1e-9, ...arr);
    if (mode === 'bars') {
      const n = arr.length || 1;
      const slot = W / n, gap = Math.max(1, Math.min(slot * 0.25, unitPx(this) * 0.25));
      ctx.fillStyle = light ? 'rgba(40,40,40,.65)' : 'rgba(220,220,220,.6)';
      arr.forEach((v, i) => {
        const bh = (clamp(v, 0, max) / max) * (H - top);
        const x = i * slot + gap / 2, bw = Math.max(1, slot - gap);
        const r = Math.min(2, bw / 2, bh);
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, H - bh, bw, bh, [r, r, 0, 0]);
        else ctx.rect(x, H - bh, bw, bh);
        ctx.fill();
      });
      return;
    }
    area(arr, max, light ? 'rgba(255,255,255,.55)' : 'rgba(255,255,255,.35)', light ? '#fff' : 'rgba(255,255,255,.85)');
  }
  render() {
    const h = typeof this.p.height === 'number' ? this.p.height : 5;
    const labels = Array.isArray(this.p.labels) ? this.p.labels : [];
    const bars = this.p.mode === 'bars';
    return html`<div class="bui-hist">
      <canvas class="bui-ed-canvas bui-hist-canvas" style="height: calc(var(--bui-u) * ${h})"></canvas>
      ${labels.length ? html`<div class="bui-hist-labels ${bars ? 'bui-hist-labels-bars' : ''}">${
          labels.map((l) => html`<span>${l}</span>`)}</div>` : nothing}
    </div>`;
  }
}

export const IMPLS = [
  impl('ColorRamp', ColorRampElement),
  impl('CurveMapping', CurveMappingElement),
  impl('NormalBall', NormalBallElement),
  impl('Histogram', HistogramElement),
];
