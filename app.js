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

// Gallery for the BUI A2UI catalog: lists showcases (message streams in
// showcases/*.json), renders them with bui/host.js, logs actions, shows the
// live data model and payload, and computes component coverage.

import {mountSurface} from './bui/host.js';
import {COMPONENTS, COMPONENT_NAMES, BUI_CATALOG_ID} from './bui/spec.js';
import {initCreate, onCreateAction} from './create.js';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

const state = {
  showcases: [],
  current: null,
  mounted: null,
  theme: localStorage.getItem('bui-demo.theme') || 'dark',
  scale: localStorage.getItem('bui-demo.scale') || '1.25',
  streamTimer: 0,
};

function highlight(json) {
  return esc(json).replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b)/gi,
      (m, str, colon, bool, num) => {
        if (str) return colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`;
        if (bool) return `<span class="b">${bool}</span>`;
        return `<span class="n">${num}</span>`;
      });
}

/** {componentName: count} for a showcase's messages. */
function usage(sc) {
  const out = {};
  for (const m of sc.messages || []) {
    for (const c of m.updateComponents?.components || []) out[c.component] = (out[c.component] || 0) + 1;
  }
  return out;
}

async function load() {
  const indexPath = new URLSearchParams(location.search).get('index') || 'showcases/index.json';
  const index = await (await fetch(indexPath, {cache: 'no-store'})).json();
  const loaded = await Promise.all(index.showcases.map(async (entry) => {
    const sc = await (await fetch(`showcases/${entry.file}`, {cache: 'no-store'})).json();
    return {...sc, id: entry.file.replace(/\.json$/, ''), group: entry.group || sc.group || 'Showcases'};
  }));
  state.showcases = loaded.map((sc) => ({...sc, usage: usage(sc)}));
}

function drawList() {
  const q = $('#filter').value.trim().toLowerCase();
  const groups = new Map();
  for (const sc of state.showcases) {
    const hay = `${sc.name} ${sc.description} ${Object.keys(sc.usage).join(' ')}`.toLowerCase();
    if (q && !hay.includes(q)) continue;
    if (!groups.has(sc.group)) groups.set(sc.group, []);
    groups.get(sc.group).push(sc);
  }
  $('#list').innerHTML = [...groups].map(([g, list]) => `<h3>${esc(g)}</h3>` + list.map((sc) => `
    <button class="sc ${state.current?.id === sc.id ? 'sel' : ''}" data-id="${esc(sc.id)}">
      <b>${esc(sc.name)}</b><small>${Object.keys(sc.usage).length} components · ${
      Object.values(sc.usage).reduce((a, b) => a + b, 0)} instances</small>
    </button>`).join('')).join('');
}

function logAction(payload) {
  const box = $('#actions');
  box.querySelector('.empty')?.remove();
  const a = payload.action || {};
  const ev = a.event || {};
  const el = document.createElement('div');
  el.className = 'ev flash';
  el.innerHTML = `<div class="ev-head"><span class="ev-name">${esc(ev.name || a.functionCall?.call || 'action')}</span>
    <span class="ev-src">${esc(a.sourceComponentId || ev.sourceComponentId || '')} · ${new Date().toLocaleTimeString()}</span></div>
    <pre>${highlight(JSON.stringify(payload, null, 2))}</pre>`;
  box.prepend(el);
}

function drawData() {
  const d = state.mounted?.getData?.();
  $('#data').innerHTML = highlight(JSON.stringify(d ?? {}, null, 2));
}

function mount(messages) {
  clearTimeout(state.streamTimer);
  state.mounted?.destroy();
  $('#errors').hidden = true;
  $('#errors').textContent = '';
  const host = $('#surface');
  host.textContent = '';
  const errs = [];
  state.renderErrors = errs;
  state.mounted = mountSurface(host, messages, {
    theme: state.theme,
    scale: Number(state.scale),
    onAction: (payload) => {
      logAction(payload);
      if (state.view === 'create') onCreateAction(payload);
    },
    onData: () => drawData(),
    onError: (m) => {
      errs.push(m);
      $('#errors').hidden = false;
      $('#errors').textContent = errs.join('\n');
    },
  });
  drawData();
  window.__bui = state.mounted;
}

function select(id) {
  const sc = state.showcases.find((s) => s.id === id) || state.showcases[0];
  if (!sc) return;
  state.current = sc;
  history.replaceState(null, '', `#${sc.id}`);
  $('#replay').hidden = false;
  $('#sc-title').textContent = sc.name;
  $('#sc-desc').textContent = sc.description || '';
  $('#win-title').textContent = sc.window || sc.name;
  $('#sc-chips').innerHTML = Object.entries(sc.usage).sort((a, b) => b[1] - a[1])
                                 .map(([n, c]) => `<span class="chip">${esc(n)}${c > 1 ? ` <b>×${c}</b>` : ''}</span>`).join('');
  $('#payload').innerHTML = highlight(JSON.stringify(sc.messages, null, 2));
  $('#actions').innerHTML = '<p class="empty">Interact with the surface. Actions the renderer would send to the agent appear here.</p>';
  $('.window').style.width = sc.width ? `${Math.min(sc.width, ($('.stage').clientWidth || 1200) - 60)}px` : '';
  mount(sc.messages);
  drawList();
}

