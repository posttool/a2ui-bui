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

// Node editor: Node + NodeEditor.
//
// NodeEditor renders its Node children inside a transformed canvas (pan +
// zoom), finds socket positions from the nodes' DOM (each socket has
// data-node / data-io / data-index / data-name) and draws links as SVG
// beziers. Nodes call back into the closest editor for selection, dragging,
// and linking; outside an editor a Node renders statically.

import {BuiElement, clamp, cssColor, drag, html, impl, nothing, toRgba} from '../base.js';
import {editText, numField, unitPx} from './editors.js';

const HEADER = {
  input: '#83314a', output: '#4d0017', shader: '#2b652b', texture: '#79461d', color: '#6c696f', vector: '#3c3c83',
  converter: '#246283', geometry: '#00866b', group: '#3b5959', script: '#084d4d', filter: '#551a80', layout: '#6c696f',
};

const SOCKET = {
  float: '#a1a1a1', value: '#a1a1a1', int: '#598c5c', integer: '#598c5c', bool: '#cca6d6', boolean: '#cca6d6',
  vector: '#6363c7', color: '#c7c729', rgba: '#c7c729', shader: '#63c763', geometry: '#00d6a3', string: '#70b2ff',
  object: '#ed9e5c', image: '#633863', collection: '#f5f5f5', texture: '#9e4fa3', material: '#eb7582',
  rotation: '#a663c7', matrix: '#b83385', menu: '#4d4d4d',
};
const sockColor = (t) => SOCKET[String(t || 'float').toLowerCase()] || SOCKET.float;

const ns = 'http://www.w3.org/2000/svg';

/** Normalizes a socket list to [{name, type, value?, ...}]. */
function socks(list) {
  return (Array.isArray(list) ? list : []).map((s, i) => {
    if (Array.isArray(s)) return {name: String(s[0] ?? `Socket ${i}`), type: s[1] || 'float', ...(s.length > 2 ? {value: s[2]} : {})};
    if (s && typeof s === 'object') return {...s, name: String(s.name ?? `Socket ${i}`), type: s.type || 'float'};
    return {name: String(s), type: 'float'};
  });
}

/* ---------------------------------------------------------------- Node */

