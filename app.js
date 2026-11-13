/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Gallery for the BUI A2UI catalog: lists showcases (message streams in
// showcases/*.json), renders them with BUI on the server (viewport.js), logs actions, shows the
// live data model and payload, and computes component coverage.

import {mountSurface} from './viewport.js';
import {COMPONENTS, COMPONENT_NAMES, BUI_CATALOG_ID} from './bui/spec.js';
import {initCreate} from './create.js';

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

const state = {
  showcases: [],
  current: null,
  mounted: null,
  activeAppId: null,
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
  const name = ev.name || a.name || a.functionCall?.call || 'action';
  const el = document.createElement('div');
  el.className = 'ev flash';
  el.dataset.actionName = name;
  el.innerHTML = `<div class="ev-head"><span class="ev-name">${esc(name)}</span>
    <span class="ev-badge"></span>
    <span class="ev-src">${esc(a.sourceComponentId || ev.sourceComponentId || '')} · ${new Date().toLocaleTimeString()}</span></div>
    <pre>${highlight(JSON.stringify(payload, null, 2))}</pre>`;
  box.prepend(el);
}

function tagLastAction(ev) {
  const el = [...document.querySelectorAll('#actions .ev')].find(
      (x) => x.dataset.actionName === ev.name && !x.querySelector('.ev-badge')?.textContent);
  if (!el) return;
  const b = el.querySelector('.ev-badge');
  const dur = ev.ms >= 1000 ? `${(ev.ms / 1000).toFixed(1)} s` : `${Math.round(ev.ms)} ms`;
  b.className = `ev-badge ${ev.source === 'code' ? 'code' : 'agent'}`;
  b.textContent = `${ev.source} · ${dur}${ev.summary ? ` · ${ev.summary}` : ''}`;
}

async function refreshBackend(appId) {
  if (!appId) {
    $('#backend-info').innerHTML = '<p class="empty">Open an app or click Build app to inspect its backend code, handlers, and versions.</p>';
    return;
  }
  try {
    const d = await (await fetch(`/api/apps/${encodeURIComponent(appId)}`)).json();
    const handlers = new Set(d.handlers || []);
    const declared = [...new Set((d.actions || []).map((a) => a.name))];
    const chips = declared.map((n) => `<span class="chip ${handlers.has(n) ? 'ok' : ''}">${esc(n)}${
        handlers.has(n) ? ' ✓' : ' (agent fallback)'}</span>`).join('') || '<span class="muted">No actions declared</span>';
    const versions = (d.versions || []).slice().reverse().map((v) => `
      <div class="ver-row"><b>v${v.version}</b> <span>${esc(v.source)}</span> — ${esc(v.summary || '')}
      <button class="btn tiny" data-rollback="${v.version}">Restore</button></div>`).join('') || '<p class="muted">No versions saved yet.</p>';
    $('#backend-info').innerHTML = `
      <div class="be-sec"><h4>Handlers (${handlers.size}/${declared.length})</h4><div class="chips">${chips}</div></div>
      <div class="be-sec"><h4>Versions</h4>${versions}</div>
      <div class="be-sec"><h4>backend/main.py</h4><pre class="code">${esc(d.main_py || '# not written yet')}</pre></div>
      <div class="be-sec"><h4>backend/test_main.py</h4><pre class="code">${esc(d.test_py || '# no tests yet')}</pre></div>`;
  } catch (e) {
    $('#backend-info').innerHTML = `<p class="empty">${esc(e)}</p>`;
  }
}

function drawData() {
  const d = state.mounted?.getData?.();
  $('#data').innerHTML = highlight(JSON.stringify(d ?? {}, null, 2));
}

function mount(messages, opts = {}) {
  clearTimeout(state.streamTimer);
  state.mounted?.destroy();
  state.activeAppId = opts.appId || null;
  $('#errors').hidden = true;
  $('#errors').textContent = '';
  const host = $('#surface');
  host.textContent = '';
  const errs = [];
  state.renderErrors = errs;
  state.mounted = mountSurface(host, messages, {
    appId: state.activeAppId,
    theme: state.theme,
    scale: Number(state.scale),
    onAction: (payload) => logAction(payload),
    onBackend: (ev) => {
      if (ev.t === 'action_handled') {
        tagLastAction(ev);
        refreshBackend(state.activeAppId);
      } else if (ev.t === 'handlers') {
        refreshBackend(state.activeAppId);
      } else if (ev.t === 'agent_status') {
        if (ev.text) ctx.setStatus?.(ev.text, '');
        else ctx.setStatus?.('', 'ok');
      }
    },
    onData: () => drawData(),
    onError: (m) => {
      errs.push(m);
      $('#errors').hidden = false;
      $('#errors').textContent = errs.join('\n');
    },
  });
  drawData();
  refreshBackend(state.activeAppId);
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

async function refreshAppsList() {
  try {
    const {apps} = await (await fetch('/api/apps')).json();
    if (!apps.length) {
      $('#apps-list').innerHTML = '<p class="muted">No apps yet. Describe an app above to create one.</p>';
      return;
    }
    $('#apps-list').innerHTML = apps.map((a) => `
      <div class="app-card" data-id="${esc(a.id)}">
        <div class="app-card-head">
          <h3>${esc(a.title || a.id)}</h3>
          <span class="chip ${a.has_backend ? 'ok' : ''}">${a.has_backend ? `v${a.backend_version || 1} backend` : 'UI only'}</span>
        </div>
        <p class="muted">${esc(a.prompt || '')}</p>
        <div class="app-cmd"><code>a2ui-bui --app ${esc(a.id)}</code></div>
        <div class="app-card-actions">
          <a class="btn primary" href="/app/${esc(a.id)}" target="_blank"><span class="ms">open_in_new</span>Open</a>
          <button class="btn" data-app-inspect="${esc(a.id)}"><span class="ms">code</span>Inspect</button>
          <button class="btn" data-app-build="${esc(a.id)}"><span class="ms">deployed_code</span>${a.has_backend ? 'Rebuild' : 'Build backend'}</button>
          <button class="btn" data-app-del="${esc(a.id)}"><span class="ms">delete</span></button>
        </div>
      </div>`).join('');
  } catch (e) {
    $('#apps-list').innerHTML = `<p class="muted">${esc(e)}</p>`;
  }
}

async function drawApps() {
  const el = $('#view-apps');
  if (!$('#apps-create-form')) {
    const modelOpts = $('#model')?.innerHTML || '<option value="">Default model</option>';
    el.innerHTML = `
      <h2>Apps</h2>
      <p class="doc-lead">Create any arbitrary app from a prompt (A2UI UI + ADK-generated Python backend in a sandbox), or open one of the saved apps below.</p>
      <form id="apps-create-form" class="apps-create">
        <textarea id="apps-prompt" rows="2" placeholder="Describe any app to build (e.g. 'A markdown note editor with tags and search', 'A habit tracker with streaks')…"></textarea>
        <div class="apps-create-row">
          <select id="apps-model">${modelOpts}</select>
          <button class="btn primary" type="submit" id="apps-create-btn"><span class="ms">deployed_code</span>Create &amp; Build App</button>
        </div>
        <div id="apps-build-status" class="build-status" hidden>
          <div class="build-status-head">
            <span class="spinner" id="apps-build-spin"></span>
            <span id="apps-build-line"></span>
            <a id="apps-build-open" class="btn primary" href="#" target="_blank" hidden><span class="ms">open_in_new</span>Open App</a>
          </div>
          <pre id="apps-build-log" class="build-log"></pre>
        </div>
      </form>
      <div id="apps-list" class="apps-grid">Loading…</div>`;
  }
  await refreshAppsList();
}

async function openAppInStage(appId) {
  const d = await (await fetch(`/api/apps/${encodeURIComponent(appId)}`)).json();
  setView('gallery');
  $('#replay').hidden = true;
  $('#sc-title').textContent = d.meta?.title || appId;
  $('#sc-desc').textContent = d.meta?.prompt || '';
  $('#win-title').textContent = `${d.meta?.title || appId} (live app)`;
  $('#sc-chips').innerHTML = (d.actions || []).map((a) => `<span class="chip">${esc(a.name)}</span>`).join('');
  $('#payload').innerHTML = highlight(JSON.stringify(d.messages || [], null, 2));
  ctx.clearActions();
  $('.window').style.width = d.meta?.width ? `${Math.min(d.meta.width, ($('.stage').clientWidth || 1200) - 60)}px` : '';
  mount([], {appId});
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
    if (!state.activeAppId) select(state.current?.id);
  }
  if (v === 'apps') drawApps();
  if (v === 'coverage') drawCoverage();
  if (v === 'catalog') drawCatalog();
}

const ctx = {
  state, $, esc, highlight, mount, drawData, openAppInStage, refreshBackend, setView,
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
    state.mounted?.setTheme(state.theme);
  });
  $('#scale').addEventListener('change', (e) => {
    state.scale = e.target.value;
    localStorage.setItem('bui-demo.scale', state.scale);
    state.mounted?.setScale(Number(state.scale));
  });
  document.querySelectorAll('.top-tab').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  document.querySelectorAll('.itab').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.itab').forEach((x) => x.classList.toggle('sel', x === b));
    document.querySelectorAll('.ipane').forEach((p) => { p.hidden = p.dataset.pane !== b.dataset.tab; });
    if (b.dataset.tab === 'data') drawData();
    if (b.dataset.tab === 'backend') refreshBackend(state.activeAppId);
  }));
  $('#backend-info').addEventListener('click', async (e) => {
    const rb = e.target.closest('[data-rollback]');
    if (!rb || !state.activeAppId) return;
    await fetch(`/api/apps/${encodeURIComponent(state.activeAppId)}/rollback`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({version: Number(rb.dataset.rollback)}),
    });
    refreshBackend(state.activeAppId);
  });
  $('#view-apps').addEventListener('submit', async (e) => {
    if (e.target.id !== 'apps-create-form') return;
    e.preventDefault();
    const prompt = ($('#apps-prompt')?.value || '').trim();
    if (!prompt) return;
    const model = $('#apps-model')?.value || '';
    const btn = $('#apps-create-btn');
    const box = $('#apps-build-status');
    const line = $('#apps-build-line');
    const log = $('#apps-build-log');
    const openLink = $('#apps-build-open');
    const spin = $('#apps-build-spin');
    btn.disabled = true;
    box.hidden = false;
    openLink.hidden = true;
    spin.hidden = false;
    const steps = [];
    const addStep = (t) => {
      steps.push(`[${new Date().toLocaleTimeString()}] ${t}`);
      log.textContent = steps.join('\n');
      log.scrollTop = log.scrollHeight;
      line.textContent = t;
    };
    try {
      addStep('Generating A2UI interface…');
      const gen = await ctx.generate({prompt, model}, () => {});
      if (gen.error || !gen.messages.length) throw new Error(gen.error || 'No UI messages generated');
      const title = gen.meta?.title || prompt.slice(0, 48);
      addStep(`UI generated: ${title} (${gen.messages.length} messages)`);
      const created = await (await fetch('/api/apps', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          title,
          width: gen.meta?.width || 900,
          prompt,
          model: gen.model || model,
          messages: gen.messages,
        }),
      })).json();
      if (!created.ok) throw new Error(created.error || 'Failed to save app');
      const appId = created.app.id;
      addStep(`Saved app '${appId}'; starting ADK backend builder…`);
      const res = await ctx.buildAppById(appId, (stepLine) => {
        steps.push(stepLine);
        log.textContent = steps.join('\n');
        log.scrollTop = log.scrollHeight;
        line.textContent = stepLine.replace(/^\[[^\]]+\]\s*/, '');
      });
      if (res?.ok) {
        line.textContent = `Ready: ${title} (v${res.version || 1})`;
        openLink.href = `/app/${encodeURIComponent(appId)}`;
        openLink.hidden = false;
      } else {
        line.textContent = `Build failed: ${res?.summary || 'check log'}`;
      }
      await refreshAppsList();
    } catch (err) {
      addStep(`Error: ${err.message || err}`);
    } finally {
      spin.hidden = true;
      btn.disabled = false;
    }
  });
  $('#view-apps').addEventListener('click', async (e) => {
    const ins = e.target.closest('[data-app-inspect]');
    if (ins) return openAppInStage(ins.dataset.appInspect);
    const bld = e.target.closest('[data-app-build]');
    if (bld) {
      const id = bld.dataset.appBuild;
      bld.disabled = true; bld.textContent = 'Building…';
      const box = $('#apps-build-status');
      const line = $('#apps-build-line');
      const log = $('#apps-build-log');
      const spin = $('#apps-build-spin');
      if (box) { box.hidden = false; spin.hidden = false; log.textContent = ''; }
      await ctx.buildAppById(id, (stepLine, all) => {
        if (log) { log.textContent = all.join('\n'); log.scrollTop = log.scrollHeight; }
        if (line) line.textContent = stepLine.replace(/^\[[^\]]+\]\s*/, '');
      });
      if (spin) spin.hidden = true;
      return refreshAppsList();
    }
    const del = e.target.closest('[data-app-del]');
    if (del) {
      await fetch(`/api/apps/${encodeURIComponent(del.dataset.appDel)}`, {method: 'DELETE'});
      return refreshAppsList();
    }
  });
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
