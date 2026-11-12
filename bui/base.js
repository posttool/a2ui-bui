/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Shared base for every BUI A2UI component.
//
// BuiElement extends the unmodified A2uiLitElement from @a2ui/web_core: the
// library's A2uiController binds props (literals, {"@path"}, {"@call"}) using
// the Zod schema from spec.js, and gives every Dynamic* prop a setter
// (setValue, setCollapsed ...) that writes back to the data model when the
// prop is bound. Components render into the light DOM so children rendered
// with renderNode() inherit the BUI theme variables and global stylesheet.

import {A2uiLitElement, ActionSchema, ChildListSchema, ChildSchema, DynamicBooleanSchema, DynamicNumberSchema, DynamicStringListSchema, DynamicStringSchema, DynamicValueSchema, html, nothing, z} from '../third_party/a2ui_bundle/a2ui.bundle.js';
import {COMPONENTS} from './spec.js';

export {html, nothing};

const TAB = () => z.object({
  title: DynamicStringSchema.optional(),
  icon: z.string().optional(),
  child: ChildSchema,
}).passthrough();

const KIND = {
  str: () => DynamicStringSchema,
  num: () => DynamicNumberSchema,
  bool: () => DynamicBooleanSchema,
  strList: () => DynamicStringListSchema,
  value: () => DynamicValueSchema,
  number: () => z.number(),
  child: () => ChildSchema,
  children: () => ChildListSchema,
  action: () => ActionSchema,
  tabs: () => z.array(TAB()),
};

/** Zod object schema for a spec component. */
export function zodFor(name) {
  const spec = COMPONENTS[name];
  const shape = {};
  for (const [prop, p] of Object.entries(spec.props)) {
    let s = p.kind === 'enum' ? z.enum(p.values) : KIND[p.kind]();
    if (!p.required) s = s.optional();
    shape[prop] = s;
  }
  return z.object(shape).passthrough();
}

/** "NumberSlider" -> "bui-number-slider". */
export const tagFor = (name) => 'bui-' + name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** UI unit in px (Blender widget_unit at the current scale). */
export function unitPx(el) {
  const s = parseFloat(getComputedStyle(el).getPropertyValue('--bui-scale'));
  return 20 * (Number.isFinite(s) && s > 0 ? s : 1);
}

export class BuiElement extends A2uiLitElement {
  constructor() {
    super();
    /** Local overrides for literal (unbound) values the user changed. */
    this._local = new Map();
  }

  createRenderRoot() {
    return this;
  }

  /** Resolved props (or {} before the controller is ready). */
  get p() {
    return this.controller?.props || {};
  }

  /** Raw (unresolved) component properties as sent by the agent. */
  raw(prop) {
    return this.context?.componentModel?.properties?.[prop];
  }

  isBound(prop) {
    const r = this.raw(prop);
    return isObj(r) && (typeof r['@path'] === 'string' || typeof r.path === 'string');
  }

  /** Current value of a prop: the user's local edit for literals, else the bound value. */
  val(prop, fallback) {
    if (!this.isBound(prop) && this._local.has(prop)) return this._local.get(prop);
    const v = this.p[prop];
    return v === undefined || v === null ? fallback : v;
  }

  /** Writes a prop: through the data model when bound, else locally. */
  set(prop, value) {
    if (this.isBound(prop)) {
      const setter = this.p['set' + cap(prop)];
      if (typeof setter === 'function') setter(value);
    } else {
      this._local.set(prop, value);
    }
    this.requestUpdate();
  }

  get enabled() {
    return this.p.enabled !== false;
  }

  /**
   * Dispatches the component's action prop (default "action"), merging
   * `extra` into an event's context. No-op when the prop is absent.
   */
  fire(extra = {}, prop = 'action') {
    const raw = this.raw(prop);
    if (!isObj(raw) || !this.enabled) return;
    let action = raw;
    try {
      const dc = this.context.dataContext;
      if (typeof dc.resolveAction === 'function') action = dc.resolveAction(raw);
    } catch (e) {
      console.warn('[bui] resolveAction failed', e);
    }
    if (isObj(action) && isObj(action.event)) {
      action = {...action, event: {...action.event, context: {...(action.event.context || {}), ...extra}}};
    }
    try {
      this.context.dispatchAction(action);
    } catch (e) {
      console.error('[bui] dispatchAction failed', e);
    }
  }

  willUpdate(changed) {
    super.willUpdate(changed);
    const p = this.p;
    if (typeof p.weight === 'number') this.style.flex = `${p.weight} 1 0`;
    else this.style.removeProperty('flex');
    this.classList.toggle('bui-disabled', p.enabled === false);
    if (typeof p.description === 'string' && p.description) this.dataset.tip = p.description;
    else delete this.dataset.tip;
    this.applyAccessibilityAttributes?.(p.accessibility);
  }

  /** Renders a ChildList / child id value through the library. */
  kids(v) {
    if (v == null) return nothing;
    const list = Array.isArray(v) ? v : [v];
    return list.map((c) => this.renderNode(c));
  }
}

/** Normalizes Dropdown / EnumRow / ListView items to {label, value, icon, description}. */
export function normItems(items, icons) {
  const list = Array.isArray(items) ? items : [];
  const ic = Array.isArray(icons) ? icons : null;
  return list.map((it, i) => {
    const o = isObj(it) ? it : {label: String(it)};
    const label = String(o.label ?? o.name ?? o.value ?? '');
    return {
      ...o,
      label,
      value: o.value != null ? String(o.value) : label,
      icon: o.icon || (ic && ic[i]) || '',
      description: o.description || '',
    };
  });
}

