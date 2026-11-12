/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: Apache-2.0
 */

// Generates bui/catalog.json (A2UI v1.0 catalog definition, JSON Schema
// 2020-12) from bui/spec.js, so agents and validators get the same contract
// the web renderer enforces.  Usage: node tools/build_catalog.mjs
import {writeFileSync} from 'node:fs';

const {COMPONENTS, BUI_CATALOG_ID} = await import('../bui/spec.js');

const CT = 'common_types.json#/$defs/';
const ref = (name, doc) => ({$ref: CT + name, ...(doc ? {description: doc} : {})});

function propSchema(p) {
  switch (p.kind) {
    case 'str': return ref('DynamicString', p.doc);
    case 'num': return ref('DynamicNumber', p.doc);
    case 'bool': return ref('DynamicBoolean', p.doc);
    case 'strList': return ref('DynamicStringList', p.doc);
    case 'value': return ref('DynamicValue', p.doc);
    case 'number': return {type: 'number', ...(p.doc ? {description: p.doc} : {})};
    case 'child': return ref('ComponentId', p.doc);
    case 'children': return ref('ChildList', p.doc);
    case 'action': return ref('Action', p.doc);
    case 'enum': return {type: 'string', enum: p.values, ...(p.doc ? {description: p.doc} : {})};
    case 'tabs': return {
      type: 'array', minItems: 1, description: p.doc || 'Tabs: {title, icon?, child}.',
      items: {type: 'object', properties: {title: ref('DynamicString'), icon: {type: 'string', description: 'Blender icon name.'},
        child: ref('ComponentId')}, required: ['child']},
    };
    default: throw new Error(`unknown kind ${p.kind}`);
  }
}

const components = {};
for (const [name, c] of Object.entries(COMPONENTS)) {
  const properties = {component: {const: name}};
  const required = ['component'];
  for (const [k, p] of Object.entries(c.props)) {
    properties[k] = propSchema(p);
    if (p.required) required.push(k);
  }
  components[name] = {
    type: 'object',
    description: c.doc,
    allOf: [{$ref: CT + 'ComponentCommon'}, {type: 'object', properties, required}],
    unevaluatedProperties: false,
  };
}

const catalog = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: BUI_CATALOG_ID,
  protocolVersion: '1.0',
  title: 'BUI Catalog (Blender interface)',
  description: 'Blender\'s interface components from BUI (github.com/ppmpreetham/BUI) as an A2UI catalog: ' +
      'properties-editor layouts, number fields and sliders, enums, color pickers, lists, outliner trees, ' +
      'menus, pie menus, color ramps, curves, histograms and node editors.',
  catalogId: BUI_CATALOG_ID,
  instructions: [
    'Build Blender-style property UIs: wrap groups in Panel components inside a Column; use Split or the label prop for',
    '"Label  [value]" rows; use Column/Row align=true for joined widget groups (e.g. Location X/Y/Z or EnumRow).',
    'Icons are Blender icon names (MESH_CUBE, LIGHT_SUN, HIDE_OFF, RENDER_STILL ...).',
    'Bind every user-editable value to the data model with {"@path": ...} so edits flow back to the agent; give',
    'commit-style widgets (Button, MenuButton, ListView ...) an action whose context reads the bound paths.',
    'Repeated rows (lists of keymap entries, jobs, waypoints, nodes) should use a ChildList template.',
    'NodeEditor children are Node components keyed by `key`; links reference node keys and socket index or name.',
  ].join(' '),
  components,
  functions: {},
  $defs: {anyComponent: {oneOf: Object.keys(components).map((n) => ({$ref: `#/components/${n}`}))}},
};

const out = new URL('../bui/catalog.json', import.meta.url);
writeFileSync(out, JSON.stringify(catalog, null, 2) + '\n');
console.log(`wrote ${out.pathname}: ${Object.keys(components).length} components`);
