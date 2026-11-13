/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Realtime generation ("Create" tab): prompt -> any model via LiteLLM (server.py) -> A2UI
// v1.0 JSON Lines streamed over SSE -> rendered message by message with the
// BUI catalog. After the stream ends, the messages are validated against the
// spec (bui/validate.js) plus renderer errors; on problems one automatic
// repair round asks the model for a corrected UI. Follow-up prompts (Refine)
// and, optionally, surface actions are sent back with the current UI + data.

import {validateMessages} from './bui/validate.js';

let ctx;
const S = {
  starters: [],
  history: [],       // [{id, prompt, title, width, messages, model, ms, cached}]
  current: null,     // history entry on stage
  busy: false,
  abort: null,
  hasKey: false,
};

const $ = (s) => document.querySelector(s);
/** Window width for a requested width, capped to the stage so it never clips. */
const fitWidth = (w) => {
  const avail = ($('.stage')?.clientWidth || 1200) - 60;
  return `${Math.max(480, Math.min(1200, w || 900, avail))}px`;
};

export async function initCreate(c) {
  ctx = c;
  try {
    const cfg = await (await fetch('api/config')).json();
    S.hasKey = cfg.hasKey;
    // Models grouped by provider; those without an API key are listed but disabled.
    const groups = new Map();
    for (const m of cfg.models) {
      if (!groups.has(m.provider)) groups.set(m.provider, []);
      groups.get(m.provider).push(m);
    }
    $('#model').innerHTML = [...groups].map(([p, list]) => {
      const prov = cfg.providers?.[p];
      const label = `${prov?.label || p}${prov && !prov.hasKey ? ' (no key)' : ''}`;
      return `<optgroup label="${ctx.esc(label)}">${list.map((m) =>
        `<option value="${ctx.esc(m.id)}" ${m.id === cfg.default ? 'selected' : ''} ${m.hasKey ? '' : 'disabled'}>${
          ctx.esc(m.label)}</option>`).join('')}</optgroup>`;
    }).join('');
    S.providers = cfg.providers || {};
  } catch {
    $('#model').innerHTML = '<option>offline</option>';
  }
  if (!S.hasKey) {
    const hints = Object.values(S.providers || {}).map((p) => `$${p.env[0]}`).join(', ') ||
        '$GEMINI_API_KEY, $ANTHROPIC_API_KEY or $OPENAI_API_KEY';
    $('#key-warning').hidden = false;
    $('#key-warning').textContent = `Live generation needs server.py with a model API key (${hints}, or ` +
        '~/.config/a2ui_bui/<provider>_api_key). Until then, examples open a cached result.';
  }
  S.starters = (await (await fetch('starters/index.json', {cache: 'no-store'})).json()).starters;
  drawStarters();
  $('#prompt-form').addEventListener('submit', (e) => {
    e.preventDefault();
    run($('#prompt').value);
  });
  $('#build-app').addEventListener('click', buildCurrentApp);
  c.setStatus = (t, k = '') => { if (t) status(t, k); else $('#gen-status').hidden = true; };
  c.buildAppById = buildAppById;
  $('#prompt').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      run($('#prompt').value);
    }
  });
  $('#starters').addEventListener('click', (e) => {
    const b = e.target.closest('.starter');
    if (b) openStarter(S.starters.find((s) => s.id === b.dataset.id));
  });
  $('#history').addEventListener('click', (e) => {
    const b = e.target.closest('.hist');
    if (b) show(S.history.find((h) => h.id === b.dataset.id));
  });
  $('#gen-status').addEventListener('click', (e) => {
    if (e.target.closest('[data-regen]')) run(S.current?.prompt || '', {fresh: true});
    if (e.target.closest('[data-stop]')) S.abort?.abort();
  });
  ctx.showCreate = showCreate;
  ctx.leaveCreate = () => {
    $('#gen-status').hidden = true;
    $('#empty-create').hidden = true;
  };
}

function drawStarters() {
  $('#starters').innerHTML = S.starters.map((s) => `
    <button class="starter ${s.cached && !S.hasKey ? 'cached' : ''}" data-id="${ctx.esc(s.id)}" title="${ctx.esc(s.prompt)}">
      <span class="ms">${ctx.esc(s.icon || 'auto_awesome')}</span><b>${ctx.esc(s.title)}</b><small>${ctx.esc(s.prompt)}</small>
    </button>`).join('');
}

function drawHistory() {
  $('#history-title').hidden = !S.history.length;
  $('#history').innerHTML = S.history.slice().reverse().map((h) => `
    <button class="hist ${S.current === h ? 'sel' : ''}" data-id="${h.id}">
      <b>${ctx.esc(h.title || h.prompt.slice(0, 40))}</b>
      <small>${h.cached ? 'cached example' : `${ctx.esc(h.model || '')} · ${(h.ms / 1000).toFixed(1)} s`} · ${h.messages.length} messages${h.repaired ? ' · repaired' : ''}</small>
    </button>`).join('');
}