function stream() {
  const sc = state.current;
  if (!sc) return;
  const msgs = sc.messages;
  mount([]);
  let i = 0;
  const step = () => {
    if (i >= msgs.length) return;
    const m = msgs[i++];
    // Stream large component lists in chunks so the surface visibly builds up.
    const uc = m.updateComponents;
    if (uc && uc.components.length > 6) {
      const chunks = [];
      for (let j = 0; j < uc.components.length; j += 6) chunks.push(uc.components.slice(j, j + 6));
      let k = 0;
      const sub = () => {
        if (k >= chunks.length) {
          state.streamTimer = setTimeout(step, 250);
          return;
        }
        state.mounted.update([{version: m.version, updateComponents: {surfaceId: uc.surfaceId, components: chunks[k++]}}]);
        drawData();
        state.streamTimer = setTimeout(sub, 160);
      };
      sub();
      return;
    }
    state.mounted.update([m]);
    drawData();
    state.streamTimer = setTimeout(step, 350);
  };
  step();
}

function drawCoverage() {
  const counts = Object.fromEntries(COMPONENT_NAMES.map((n) => [n, {count: 0, uses: []}]));
  for (const sc of state.showcases) {
    for (const [n, c] of Object.entries(sc.usage)) {
      if (!counts[n]) counts[n] = {count: 0, uses: [], unknown: true};
      counts[n].count += c;
      counts[n].uses.push(sc);
    }
  }
  const max = Math.max(...Object.values(counts).map((c) => c.count), 1);
  const covered = COMPONENT_NAMES.filter((n) => counts[n].count > 0).length;
  const total = Object.values(counts).reduce((a, c) => a + c.count, 0);
  const unknown = Object.entries(counts).filter(([, c]) => c.unknown).map(([n]) => n);
  const groups = [...new Set(COMPONENT_NAMES.map((n) => COMPONENTS[n].group))];
  $('#view-coverage').innerHTML = `
    <h2>Component coverage</h2>
    <p class="lede">Every component in the BUI catalog is rendered by at least one showcase. Counts are component instances across all
      showcase payloads (templated children count once per definition, not per data row).</p>
    <div class="cov-summary">
      <div>${covered}/${COMPONENT_NAMES.length}<small>components covered</small></div>
      <div>${state.showcases.length}<small>showcases</small></div>
      <div>${total}<small>component instances</small></div>
      ${unknown.length ? `<div style="color:var(--hl-bug)">${unknown.length}<small>unknown names: ${esc(unknown.join(', '))}</small></div>` : ''}
    </div>
    <table class="matrix"><thead><tr><th>Group</th><th>Component</th><th>Uses</th><th style="width:180px"></th><th>Showcases</th></tr></thead><tbody>
    ${groups.map((g) => COMPONENT_NAMES.filter((n) => COMPONENTS[n].group === g).map((n, i) => {
    const c = counts[n];
    return `<tr><td>${i === 0 ? esc(g) : ''}</td><td class="name">${n}</td><td class="count ${c.count ? '' : 'zero'}">${c.count}</td>
        <td><div class="bar" style="width:${(c.count / max) * 100}%"></div></td>
        <td><div class="uses">${c.uses.map((sc) => `<a href="#${esc(sc.id)}" data-goto="${esc(sc.id)}">${esc(sc.name)}</a>`).join('')}</div></td></tr>`;
  }).join('')).join('')}
    </tbody></table>`;
}

function drawCatalog() {
  const groups = [...new Set(COMPONENT_NAMES.map((n) => COMPONENTS[n].group))];
  $('#view-catalog').innerHTML = `
    <h2>BUI catalog</h2>
    <p class="lede">catalogId <code>${esc(BUI_CATALOG_ID)}</code> · ${COMPONENT_NAMES.length} components. Download the
      <a href="bui/catalog.json" target="_blank">catalog.json</a> (A2UI v1.0 catalog definition) to give an agent the schema.</p>
    <div class="cat-grid">${groups.map((g) => COMPONENT_NAMES.filter((n) => COMPONENTS[n].group === g).map((n) => {
    const c = COMPONENTS[n];
    return `<div class="cat-card"><div class="grp">${esc(g)}</div><h3>${n}</h3><p>${esc(c.doc)}</p><table>${
        Object.entries(c.props).map(([k, p]) => `<tr><td>${k}${p.required ? '<span class="req">*</span>' : ''}</td><td><span class="kind">${
            p.kind === 'enum' ? esc(p.values.join(' | ')) : p.kind}</span>${p.doc ? ` — ${esc(p.doc)}` : ''}</td></tr>`).join('')}</table></div>`;
  }).join('')).join('')}</div>`;
}

