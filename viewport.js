/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Shows an A2UI surface rendered by BUI's native renderer on the server.
//
// The browser does no UI rendering: A2UI messages go to the server over a
// WebSocket (/ws/surface), where a2ui_bui (official A2UI Python framework +
// BUI, Blender's UI engine) renders them headlessly; damaged regions come back
// as PNG tiles painted onto a canvas, and pointer / keyboard input goes back to
// BUI. Same contract the old in-browser renderer had:
//
//   const s = mountSurface(container, messages, {theme, scale, onAction, onData, onError});
//   s.update(moreMessages); s.getData(); s.setTheme('light'); s.setScale(1.5); s.destroy();

const TK_KEYS = {
  Enter: 'Return', Backspace: 'BackSpace', Escape: 'Escape', Tab: 'Tab', Delete: 'Delete',
  ArrowLeft: 'Left', ArrowRight: 'Right', ArrowUp: 'Up', ArrowDown: 'Down', Home: 'Home', End: 'End',
  PageUp: 'Prior', PageDown: 'Next', Insert: 'Insert', ' ': 'space', Shift: 'Shift_L',
  Control: 'Control_L', Alt: 'Alt_L', Meta: 'Super_L', CapsLock: 'Caps_Lock',
  '-': 'minus', '+': 'plus', '=': 'equal', '.': 'period', ',': 'comma', '/': 'slash',
  '*': 'asterisk', '(': 'parenleft', ')': 'parenright',
};

function keysym(e) {
  if (TK_KEYS[e.key]) return TK_KEYS[e.key];
  if (/^F\d{1,2}$/.test(e.key)) return e.key;
  if (e.key.length === 1) return /[a-z]/i.test(e.key) ? e.key : e.key;
  return e.key;
}

const mods = (e) => ({shift: e.shiftKey, ctrl: e.ctrlKey || e.metaKey, alt: e.altKey});