class NodeElement extends BuiElement {
  constructor() {
    super();
    this._tmpLoc = null;
    this._liveIn = null;
  }
  get editor() {
    return this.closest('bui-node-editor');
  }
  get key() {
    return String(this.p.key ?? '');
  }
  loc() {
    if (this._tmpLoc) return this._tmpLoc;
    const l = this.val('location', [0, 0]);
    return Array.isArray(l) ? [Number(l[0]) || 0, Number(l[1]) || 0] : [0, 0];
  }
  inputs() {
    return this._liveIn || socks(this.val('inputs', []));
  }
  outputs() {
    return socks(this.val('outputs', []));
  }
  /** Moves the node during a drag without writing the model. */
  setTempLoc(l) {
    this._tmpLoc = l;
    this.applyLoc();
    this.dispatchEvent(new CustomEvent('bui-node-moved', {bubbles: true, detail: {key: this.key, location: l}}));
  }
  commitLoc() {
    if (!this._tmpLoc) return;
    const l = this._tmpLoc.map((n) => Math.round(n));
    this._tmpLoc = null;
    this.set('location', l);
  }
  applyLoc() {
    if (!this.editor) {
      this.style.removeProperty('left');
      this.style.removeProperty('top');
      return;
    }
    const [x, y] = this.loc();
    this.style.left = `calc(${x}px * var(--bui-scale))`;
    this.style.top = `calc(${y}px * var(--bui-scale))`;
  }
  willUpdate(c) {
    super.willUpdate(c);
    this.classList.toggle('bui-node-in-editor', !!this.editor);
    this.applyLoc();
    this.dataset.key = this.key;
  }
  updated(c) {
    super.updated?.(c);
    this.dispatchEvent(new CustomEvent('bui-node-moved', {bubbles: true, detail: {key: this.key}}));
  }
  toggleCollapsed(e) {
    e.stopPropagation();
    this.set('collapsed', !this.val('collapsed', false));
  }
  down(e) {
    if (e.target.closest('.bui-sock, .bui-ed-num, .bui-node-w, .bui-node-tri, .bui-node-slot, input')) return;
    const ed = this.editor;
    if (ed) {
      ed.nodeDown(this, e);
      return;
    }
  }
  setInput(i, v, live) {
    const list = socks(this.val('inputs', [])).map((s) => ({...s}));
    if (!list[i]) return;
    list[i].value = v;
    if (live) {
      this._liveIn = list;
      this.requestUpdate();
      return;
    }
    this._liveIn = null;
    // Write back in the agent's original shape where it was an object list.
    const raw = this.val('inputs', []);
    const out = (Array.isArray(raw) ? raw : []).map((s, k) => {
      if (k !== i) return s;
      if (Array.isArray(s)) return [s[0], s[1], v];
      if (s && typeof s === 'object') return {...s, value: v};
      return s;
    });
    this.set('inputs', out);
  }
  sockEl(io, i, s, collapsed) {
    return html`<span class="bui-sock bui-sock-${io} ${collapsed ? 'bui-sock-col' : ''}"
        data-node=${this.key} data-io=${io} data-index=${i} data-name=${s.name} data-type=${s.type}
        style="--sc:${sockColor(s.type)}"
        @pointerdown=${(e) => this.editor?.sockDown(this, io, i, e)}></span>`;
  }
  inputWidget(s, i) {
    const t = String(s.type).toLowerCase();
    const v = s.value;
    if (t === 'float' || t === 'value' || t === 'int' || t === 'integer') {
      const integer = t === 'int' || t === 'integer';
      return numField({
        label: s.name, value: Number(v) || 0, integer, min: s.min, max: s.max, step: s.step, precision: s.precision,
        slider: typeof s.min === 'number' && typeof s.max === 'number', cls: 'bui-node-num',
        disabled: !this.enabled, onLive: (n) => this.setInput(i, n, true), onCommit: (n) => this.setInput(i, n, false),
      });
    }
    if (t === 'color' || t === 'rgba') {
      const c = toRgba(v);
      return html`<span class="bui-node-label">${s.name}</span>
        <span class="bui-w bui-node-w bui-node-swatch" data-tip=${cssColor(c)}>
          <span style="background:${cssColor([...c.slice(0, 3), 1])}"></span><span style="background:${cssColor(c)}"></span>
        </span>`;
    }
    if (t === 'bool' || t === 'boolean') {
      return html`<label class="bui-node-w bui-node-check" @click=${(e) => {
        e.preventDefault();
        this.setInput(i, !v, false);
      }}><span class="bui-w bui-node-box ${v ? 'bui-sel' : ''}">${v ? html`<svg viewBox="0 0 10 10"><path d="M2 5.2l2 2 4-4.4"/></svg>` : nothing}</span>
        <span class="bui-node-label">${s.name}</span></label>`;
    }
    if (t === 'string') {
      return html`<span class="bui-w bui-node-w bui-node-text" @pointerdown=${(e) => {
        e.stopPropagation();
        editText(e.currentTarget, String(v ?? ''), (txt) => this.setInput(i, txt, false), {numeric: false});
      }}><span class="bui-txt">${v || s.name}</span></span>`;
    }
    if (t === 'vector' || t === 'rotation') {
      const arr = Array.isArray(v) ? v : [0, 0, 0];
      return html`<div class="bui-node-vec">
        <span class="bui-node-label">${s.name}:</span>
        <div class="bui-node-vec-f bui-joined-v">${['X', 'Y', 'Z'].map((a, k) => numField({
          label: a, value: Number(arr[k]) || 0, cls: 'bui-node-num', disabled: !this.enabled,
          onLive: (n) => this.setInput(i, arr.map((x, j) => (j === k ? n : x)), true),
          onCommit: (n) => this.setInput(i, arr.map((x, j) => (j === k ? n : x)), false),
        }))}</div>
      </div>`;
    }
    return html`<span class="bui-node-label">${s.name}</span>`;
  }
  render() {
    const p = this.p;
    const collapsed = !!this.val('collapsed', false);
    const outs = this.outputs(), ins = this.inputs();
    const linked = this.editor?.linkedInputs(this.key) || new Set();
    const w = typeof p.width === 'number' ? p.width : 7;
    const kind = String(p.kind || 'converter').toLowerCase();
    this.style.width = `calc(var(--bui-u) * ${w})`;
    const tri = html`<span class="bui-node-tri" @pointerdown=${(e) => e.stopPropagation()}
        @click=${(e) => this.toggleCollapsed(e)}>${collapsed
        ? html`<svg viewBox="0 0 10 10"><path d="M3.5 2l3 3-3 3"/></svg>`
        : html`<svg viewBox="0 0 10 10"><path d="M2 3.5l3 3 3-3"/></svg>`}</span>`;
    return html`<div class="bui-node ${collapsed ? 'bui-node-collapsed' : ''}" style="--hc:${HEADER[kind] || HEADER.converter}"
        @pointerdown=${(e) => this.down(e)}>
      <div class="bui-node-hdr">${tri}<span class="bui-node-title">${p.title}</span>
        ${collapsed ? html`${outs.map((s, i) => this.sockEl('out', i, s, true))}${ins.map((s, i) => this.sockEl('in', i, s, true))}` : nothing}
      </div>
      ${collapsed ? nothing : html`<div class="bui-node-body">
        ${outs.map((s, i) => html`<div class="bui-node-row bui-node-out">
          <span class="bui-node-label">${s.name}</span>${this.sockEl('out', i, s)}</div>`)}
        ${p.preview ? html`<div class="bui-node-preview"><img src=${p.preview} alt="" draggable="false"></div>` : nothing}
        ${p.body ? html`<div class="bui-node-slot">${this.kids(p.body)}</div>` : nothing}
        ${ins.map((s, i) => {
          const showW = !linked.has(i) && s.value !== undefined && s.hide_value !== true;
          const t = String(s.type).toLowerCase();
          const tall = showW && (t === 'vector' || t === 'rotation');
          return html`<div class="bui-node-row bui-node-in ${tall ? 'bui-node-tall' : ''}">${this.sockEl('in', i, s)}${
              showW ? this.inputWidget(s, i) : html`<span class="bui-node-label">${s.name}</span>`}</div>`;
        })}
      </div>`}
    </div>`;
  }
}