function setView(v) {
  const prev = state.view;
  state.view = v;
  document.querySelectorAll('.top-tab').forEach((b) => b.classList.toggle('sel', b.dataset.view === v));
  const main = v === 'create' ? 'gallery' : v;
  document.querySelectorAll('.view').forEach((m) => { m.hidden = m.id !== `view-${main}`; });
  $('#create-panel').hidden = v !== 'create';
  $('#gallery-panel').hidden = v !== 'gallery';
  $('#replay').hidden = v === 'create';
  if (v === 'create' && prev !== 'create') ctx.showCreate();
  if (v === 'gallery' && prev !== 'gallery') {
    ctx.leaveCreate();
    select(state.current?.id);
  }
  if (v === 'coverage') drawCoverage();
  if (v === 'catalog') drawCatalog();
}

const ctx = {
  state, $, esc, highlight, mount, drawData,
  setHeader(title, desc, usage) {
    $('#sc-title').textContent = title;
    $('#sc-desc').textContent = desc || '';
    $('#sc-chips').innerHTML = Object.entries(usage || {}).sort((a, b) => b[1] - a[1])
                                   .map(([n, c]) => `<span class="chip">${esc(n)}${c > 1 ? ` <b>×${c}</b>` : ''}</span>`).join('');
  },
  clearActions() {
    $('#actions').innerHTML = '<p class="empty">Interact with the surface. Actions the renderer would send to the agent appear here.</p>';
  },
  logNote(title, body) {
    const box = $('#actions');
    box.querySelector('.empty')?.remove();
    const el = document.createElement('div');
    el.className = 'ev agent flash';
    el.innerHTML = `<div class="ev-head"><span class="ev-name">${esc(title)}</span><span class="ev-src">${new Date().toLocaleTimeString()}</span></div>${body ? `<pre>${esc(body)}</pre>` : ''}`;
    box.prepend(el);
  },
};

async function main() {
  $('#theme').value = state.theme;
  $('#scale').value = state.scale;
  await load();
  drawList();
  $('#list').addEventListener('click', (e) => {
    const b = e.target.closest('.sc');
    if (b) select(b.dataset.id);
  });
  $('#filter').addEventListener('input', drawList);
  $('#reset').addEventListener('click', () => select(state.current?.id));
  $('#replay').addEventListener('click', stream);
  $('#theme').addEventListener('change', (e) => {
    state.theme = e.target.value;
    localStorage.setItem('bui-demo.theme', state.theme);
    state.mounted?.root.classList.toggle('bui-theme-light', state.theme === 'light');
    state.mounted?.root.classList.toggle('bui-theme-dark', state.theme !== 'light');
  });
  $('#scale').addEventListener('change', (e) => {
    state.scale = e.target.value;
    localStorage.setItem('bui-demo.scale', state.scale);
    state.mounted?.root.style.setProperty('--bui-scale', state.scale);
  });
  document.querySelectorAll('.top-tab').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  document.querySelectorAll('.itab').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.itab').forEach((x) => x.classList.toggle('sel', x === b));
    document.querySelectorAll('.ipane').forEach((p) => { p.hidden = p.dataset.pane !== b.dataset.tab; });
    if (b.dataset.tab === 'data') drawData();
  }));
  $('#view-coverage').addEventListener('click', (e) => {
    const a = e.target.closest('[data-goto]');
    if (!a) return;
    e.preventDefault();
    setView('gallery');
    select(a.dataset.goto);
  });
  window.addEventListener('hashchange', () => {
    const id = location.hash.slice(1);
    if (id && state.showcases.some((x) => x.id === id) && id !== state.current?.id) {
      if (state.view !== 'gallery') setView('gallery');
      else select(id);
    }
  });
  await initCreate(ctx);
  const hashId = location.hash.slice(1);
  if (hashId && state.showcases.some((x) => x.id === hashId)) {
    state.current = state.showcases.find((x) => x.id === hashId);
    setView('gallery');
  } else {
    state.current = state.showcases[0];
    setView('create');
  }
  window.__demo = {ready: true, state, select, setView, ctx};
}

main().catch((e) => {
  console.error(e);
  $('#errors').hidden = false;
  $('#errors').textContent = String(e.stack || e);
  window.__demo = {ready: true, error: String(e)};
});