function status(text, kind = '', buttons = '') {
  const el = $('#gen-status');
  el.hidden = false;
  el.className = `gen-status ${kind}`;
  $('#gen-text').innerHTML = `${ctx.esc(text)} ${buttons}`;
}

function showCreate() {
  ctx.clearActions();
  if (S.current) {
    show(S.current);
  } else {
    ctx.state.mounted?.destroy();
    ctx.state.mounted = null;
    $('#surface').textContent = '';
    $('.window').style.width = '';
    $('#win-title').textContent = 'New surface';
    ctx.setHeader('Create', 'Describe a tool and the model builds it with the BUI catalog, streamed live as A2UI messages.', {});
    $('#empty-create').hidden = false;
    $('#gen-status').hidden = true;
    $('#payload').innerHTML = '';
  }
  $('#prompt').focus();
}

function usageOf(messages) {
  return validateMessages(messages).usage;
}

function show(h) {
  if (!h) return;
  S.current = h;
  $('#empty-create').hidden = true;
  $('.window').style.width = fitWidth(h.width);
  $('#win-title').textContent = h.title || 'Surface';
  ctx.setHeader(h.title || 'Generated UI', h.prompt, usageOf(h.messages));
  ctx.mount(h.messages);
  $('#payload').innerHTML = ctx.highlight(h.messages.map((m) => JSON.stringify(m)).join('\n'));
  if (h.cached) {
    status(`Cached example generated by ${h.model || 'the model'} from this prompt.`, 'ok',
        S.hasKey ? '<button class="btn" data-regen><span class="ms">bolt</span>Regenerate live</button>' : '');
  } else {
    status(`${h.model} · ${(h.ms / 1000).toFixed(1)} s · ${h.messages.length} messages${h.repaired ? ' · auto-repaired' : ''}`, 'ok',
        '<button class="btn" data-regen><span class="ms">refresh</span>Regenerate</button>');
  }
  drawHistory();
  $('#build-app').hidden = false;
  if (h.appId) {
    $('#open-app').hidden = false;
    $('#open-app').href = `/app/${encodeURIComponent(h.appId)}`;
  } else {
    $('#open-app').hidden = true;
  }
}

async function openStarter(st) {
  if (!st || S.busy) return;
  $('#prompt').value = st.prompt;
  $('#refine').checked = false;
  // Starters always generate live; the cached result is only a fallback when the server has no API key.
  if (st.cached && !S.hasKey) {
    try {
      const c = await (await fetch(`starters/${st.id}.json`, {cache: 'no-store'})).json();
      const h = {id: `h${Date.now()}`, prompt: st.prompt, title: c.meta?.title || st.title, width: c.meta?.width,
        messages: c.messages, model: c.model, ms: c.ms || 0, cached: true};
      S.history.push(h);
      show(h);
      return;
    } catch {
      // fall through to live generation
    }
  }
  run(st.prompt, {fresh: true});
}

async function buildAppById(appId) {
  status('Starting ADK backend builder…', '');
  const res = await fetch(`/api/apps/${encodeURIComponent(appId)}/build`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({model: $('#model')?.value || ''}),
  });
  if (!res.ok || !res.body) {
    status(`Build failed: HTTP ${res.status}`, 'bad');
    return null;
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let doneEv = null;
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream: true});
    const parts = buf.split('\n\n');
    buf = parts.pop();
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      const ev = JSON.parse(line.slice(5));
      if (ev.type === 'status') status(ev.text, '');
      else if (ev.type === 'error') status(ev.error, 'bad');
      else if (ev.type === 'done') doneEv = ev;
    }
  }
  if (doneEv?.ok) {
    status(`App built (v${doneEv.version || 1}): ${doneEv.summary || 'ready'}`, 'ok');
  } else if (doneEv && !doneEv.ok) {
    status(`Build failed tests: ${doneEv.summary || ''}`, 'bad');
  }
  return doneEv;
}

async function buildCurrentApp() {
  if (!S.current || S.busy) return;
  const btn = $('#build-app');
  btn.disabled = true;
  try {
    let appId = S.current.appId;
    if (!appId) {
      status('Saving app…', '');
      const created = await (await fetch('/api/apps', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          title: S.current.title || 'App',
          width: S.current.width || 900,
          prompt: S.current.prompt || '',
          model: S.current.model || '',
          messages: S.current.messages,
        }),
      })).json();
      if (!created.ok) throw new Error(created.error || 'failed to save app');
      appId = S.current.appId = created.app.id;
    }
    const res = await buildAppById(appId);
    if (res?.ok) {
      $('#open-app').hidden = false;
      $('#open-app').href = `/app/${encodeURIComponent(appId)}`;
      ctx.mount([], {appId});
    }
  } catch (e) {
    status(String(e.message || e), 'bad');
  } finally {
    btn.disabled = false;
  }
}