/* ---------------------------------------------------------- NodeEditor */

/** Cubic bezier between two sockets, Blender noodle style. */
function bez(a, b) {
  const d = Math.max(Math.abs(b[0] - a[0]) * 0.4, 18);
  return [a, [a[0] + d, a[1]], [b[0] - d, b[1]], b];
}
const bezPath = (c) => `M${c[0][0]},${c[0][1]} C${c[1][0]},${c[1][1]} ${c[2][0]},${c[2][1]} ${c[3][0]},${c[3][1]}`;
function bezPoints(c, n = 24) {
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, mt = 1 - t;
    out.push([0, 1].map((k) => mt ** 3 * c[0][k] + 3 * mt * mt * t * c[1][k] + 3 * mt * t * t * c[2][k] + t ** 3 * c[3][k]));
  }
  return out;
}
function segX(p1, p2, p3, p4) {
  const d = (p4[1] - p3[1]) * (p2[0] - p1[0]) - (p4[0] - p3[0]) * (p2[1] - p1[1]);
  if (!d) return false;
  const ua = ((p4[0] - p3[0]) * (p1[1] - p3[1]) - (p4[1] - p3[1]) * (p1[0] - p3[0])) / d;
  const ub = ((p2[0] - p1[0]) * (p1[1] - p3[1]) - (p2[1] - p1[1]) * (p1[0] - p3[0])) / d;
  return ua >= 0 && ua <= 1 && ub >= 0 && ub <= 1;
}