export function mountSurface(container, messages = [], opts = {}) {
  const doc = container.ownerDocument || document;
  const root = doc.createElement('div');
  root.className = 'bui-root bui-native';
  const canvas = doc.createElement('canvas');
  canvas.className = 'bui-canvas';
  canvas.tabIndex = 0;
  canvas.setAttribute('role', 'application');
  canvas.setAttribute('aria-label', 'BUI surface (rendered by Blender\'s UI engine)');
  const status = doc.createElement('div');
  status.className = 'bui-status';
  status.textContent = 'Connecting to the BUI renderer…';
  root.append(canvas, status);
  container.appendChild(root);
  const g = canvas.getContext('2d');

  const dpr = () => Math.max(1, Math.min(3, window.devicePixelRatio || 1));
  let ratio = dpr();
  let scale = Number(opts.scale) || 1;
  let data = null;
  let closed = false;
  let open = false;
  const pending = [];
  let paint = Promise.resolve();

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/surface`);
  const send = (cmd) => {
    if (closed) return;
    if (open) ws.send(JSON.stringify(cmd));
    else pending.push(cmd);
  };
  const cssWidth = () => {
    const cs = getComputedStyle(container);
    const inner = container.clientWidth - parseFloat(cs.paddingLeft || 0) - parseFloat(cs.paddingRight || 0);
    return Math.max(200, Math.floor(inner > 0 ? inner : (opts.width || 900)));
  };

  ws.addEventListener('open', () => {
    open = true;
    ws.send(JSON.stringify({
      t: 'open', messages, theme: opts.theme || 'dark', scale: scale * ratio,
      width: Math.round(cssWidth() * ratio),
    }));
    for (const c of pending.splice(0)) ws.send(JSON.stringify(c));
  });
  ws.addEventListener('close', () => {
    if (!closed) {
      status.hidden = false;
      status.textContent = 'Disconnected from the BUI renderer. Is server.py running with the a2ui_bui venv?';
    }
  });
  ws.addEventListener('message', (e) => {
    const ev = JSON.parse(e.data);
    if (ev.t === 'size') {
      paint = paint.then(() => {
        canvas.width = ev.w;
        canvas.height = ev.h;
        canvas.style.width = `${ev.w / ratio}px`;
        canvas.style.height = `${ev.h / ratio}px`;
      });
    } else if (ev.t === 'frame') {
      status.hidden = true;
      const tiles = ev.tiles;
      // Decode in parallel, paint in arrival order.
      const decoded = tiles.map((t) => fetch(`data:image/png;base64,${t.png}`)
          .then((r) => r.blob()).then((b) => createImageBitmap(b)));
      paint = paint.then(() => Promise.all(decoded)).then((bitmaps) => {
        bitmaps.forEach((bm, i) => {
          g.drawImage(bm, tiles[i].x, tiles[i].y);
          bm.close?.();
        });
      }).catch((err) => console.warn('[bui] tile', err));
    } else if (ev.t === 'cursor') {
      canvas.style.cursor = ev.css;
    } else if (ev.t === 'action') {
      opts.onAction?.(ev.payload);
    } else if (ev.t === 'data') {
      data = ev.data;
      opts.onData?.(data);
    } else if (ev.t === 'error') {
      const er = ev.error || {};
      opts.onError?.(`${er.code || 'ERROR'}: ${er.message || ''}`);
    }
  });

  // ---- input -------------------------------------------------------------------
  const pos = (e) => {
    const r = canvas.getBoundingClientRect();
    return {x: Math.round((e.clientX - r.left) * ratio), y: Math.round((e.clientY - r.top) * ratio)};
  };
  let held = false;
  let moveQueued = null;
  canvas.addEventListener('pointerdown', (e) => {
    canvas.focus({preventScroll: true});
    canvas.setPointerCapture(e.pointerId);
    held = e.button === 0;
    send({t: 'mouse', k: 'down', ...pos(e), b: e.button === 2 ? 3 : 1, mods: mods(e)});
    e.preventDefault();
  });
  canvas.addEventListener('pointerup', (e) => {
    held = false;
    send({t: 'mouse', k: 'up', ...pos(e), b: e.button === 2 ? 3 : 1, mods: mods(e)});
  });
  canvas.addEventListener('pointermove', (e) => {
    const first = moveQueued === null;
    moveQueued = {t: 'mouse', k: 'move', ...pos(e), held, mods: mods(e)};
    if (first) {
      requestAnimationFrame(() => {
        send(moveQueued);
        moveQueued = null;
      });
    }
  });
  canvas.addEventListener('pointerleave', () => send({t: 'mouse', k: 'move', x: -1, y: -1, mods: {}}));
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const d = e.deltaMode === 1 ? -e.deltaY / 3 : -e.deltaY / 100;
    send({t: 'mouse', k: 'wheel', ...pos(e), d, mods: mods(e)});
  }, {passive: false});
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('dblclick', (e) => e.preventDefault());
  canvas.addEventListener('keydown', (e) => {
    // Keep browser reload / devtools; BUI gets everything else (Ctrl+Z, Tab, math typing).
    if (e.key === 'F5' || e.key === 'F12' || ((e.ctrlKey || e.metaKey) && /^[rlt]$/i.test(e.key))) return;
    e.preventDefault();
    const ch = e.key.length === 1 ? e.key : (e.key === 'Enter' ? '\r' : e.key === 'Tab' ? '\t' : '');
    send({t: 'key', char: ch, keysym: keysym(e), mods: mods(e)});
  });
  canvas.addEventListener('keyup', (e) => {
    send({t: 'key', up: true, keysym: keysym(e), mods: mods(e)});
  });

  const ro = new ResizeObserver(() => {
    const r = dpr();
    if (r !== ratio) {
      ratio = r;
      send({t: 'scale', v: scale * ratio});
    }
    send({t: 'width', w: Math.round(cssWidth() * ratio)});
  });
  ro.observe(container);

  return {
    root,
    canvas,
    update(msgs) {
      if (msgs?.length) send({t: 'update', messages: msgs});
    },
    reset(msgs) {
      send({t: 'reset', messages: msgs || []});
    },
    getData() {
      return data;
    },
    setTheme(name) {
      send({t: 'theme', name});
    },
    setScale(v) {
      scale = Number(v) || 1;
      send({t: 'scale', v: scale * ratio});
    },
    destroy() {
      closed = true;
      ro.disconnect();
      try {
        ws.close();
      } catch (e) { /* already closed */ }
      root.remove();
    },
  };
}
