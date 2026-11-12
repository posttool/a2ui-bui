/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Mounts A2UI v1.0 message streams with the BUI catalog.
//
//   const s = mountSurface(container, messages, {theme: 'dark', scale: 1.25,
//                                              onAction, onData, onError});
//   s.update(moreMessages); s.getData(); s.destroy();
//
// Also owns the Blender-style tooltip (any element with data-tip, shown
// after a hover delay) for everything inside a .bui-root.

import {MessageProcessor} from '../third_party/a2ui_bundle/a2ui.bundle.js';
import {BUI_STYLESHEETS, buiCatalog, MISSING} from './catalog.js';

export {BUI_CATALOG_ID, MISSING} from './catalog.js';

let assetsInjected = false;
function ensureAssets(doc) {
  if (assetsInjected) return;
  assetsInjected = true;
  const add = (href) => {
    const l = doc.createElement('link');
    l.rel = 'stylesheet';
    l.href = href;
    doc.head.appendChild(l);
  };
  add('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
  add('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block');
  BUI_STYLESHEETS.forEach(add);
}

/** Blender tooltips: hover an element with data-tip for 500 ms. */
function installTooltips(root) {
  let timer = 0, tip = null, target = null;
  const hide = () => {
    clearTimeout(timer);
    tip?.remove();
    tip = null;
    target = null;
  };
  const show = (el) => {
    hide();
    target = el;
    timer = setTimeout(() => {
      if (!target || !target.isConnected) return;
      tip = document.createElement('div');
      tip.className = 'bui-tooltip';
      tip.textContent = target.dataset.tip;
      root.appendChild(tip);
      const rr = root.getBoundingClientRect();
      const rt = target.getBoundingClientRect();
      const rb = tip.getBoundingClientRect();
      let x = rt.left - rr.left + Math.min(rt.width / 2, 40) - 8;
      let y = rt.bottom - rr.top + 6;
      if (y + rb.height > root.clientHeight) y = rt.top - rr.top - rb.height - 6;
      x = Math.max(4, Math.min(x, root.clientWidth - rb.width - 4));
      tip.style.left = `${x}px`;
      tip.style.top = `${Math.max(4, y)}px`;
    }, 500);
  };
  root.addEventListener('pointerover', (e) => {
    const el = e.target.closest?.('[data-tip]');
    if (!el || !root.contains(el) || !el.dataset.tip) {
      if (target) hide();
      return;
    }
    if (el !== target) show(el);
  });
  root.addEventListener('pointerleave', hide);
  root.addEventListener('pointerdown', hide, true);
  root.addEventListener('wheel', hide, {passive: true});
}

export function mountSurface(container, messages = [], opts = {}) {
  const doc = container.ownerDocument || document;
  ensureAssets(doc);
  const root = doc.createElement('div');
  root.className = `bui-root bui-theme-${opts.theme === 'light' ? 'light' : 'dark'}`;
  if (opts.scale) root.style.setProperty('--bui-scale', String(opts.scale));
  container.appendChild(root);
  installTooltips(root);

  const errors = [];
  const err = (m) => {
    errors.push(String(m));
    opts.onError?.(String(m));
  };
  const processor = new MessageProcessor([buiCatalog], (action) => {
    opts.onAction?.({version: 'v1.0', action});
  }, {version: 'v1.0'});

  const views = new Map();
  const surfaces = new Map();
  const subs = [];
  subs.push(processor.onSurfaceCreated((surface) => {
    const el = doc.createElement('a2ui-surface');
    el.className = 'bui-surface';
    el.surface = surface;
    views.set(surface.id, el);
    surfaces.set(surface.id, surface);
    root.appendChild(el);
    try {
      const sub = surface.dataModel?.subscribe?.('/', () => opts.onData?.(surface.id, getData(surface.id)));
      if (sub) subs.push(sub);
    } catch {
    }
  }));
  subs.push(processor.onSurfaceDeleted((id) => {
    views.get(id)?.remove();
    views.delete(id);
    surfaces.delete(id);
  }));

  const runOne = (msg) => {
    try {
      processor.processMessages([msg]);
      return;
    } catch (e) {
      const uc = msg.updateComponents;
      if (!uc || !Array.isArray(uc.components) || uc.components.length < 2) {
        err(`${Object.keys(msg).find((k) => k !== 'version')}: ${e.message || e}`);
        return;
      }
    }
    for (const comp of msg.updateComponents.components) {
      try {
        processor.processMessages([{version: msg.version, updateComponents: {surfaceId: msg.updateComponents.surfaceId, components: [comp]}}]);
      } catch (e2) {
        err(`component "${comp.id}" (${comp.component}): ${e2.message || e2}`);
      }
    }
  };

  function getData(id) {
    const s = surfaces.get(id ?? [...surfaces.keys()][0]);
    try {
      return s?.dataModel?.get?.('/') ?? null;
    } catch {
      return null;
    }
  }

  const update = (msgs) => {
    for (const m of msgs || []) runOne(m);
  };
  update(messages);

  return {
    root,
    processor,
    errors,
    update,
    getData,
    destroy() {
      for (const s of subs) {
        try {
          typeof s === 'function' ? s() : s?.unsubscribe?.();
        } catch {
        }
      }
      root.remove();
    },
  };
}
