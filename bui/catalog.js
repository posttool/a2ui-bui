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

// The BUI A2UI catalog: every component from spec.js implemented as an
// A2uiLitElement, assembled into one web_core Catalog.

import {Catalog} from '../third_party/a2ui_bundle/a2ui.bundle.js';
import {BUI_CATALOG_ID, COMPONENT_NAMES} from './spec.js';
import {IMPLS as LAYOUT} from './components/layout.js';
import {IMPLS as VALUES} from './components/values.js';
import {IMPLS as CHOICE} from './components/choice.js';
import {IMPLS as BUTTONS} from './components/buttons.js';
import {IMPLS as MENUS} from './components/menus.js';
import {IMPLS as VIEWS} from './components/views.js';
import {IMPLS as EDITORS} from './components/editors.js';
import {IMPLS as NODES} from './components/nodes.js';

export {BUI_CATALOG_ID};

export const BUI_IMPLS = [...LAYOUT, ...VALUES, ...CHOICE, ...BUTTONS, ...MENUS, ...VIEWS, ...EDITORS, ...NODES];

const have = new Set(BUI_IMPLS.map((i) => i.name));
export const MISSING = COMPONENT_NAMES.filter((n) => !have.has(n));
if (MISSING.length) console.warn('[bui] components not implemented yet:', MISSING.join(', '));

export const buiCatalog = new Catalog(BUI_CATALOG_ID, '1.0', BUI_IMPLS);

/** Stylesheets the catalog needs (relative to this module). */
export const BUI_STYLESHEETS = ['bui.css', ...['layout', 'values', 'choice', 'buttons', 'menus', 'views', 'editors', 'nodes']
                                                  .map((g) => `css/${g}.css`)]
                                   .map((p) => new URL(p, import.meta.url).href);