/** Streams one generation; returns {messages, meta, model, ms} or null. */
async function generate(body, onMessage) {
  S.abort = new AbortController();
  const res = await fetch('api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
    signal: S.abort.signal,
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  const out = {messages: [], meta: null, model: '', ms: 0, error: ''};
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream: true});
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      let ev;
      try {
        ev = JSON.parse(line.slice(5));
      } catch {
        continue;
      }
      if (ev.type === 'status') {
        S.serverStatus = ev.text;
        status(ev.text, '', '<button class="btn" data-stop>Stop</button>');
      }
      else if (ev.type === 'meta') {
        out.meta = ev.meta;
        onMessage(null, ev.meta);
      } else if (ev.type === 'message') {
        out.messages.push(ev.message);
        onMessage(ev.message);
      } else if (ev.type === 'done') {
        out.model = ev.model;
        out.ms = ev.ms;
        out.usage = ev.usage;
      } else if (ev.type === 'error') out.error = ev.error;
    }
  }
  return out;
}

async function run(prompt, {refine = $('#refine').checked, fresh = false, viaAction = false} = {}) {
  prompt = String(prompt || '').trim();
  if (!prompt || S.busy) return;
  if (!S.hasKey) {
    status('No model API key on the server; open an example instead.', 'bad');
    return;
  }
  const base = refine && !fresh && S.current ? S.current : null;
  const body = {prompt, model: $('#model').value};
  if (base) {
    body.previous = base.messages;
    body.data = ctx.state.mounted?.getData?.() ?? null;
  }
  S.busy = true;
  S.serverStatus = '';
  $('#go').disabled = true;
  $('#empty-create').hidden = true;
  if (viaAction) ctx.logNote('agent ← action', 'Sending the action to the model for an updated UI…');
  const t0 = performance.now();
  let comps = 0;
  const live = [];
  const ticker = setInterval(() => {
    if (live.length) return;
    status(`${S.serverStatus || 'The model is designing the UI…'} ${((performance.now() - t0) / 1000).toFixed(0)} s (first lines usually arrive in 15–35 s)`, '',
        '<button class="btn" data-stop>Stop</button>');
  }, 1000);
  const onMessage = (m, meta) => {
    if (meta) {
      $('#win-title').textContent = meta.title || 'Surface';
      if (meta.width) $('.window').style.width = fitWidth(meta.width);
      ctx.setHeader(meta.title || 'Generating…', prompt, {});
      return;
    }
    if (m.createSurface || !ctx.state.mounted || live.length === 0) {
      if (m.createSurface) ctx.mount([]);
    }
    live.push(m);
    comps += m.updateComponents?.components?.length || 0;
    ctx.state.mounted?.update([m]);
    ctx.drawData();
    status(`Streaming · ${live.length} messages · ${comps} components · ${((performance.now() - t0) / 1000).toFixed(1)} s`, '',
        '<button class="btn" data-stop>Stop</button>');
  };
  try {
    if (!base) {
      ctx.clearActions();
      ctx.mount([]);
    }
    let out = await generate(body, onMessage);
    if (out.error && !out.messages.length) throw new Error(out.error);
    let repaired = false;
    let problems = check(out.messages);
    if (problems.length) {
      status(`Repairing ${problems.length} issue${problems.length === 1 ? '' : 's'}…`, '', '<button class="btn" data-stop>Stop</button>');
      ctx.logNote('validator → agent', problems.slice(0, 12).join('\n'));
      live.length = 0;
      comps = 0;
      const fix = await generate({prompt, model: body.model, previous: out.messages, errors: problems}, onMessage);
      if (fix.messages.length && check(fix.messages).length < problems.length) {
        fix.ms += out.ms;
        out = fix;
        repaired = true;
      } else {
        ctx.mount(out.messages);
      }
    }
    const h = {id: `h${Date.now()}`, prompt: base ? `${base.prompt} → ${prompt}` : prompt, title: out.meta?.title,
      width: out.meta?.width, messages: out.messages, model: out.model, ms: out.ms || (performance.now() - t0), repaired};
    S.history.push(h);
    S.current = h;
    $('#refine').checked = true;
    $('#payload').innerHTML = ctx.highlight(h.messages.map((m) => JSON.stringify(m)).join('\n'));
    ctx.setHeader(h.title || 'Generated UI', h.prompt, usageOf(h.messages));
    const left = check(h.messages);
    status(`${h.model} · ${(h.ms / 1000).toFixed(1)} s · ${h.messages.length} messages${repaired ? ' · auto-repaired' : ''}${
        left.length ? ` · ${left.length} issue(s) left` : ''}`, left.length ? 'bad' : 'ok',
        '<button class="btn" data-regen><span class="ms">refresh</span>Regenerate</button>');
    drawHistory();
    if (viaAction) ctx.logNote('agent → UI', `Updated UI (${h.messages.length} messages)`);
  } catch (e) {
    status(e.name === 'AbortError' ? 'Stopped.' : `Generation failed: ${e.message || e}`, 'bad');
  } finally {
    clearInterval(ticker);
    S.busy = false;
    S.abort = null;
    $('#go').disabled = false;
  }
}

/** Spec errors + renderer errors for a message list (render errors come from the current mount). */
function check(messages) {
  const v = validateMessages(messages);
  const render = (ctx.state.renderErrors || []).slice();
  return [...v.errors, ...render].slice(0, 40);
}
