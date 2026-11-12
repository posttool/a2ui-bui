/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Validates A2UI v1.0 message streams against the BUI catalog spec.
// Shared by the browser (realtime generation repair loop) and
// tools/validate_showcases.mjs (CI for the showcase payloads).
//
//   validateMessages(messages) -> {errors: [str], warnings: [str], usage: {Component: count}}
//
// Checks: known components, required props, enum values, literal types, no
// unknown props, child / children / tabs / template references resolve,
// "root" exists, actions are well formed; warns on bindings missing from the
// final data model, relative bindings outside templates, unreferenced ids.

import {COMPONENTS} from './spec.js';

const ALWAYS = new Set(['id', 'component', 'accessibility', 'catalogId']);
const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const isBinding = (v) => isObj(v) && (typeof v['@path'] === 'string' || typeof v.path === 'string' ||
                                     typeof v['@call'] === 'string' || isObj(v['@call']) || typeof v.call === 'string');

function setPath(model, path, value) {
  if (!path || path === '/') return value;
  const parts = path.split('/').filter(Boolean);
  let o = model;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!isObj(o[parts[i]]) && !Array.isArray(o[parts[i]])) o[parts[i]] = {};
    o = o[parts[i]];
  }
  o[parts.at(-1)] = value;
  return model;
}

function getAt(model, path) {
  let o = model;
  for (const p of path.split('/').filter(Boolean)) o = o?.[p];
  return o;
}

function hasPath(model, path) {
  let o = model;
  for (const p of path.split('/').filter(Boolean)) {
    if (o === null || o === undefined || typeof o !== 'object' || !(p in o)) return false;
    o = o[p];
  }
  return true;
}

function literalOk(kind, v) {
  switch (kind) {
    case 'str': return typeof v === 'string';
    case 'num': case 'number': return typeof v === 'number';
    case 'bool': return typeof v === 'boolean';
    case 'strList': return Array.isArray(v) && v.every((x) => typeof x === 'string');
    default: return true;
  }
}