/** [r,g,b,a] floats or "#rrggbb[aa]" -> [r,g,b,a] floats. */
export function toRgba(v) {
  if (Array.isArray(v)) {
    const [r = 0, g = 0, b = 0, a = 1] = v.map(Number);
    return [r, g, b, a];
  }
  if (typeof v === 'string' && /^#?[0-9a-f]{6}([0-9a-f]{2})?$/i.test(v.trim())) {
    const h = v.trim().replace('#', '');
    const n = (i) => parseInt(h.slice(i, i + 2), 16) / 255;
    return [n(0), n(2), n(4), h.length === 8 ? n(6) : 1];
  }
  return [0.5, 0.5, 0.5, 1];
}

/** Linear-ish display: floats 0..1 -> css rgba() (Blender shows display-space colors). */
export function cssColor(v) {
  if (typeof v === 'string' && !/^#?[0-9a-f]{6}([0-9a-f]{2})?$/i.test(v.trim())) return v;
  const [r, g, b, a] = toRgba(v);
  const c = (x) => Math.round(Math.max(0, Math.min(1, x)) * 255);
  return `rgba(${c(r)}, ${c(g)}, ${c(b)}, ${Math.max(0, Math.min(1, a))})`;
}

export function toHex(v) {
  const [r, g, b] = toRgba(v);
  const c = (x) => Math.round(Math.max(0, Math.min(1, x)) * 255).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`.toUpperCase();
}

export const clamp = (v, lo, hi) => Math.min(hi ?? Infinity, Math.max(lo ?? -Infinity, v));

/** Formats a number the way Blender number fields do. */
export function fmtNum(v, {precision, integer, suffix} = {}) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? '');
  const prec = integer ? 0 : (typeof precision === 'number' ? precision : 3);
  const s = n.toFixed(prec);
  if (!suffix) return s;
  return suffix === '°' || suffix === '%' ? s + suffix : `${s} ${suffix}`;
}

/**
 * Pointer drag helper: calls onMove(dx, dy, e) with deltas from the start and
 * onEnd(moved, e) on release. Shift is passed through for fine control.
 */
export function drag(e, {onMove, onEnd, lock = false}) {
  const x0 = e.clientX, y0 = e.clientY;
  let moved = false;
  const target = e.currentTarget || e.target;
  try {
    if (lock) target.setPointerCapture?.(e.pointerId);
  } catch {
  }
  const move = (ev) => {
    const dx = ev.clientX - x0, dy = ev.clientY - y0;
    if (!moved && Math.abs(dx) + Math.abs(dy) < 3) return;
    moved = true;
    onMove?.(dx, dy, ev);
  };
  const up = (ev) => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    window.removeEventListener('pointercancel', up);
    onEnd?.(moved, ev);
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
  window.addEventListener('pointercancel', up);
}

/**
 * Opens a floating popup (menus, pickers, popovers) positioned under/near an
 * anchor inside the nearest `.bui-root`, closing on outside press or Escape.
 * `render(container, close)` fills it. Returns close().
 */
export function popup(anchor, render, {placement = 'below', className = '', offset = 2} = {}) {
  const root = anchor.closest('.bui-root') || document.body;
  const layer = root.querySelector(':scope > .bui-layer') || (() => {
    const l = document.createElement('div');
    l.className = 'bui-layer';
    root.appendChild(l);
    return l;
  })();
  const box = document.createElement('div');
  box.className = `bui-popup ${className}`;
  layer.appendChild(box);
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    box.remove();
    document.removeEventListener('pointerdown', outside, true);
    document.removeEventListener('keydown', esc, true);
    anchor.dispatchEvent(new CustomEvent('bui-popup-closed'));
  };
  const outside = (e) => {
    if (box.contains(e.target) || anchor.contains(e.target)) return;
    if (e.target.closest?.('.bui-popup')) return;  // nested popups (submenus, pickers)
    close();
  };
  const esc = (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      close();
    }
  };
  render(box, close);
  const place = () => {
    const ra = anchor.getBoundingClientRect();
    const rr = layer.getBoundingClientRect();
    const rb = box.getBoundingClientRect();
    let x, y;
    if (placement === 'right') {
      x = ra.right - rr.left + offset;
      y = ra.top - rr.top - 4;
    } else if (placement === 'center') {
      x = ra.left - rr.left + ra.width / 2 - rb.width / 2;
      y = ra.top - rr.top + ra.height / 2 - rb.height / 2;
    } else if (placement === 'over') {
      x = ra.left - rr.left;
      y = ra.top - rr.top;
    } else {
      x = ra.left - rr.left;
      y = ra.bottom - rr.top + offset;
    }
    const maxX = Math.max(0, layer.clientWidth - rb.width - 4);
    const maxY = Math.max(0, layer.clientHeight - rb.height - 4);
    if (placement === 'below' && y > maxY && ra.top - rr.top - rb.height - offset > 0) {
      y = ra.top - rr.top - rb.height - offset;
    }
    box.style.left = `${clamp(x, 4, maxX)}px`;
    box.style.top = `${clamp(y, 4, Math.max(4, maxY))}px`;
  };
  place();
  requestAnimationFrame(place);
  setTimeout(() => {
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', esc, true);
  }, 0);
  return close;
}

/** Defines a WebComponentImplementation for a spec component. */
export function impl(name, Element) {
  Element.tagName = tagFor(name);
  return {name, schema: zodFor(name), tagName: Element.tagName, element: Element};
}