class NodeEditorElement extends BuiElement {
  constructor() {
    super();
    this._pan = [0, 0];
    this._zoom = 1;
    this._framed = false;
    this._sel = new Set();
    this._active = '';
    this._links = null;   // local working copy during edits
    this._tmp = null;     // {from:[x,y], to:[x,y], color} while linking
  }
  connectedCallback() {
    super.connectedCallback();
    this._ro = new ResizeObserver(() => this.redraw());
    this._mo = new MutationObserver(() => this.observeNodes());
    this.addEventListener('bui-node-moved', () => this.redraw());
    this._rootMo = new MutationObserver(() => {
      if (!this._userView) this._framed = false;
      this.redraw();
    });
    const root = this.closest('.bui-root');
    if (root) this._rootMo.observe(root, {attributes: true, attributeFilter: ['class', 'style']});
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this._ro?.disconnect();
    this._mo?.disconnect();
    this._rootMo?.disconnect();
    this._vro?.disconnect();
    this._vpObs = null;
  }
  get canvas() {
    return this.querySelector('.bui-ne-canvas');
  }
  nodes() {
    const c = this.canvas;
    return c ? [...c.querySelectorAll('bui-node')].filter((n) => n.closest('bui-node-editor') === this) : [];
  }
  nodeByKey(k) {
    return this.nodes().find((n) => n.key === String(k));
  }
  links() {
    if (this._links) return this._links;
    const l = this.val('links', []);
    return Array.isArray(l) ? l.filter((x) => x && typeof x === 'object') : [];
  }
  /** Resolves a socket reference (index or name) to an index. */
  sockIndex(key, io, ref) {
    if (typeof ref === 'number') return ref;
    if (/^\d+$/.test(String(ref))) return Number(ref);
    const n = this.nodeByKey(key);
    if (!n) return -1;
    const list = io === 'out' ? n.outputs() : n.inputs();
    return list.findIndex((s) => s.name === ref);
  }
  linkedInputs(key) {
    const s = new Set();
    for (const l of this.links()) if (String(l.to) === key) s.add(this.sockIndex(key, 'in', l.in));
    return s;
  }
  writeLinks(next) {
    this._links = null;
    this.set('links', next);
    this.fire({links: next});
    for (const n of this.nodes()) n.requestUpdate();
    this.redraw();
  }
  /* ---------------- geometry */
  observeNodes() {
    this._ro.disconnect();
    for (const n of this.nodes()) this._ro.observe(n);
    for (const n of this.nodes()) n.requestUpdate();  // nodes read linkedInputs()
    this.redraw();
  }
  updated(c) {
    super.updated?.(c);
    const cv = this.canvas;
    if (cv && cv !== this._mod) {
      this._mo.disconnect();
      this._mo.observe(cv, {childList: true, subtree: true});
      this._mod = cv;
      this.observeNodes();
    }
    const vp = this.querySelector('.bui-ne');
    if (vp && vp !== this._vpObs) {
      this._vpObs = vp;
      // Keep the graph framed while the viewport resizes, until the user navigates.
      this._vro = new ResizeObserver(() => {
        if (!this._userView) this._framed = false;
        this.redraw();
      });
      this._vro.observe(vp);
    }
    this.applyView();
    for (const n of this.nodes()) n.requestUpdate();
    this.redraw();
  }
  scale() {
    return unitPx(this) / 20;
  }
  applyView() {
    const cv = this.canvas;
    const vp = this.querySelector('.bui-ne');
    if (!cv || !vp) return;
    cv.style.transform = `translate(${this._pan[0]}px, ${this._pan[1]}px) scale(${this._zoom})`;
    const step = 20 * this.scale() * this._zoom * 1.25;
    vp.style.backgroundSize = `${step}px ${step}px`;
    vp.style.backgroundPosition = `${this._pan[0] - step / 2}px ${this._pan[1] - step / 2}px`;
  }
  /** Socket center in canvas coordinates. */
  sockPos(el) {
    const c = this.canvas.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    return [(r.left + r.width / 2 - c.left) / this._zoom, (r.top + r.height / 2 - c.top) / this._zoom];
  }
  toCanvas(cx, cy) {
    const c = this.canvas.getBoundingClientRect();
    return [(cx - c.left) / this._zoom, (cy - c.top) / this._zoom];
  }
  findSock(key, io, ref) {
    const idx = this.sockIndex(key, io, ref);
    const n = this.nodeByKey(key);
    if (!n || idx < 0) return null;
    return n.querySelector(`.bui-sock[data-io="${io}"][data-index="${idx}"]`);
  }
  linkCurves() {
    const out = [];
    this.links().forEach((l, i) => {
      const a = this.findSock(l.from, 'out', l.out), b = this.findSock(l.to, 'in', l.in);
      if (!a || !b) return;
      out.push({i, link: l, c: bez(this.sockPos(a), this.sockPos(b)), color: a.style.getPropertyValue('--sc'),
                sel: this._sel.has(String(l.from)) || this._sel.has(String(l.to))});
    });
    return out;
  }
  redraw() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = 0;
      this.drawLinks();
      if (!this._framed && this.nodes().length) {
        const r = this.querySelector('.bui-ne')?.getBoundingClientRect();
        if (r && r.width > 0 && this.nodes().every((n) => n.offsetWidth > 0)) {
          this._framed = true;
          this.frameAll(false);
        }
      }
    });
  }
  drawLinks() {
    const svg = this.querySelector('svg.bui-ne-links');
    if (!svg || !this.canvas) return;
    const s = this.scale();
    const wOuter = 4.2 * s, wInner = 2.2 * s;
    const wire = getComputedStyle(this).getPropertyValue('--bui-node-wire').trim() || '#1a1a1a';
    let out = '';
    for (const L of this.linkCurves()) {
      const d = bezPath(L.c);
      out += `<path d="${d}" stroke="${wire}" stroke-width="${wOuter}" fill="none" stroke-linecap="round"/>`;
      out += `<path d="${d}" stroke="${L.sel ? '#ffffff' : (L.color || '#a1a1a1')}" stroke-width="${wInner}" fill="none" stroke-linecap="round" ${L.sel ? 'stroke-opacity=".9"' : ''}/>`;
      if (L.sel) out += `<path d="${d}" stroke="${L.color || '#a1a1a1'}" stroke-width="${wInner * 0.55}" fill="none" stroke-linecap="round"/>`;
    }
    if (this._tmp) {
      const d = bezPath(this._tmp.rev ? bez(this._tmp.to, this._tmp.from) : bez(this._tmp.from, this._tmp.to));
      out += `<path d="${d}" stroke="${wire}" stroke-width="${wOuter}" fill="none" stroke-linecap="round"/>`;
      out += `<path d="${d}" stroke="${this._tmp.color}" stroke-width="${wInner}" fill="none" stroke-linecap="round" stroke-dasharray="${this._tmp.ok ? '' : `${6 * s} ${4 * s}`}"/>`;
    }
    svg.innerHTML = out;
  }
  /* ---------------- view */
  frameAll(animate = true) {
    const vp = this.querySelector('.bui-ne');
    const nodes = this.nodes();
    if (!vp || !nodes.length) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    const s = this.scale();
    for (const n of nodes) {
      const [x, y] = n.loc();
      x0 = Math.min(x0, x * s);
      y0 = Math.min(y0, y * s);
      x1 = Math.max(x1, x * s + n.offsetWidth);
      y1 = Math.max(y1, y * s + n.offsetHeight);
    }
    const W = vp.clientWidth, H = vp.clientHeight, m = unitPx(this) * 1.2;
    const z = clamp(Math.min((W - m * 2) / Math.max(1, x1 - x0), (H - m * 2) / Math.max(1, y1 - y0)), 0.2, 1.25);
    this._zoom = z;
    this._pan = [(W - (x1 - x0) * z) / 2 - x0 * z, (H - (y1 - y0) * z) / 2 - y0 * z];
    const cv = this.canvas;
    if (animate && cv) {
      cv.style.transition = 'transform .18s ease-out';
      setTimeout(() => (cv.style.transition = ''), 200);
    }
    this.applyView();
    this.redraw();
  }
  wheel(e) {
    e.preventDefault();
    this._userView = true;
    const vp = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - vp.left, my = e.clientY - vp.top;
    if (e.ctrlKey && Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      this._pan[0] -= e.deltaX;
    } else if (e.shiftKey) {
      this._pan[1] -= e.deltaY;
    } else {
      const z0 = this._zoom;
      const z = clamp(z0 * Math.pow(1.0015, -e.deltaY), 0.2, 2.5);
      this._pan = [mx - (mx - this._pan[0]) * (z / z0), my - (my - this._pan[1]) * (z / z0)];
      this._zoom = z;
    }
    this.applyView();
  }
  pan(e) {
    this._userView = true;
    const p0 = [...this._pan];
    e.preventDefault();
    this.querySelector('.bui-ne').classList.add('bui-ne-panning');
    drag(e, {
      onMove: (dx, dy) => {
        this._pan = [p0[0] + dx, p0[1] + dy];
        this.applyView();
      },
      onEnd: () => this.querySelector('.bui-ne')?.classList.remove('bui-ne-panning'),
    });
  }
  /* ---------------- selection */
  applySel() {
    for (const n of this.nodes()) {
      n.classList.toggle('bui-node-sel', this._sel.has(n.key));
      n.classList.toggle('bui-node-act', this._active === n.key && this._sel.has(n.key));
    }
    this.redraw();
  }
  select(keys, {extend = false} = {}) {
    if (!extend) this._sel = new Set();
    for (const k of keys) this._sel.add(k);
    this.applySel();
  }
  nodeDown(node, e) {
    this.querySelector('.bui-ne')?.focus({preventScroll: true});
    if (e.button === 1 || (e.button === 0 && (e.altKey || this._space))) return this.pan(e);
    if (e.button !== 0) return;
    e.stopPropagation();
    const k = node.key;
    if (e.shiftKey) {
      if (this._sel.has(k) && this._active === k) this._sel.delete(k);
      else this._sel.add(k);
      this._active = k;
    } else if (!this._sel.has(k)) {
      this._sel = new Set([k]);
      this._active = k;
    } else {
      this._active = k;
    }
    this.applySel();
    // Bring to front (Blender draws the active node on top).
    const parent = node.parentElement;
    for (const n of this.nodes()) n.style.zIndex = n === node ? '3' : (this._sel.has(n.key) ? '2' : '1');
    void parent;
    const moving = this.nodes().filter((n) => this._sel.has(n.key));
    const starts = moving.map((n) => n.loc());
    const s = this.scale();
    drag(e, {
      onMove: (dx, dy, ev) => {
        let ox = dx / (this._zoom * s), oy = dy / (this._zoom * s);
        if (ev.ctrlKey) {
          ox = Math.round(ox / 20) * 20;
          oy = Math.round(oy / 20) * 20;
        }
        moving.forEach((n, i) => n.setTempLoc([starts[i][0] + ox, starts[i][1] + oy]));
      },
      onEnd: (moved, ev) => {
        if (moved) {
          this._userView = true;
          moving.forEach((n) => n.commitLoc());
        } else if (!ev.shiftKey) {
          this._sel = new Set([k]);
          this.applySel();
        }
      },
    });
  }
  bgDown(e) {
    if (e.target.closest('bui-node')) return;
    this.querySelector('.bui-ne')?.focus({preventScroll: true});
    if (e.button === 1 || (e.button === 0 && (e.altKey || this._space))) return this.pan(e);
    if (e.button === 2 && (e.ctrlKey || e.metaKey)) return this.cut(e);
    if (e.button === 2) return this.pan(e);
    if (e.button !== 0) return;
    e.preventDefault();
    const vp = this.querySelector('.bui-ne');
    const vr = vp.getBoundingClientRect();
    const box = this.querySelector('.bui-ne-box');
    const x0 = e.clientX, y0 = e.clientY;
    const base = e.shiftKey ? new Set(this._sel) : new Set();
    drag(e, {
      onMove: (dx, dy) => {
        const l = Math.min(x0, x0 + dx), t = Math.min(y0, y0 + dy), w = Math.abs(dx), h = Math.abs(dy);
        Object.assign(box.style, {display: 'block', left: `${l - vr.left}px`, top: `${t - vr.top}px`, width: `${w}px`, height: `${h}px`});
        const sel = new Set(base);
        for (const n of this.nodes()) {
          const r = n.getBoundingClientRect();
          if (r.right > l && r.left < l + w && r.bottom > t && r.top < t + h) sel.add(n.key);
        }
        this._sel = sel;
        this.applySel();
      },
      onEnd: (moved) => {
        box.style.display = 'none';
        if (!moved && !e.shiftKey) {
          this._sel = new Set();
          this._active = '';
          this.applySel();
        }
      },
    });
  }
  /** Ctrl+right-drag: knife across links. */
  cut(e) {
    e.preventDefault();
    const pts = [this.toCanvas(e.clientX, e.clientY)];
    const knife = this.querySelector('svg.bui-ne-knife');
    const draw = () => {
      knife.innerHTML = `<polyline points="${pts.map((p) => p.join(',')).join(' ')}" fill="none" stroke="#ff5050"
          stroke-width="${1.5 * this.scale()}" stroke-dasharray="${5 * this.scale()} ${3 * this.scale()}"/>`;
    };
    drag(e, {
      onMove: (dx, dy, ev) => {
        pts.push(this.toCanvas(ev.clientX, ev.clientY));
        draw();
      },
      onEnd: () => {
        knife.innerHTML = '';
        if (pts.length < 2) return;
        const dead = new Set();
        for (const L of this.linkCurves()) {
          const bp = bezPoints(L.c);
          outer: for (let i = 0; i < bp.length - 1; i++) {
            for (let j = 0; j < pts.length - 1; j++) {
              if (segX(bp[i], bp[i + 1], pts[j], pts[j + 1])) {
                dead.add(L.i);
                break outer;
              }
            }
          }
        }
        if (dead.size) this.writeLinks(this.links().filter((_, i) => !dead.has(i)));
      },
    });
  }
  /* ---------------- linking */
  sockDown(node, io, idx, e) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    this.querySelector('.bui-ne')?.focus({preventScroll: true});
    let links = [...this.links()];
    let fromKey = node.key, fromIo = io, fromIdx = idx;
    if (io === 'in') {
      // Dragging from a linked input picks the (last) link up.
      const j = links.map((l, k) => [l, k]).reverse()
                    .find(([l]) => String(l.to) === node.key && this.sockIndex(node.key, 'in', l.in) === idx);
      if (j) {
        const [l, k] = j;
        links.splice(k, 1);
        fromKey = String(l.from);
        fromIo = 'out';
        fromIdx = this.sockIndex(fromKey, 'out', l.out);
        this._links = links;
        for (const n of this.nodes()) n.requestUpdate();
      }
    }
    const srcEl = this.findSock(fromKey, fromIo, fromIdx);
    if (!srcEl) return;
    const want = fromIo === 'out' ? 'in' : 'out';
    const color = srcEl.style.getPropertyValue('--sc') || '#a1a1a1';
    const start = this.sockPos(srcEl);
    const hitR = unitPx(this) * 0.8;
    let target = null;
    const update = (ev) => {
      const p = this.toCanvas(ev.clientX, ev.clientY);
      target = null;
      let best = hitR / this._zoom;
      for (const el of this.canvas.querySelectorAll(`.bui-sock[data-io="${want}"]`)) {
        if (el.dataset.node === fromKey || el.classList.contains('bui-sock-col') && !el.offsetParent) continue;
        const sp = this.sockPos(el);
        const d = Math.hypot(sp[0] - p[0], sp[1] - p[1]);
        if (d < best) {
          best = d;
          target = el;
        }
      }
      for (const el of this.canvas.querySelectorAll('.bui-sock.bui-sock-hot')) el.classList.remove('bui-sock-hot');
      target?.classList.add('bui-sock-hot');
      this._tmp = {from: start, to: target ? this.sockPos(target) : p, color, ok: !!target, rev: fromIo === 'in'};
      this.drawLinks();
    };
    this._tmp = {from: start, to: start, color, ok: false, rev: fromIo === 'in'};
    drag(e, {
      onMove: (dx, dy, ev) => update(ev),
      onEnd: (moved) => {
        target?.classList.remove('bui-sock-hot');
        this._tmp = null;
        const picked = links.length !== this.val('links', []).length;
        if (!target) {
          if (picked) this.writeLinks(links);
          else {
            this._links = null;
            this.drawLinks();
          }
          return;
        }
        const tk = target.dataset.node, ti = Number(target.dataset.index);
        const link = fromIo === 'out' ? {from: fromKey, out: fromIdx, to: tk, in: ti} : {from: tk, out: ti, to: fromKey, in: fromIdx};
        // One link per input: replace whatever was there.
        links = links.filter((l) => !(String(l.to) === String(link.to) && this.sockIndex(String(l.to), 'in', l.in) === link.in));
        links.push(link);
        this.writeLinks(links);
      },
    });
  }
  key(e) {
    if (e.target.closest('input')) return;
    if (e.key === ' ') {
      this._space = true;
      e.preventDefault();
    } else if (e.key === 'Home') {
      e.preventDefault();
      this.frameAll();
    } else if (e.key === 'a' && !e.ctrlKey) {
      e.preventDefault();
      this.select(e.altKey ? [] : this.nodes().map((n) => n.key));
    }
  }
  keyUp(e) {
    if (e.key === ' ') this._space = false;
  }
  render() {
    const h = typeof this.p.height === 'number' ? this.p.height : 16;
    return html`<div class="bui-ne" tabindex="0" style="height: calc(var(--bui-u) * ${h})"
        @pointerdown=${(e) => this.bgDown(e)} @wheel=${(e) => this.wheel(e)} @contextmenu=${(e) => e.preventDefault()}
        @keydown=${(e) => this.key(e)} @keyup=${(e) => this.keyUp(e)} @blur=${() => (this._space = false)}>
      <div class="bui-ne-canvas">
        <svg class="bui-ne-links" xmlns=${ns}></svg>
        ${this.kids(this.p.children)}
        <svg class="bui-ne-knife" xmlns=${ns}></svg>
      </div>
      <div class="bui-ne-box"></div>
    </div>`;
  }
}

export const IMPLS = [
  impl('Node', NodeElement),
  impl('NodeEditor', NodeEditorElement),
];