export function validateMessages(messages, {catalogSuffix = '/catalogs/bui/v1/catalog.json'} = {}) {
  const errors = [];
  const warnings = [];
  const usage = {};
  const err = (m) => errors.push(m);
  const warn = (m) => warnings.push(m);
  const surfaces = new Map();
  for (const [i, m] of (messages || []).entries()) {
    if (m.version !== 'v1.0') err(`message ${i}: version must be "v1.0"`);
    if (m.createSurface) {
      const {surfaceId, catalogId} = m.createSurface;
      if (catalogSuffix && !String(catalogId || '').endsWith(catalogSuffix)) err(`message ${i}: unexpected catalogId ${catalogId}`);
      surfaces.set(surfaceId, {comps: new Map(), model: {}});
    } else if (m.updateComponents) {
      const s = surfaces.get(m.updateComponents.surfaceId);
      if (!s) { err(`message ${i}: updateComponents before createSurface`); continue; }
      for (const c of m.updateComponents.components || []) {
        if (s.comps.has(c.id) && s.comps.get(c.id)._msg === i) err(`duplicate id "${c.id}" in message ${i}`);
        s.comps.set(c.id, {...c, _msg: i});
      }
    } else if (m.updateDataModel) {
      const s = surfaces.get(m.updateDataModel.surfaceId);
      if (!s) { err(`message ${i}: updateDataModel before createSurface`); continue; }
      s.model = setPath(s.model, m.updateDataModel.path, structuredClone(m.updateDataModel.value));
    } else if (!m.deleteSurface) {
      err(`message ${i}: unknown message type ${Object.keys(m).join(',')}`);
    }
  }
  for (const [sid, s] of surfaces) {
    if (!s.comps.has('root')) err(`surface ${sid}: no "root" component`);
    const templated = new Set();
    const markTemplated = (id) => {
      if (templated.has(id)) return;
      templated.add(id);
      const c = s.comps.get(id);
      if (!c) return;
      for (const [prop, p] of Object.entries(COMPONENTS[c.component]?.props || {})) {
        const v = c[prop];
        if (p.kind === 'child' && typeof v === 'string') markTemplated(v);
        if (p.kind === 'children' && Array.isArray(v)) v.forEach(markTemplated);
        if (p.kind === 'tabs' && Array.isArray(v)) v.forEach((t) => markTemplated(t?.child));
      }
    };
    for (const c of s.comps.values()) {
      for (const v of Object.values(c)) if (isObj(v) && typeof v.componentId === 'string') markTemplated(v.componentId);
    }
    const reachable = new Set();
    const walkPaths = (v, id) => {
      if (Array.isArray(v)) return v.forEach((x) => walkPaths(x, id));
      if (!isObj(v)) return;
      if (typeof v['@path'] === 'string') {
        const p = v['@path'];
        if (p.startsWith('/') && !hasPath(s.model, p)) warn(`"${id}": binding ${p} not in the data model`);
        if (!p.startsWith('/') && !templated.has(id)) warn(`"${id}": relative binding "${p}" outside a template`);
        return;
      }
      Object.values(v).forEach((x) => walkPaths(x, id));
    };
    for (const c of s.comps.values()) {
      const spec = COMPONENTS[c.component];
      if (!spec) { err(`"${c.id}": unknown component "${c.component}"`); continue; }
      usage[c.component] = (usage[c.component] || 0) + 1;
      for (const k of Object.keys(c)) {
        if (k === '_msg' || ALWAYS.has(k)) continue;
        if (!(k in spec.props)) err(`"${c.id}" (${c.component}): unknown prop "${k}"`);
      }
      for (const [prop, p] of Object.entries(spec.props)) {
        const v = c[prop];
        if (v === undefined) {
          if (p.required) err(`"${c.id}" (${c.component}): missing required prop "${prop}"`);
          continue;
        }
        if (p.kind === 'enum') {
          if (!p.values.includes(v)) err(`"${c.id}" (${c.component}): ${prop}=${JSON.stringify(v)} not in [${p.values}]`);
        } else if (p.kind === 'child') {
          if (typeof v !== 'string') err(`"${c.id}": ${prop} must be a component id`);
          else if (!s.comps.has(v)) err(`"${c.id}": ${prop} references missing "${v}"`);
          else reachable.add(v);
        } else if (p.kind === 'children') {
          if (Array.isArray(v)) {
            for (const id of v) {
              if (!s.comps.has(id)) err(`"${c.id}": ${prop} references missing "${id}"`);
              reachable.add(id);
            }
          } else if (isObj(v) && typeof v.componentId === 'string') {
            if (!s.comps.has(v.componentId)) err(`"${c.id}": template references missing "${v.componentId}"`);
            if (typeof v.path !== 'string') err(`"${c.id}": template without path`);
            else if (v.path.startsWith('/') && !Array.isArray(getAt(s.model, v.path))) {
              warn(`"${c.id}": template path ${v.path} is not an array in the data model`);
            }
            reachable.add(v.componentId);
          } else err(`"${c.id}": ${prop} must be an id list or {componentId, path}`);
        } else if (p.kind === 'tabs') {
          if (!Array.isArray(v)) err(`"${c.id}": tabs must be an array`);
          else for (const t of v) {
            if (!s.comps.has(t?.child)) err(`"${c.id}": tab "${t?.title}" references missing "${t?.child}"`);
            reachable.add(t?.child);
          }
        } else if (p.kind === 'action') {
          if (!isObj(v) || !(isObj(v.event) || isObj(v.functionCall))) err(`"${c.id}": ${prop} must be {event} or {functionCall}`);
          else if (v.event && typeof v.event.name !== 'string') err(`"${c.id}": event without name`);
        } else if (!isBinding(v) && !literalOk(p.kind, v)) {
          err(`"${c.id}" (${c.component}): ${prop}=${JSON.stringify(v).slice(0, 60)} is not a ${p.kind}`);
        }
      }
      walkPaths(Object.fromEntries(Object.entries(c).filter(([k]) => !['id', 'component', '_msg'].includes(k))), c.id);
    }
    for (const id of s.comps.keys()) if (id !== 'root' && !reachable.has(id)) warn(`"${id}" is never referenced`);
  }
  return {errors, warnings, usage};
}
