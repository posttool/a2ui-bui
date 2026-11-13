/**
 * Copyright 2026 posttool
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// Validates showcases against bui/spec.js using bui/validate.js (node, no deps).
//
//   node tools/validate_showcases.mjs [--index showcases/index.json]
//
// Also checks showcase metadata (name, messages, width 560..1200) and prints
// per-component coverage; exits 1 on any error or a component with 0 uses.

import {readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const {COMPONENT_NAMES} = await import('../bui/spec.js');
const {validateMessages} = await import('../bui/validate.js');

const argIdx = process.argv.indexOf('--index');
const indexPath = argIdx > 0 ? process.argv[argIdx + 1] : 'showcases/index.json';
const index = JSON.parse(readFileSync(join(ROOT, indexPath), 'utf8'));

let errors = 0;
let warnings = 0;
const coverage = Object.fromEntries(COMPONENT_NAMES.map((n) => [n, 0]));
const where = Object.fromEntries(COMPONENT_NAMES.map((n) => [n, new Set()]));

for (const {file} of index.showcases) {
  const sc = JSON.parse(readFileSync(join(ROOT, 'showcases', file), 'utf8'));
  const errs = [];
  for (const k of ['name', 'messages']) if (!(k in sc)) errs.push(`missing top-level "${k}"`);
  if (sc.width !== undefined && (typeof sc.width !== 'number' || sc.width < 560 || sc.width > 1200)) {
    errs.push(`width ${sc.width} outside 560..1200`);
  }
  const r = validateMessages(sc.messages || []);
  errs.push(...r.errors);
  for (const e of errs) console.log(`  ERROR ${file}: ${e}`);
  for (const w of r.warnings) console.log(`  warn  ${file}: ${w}`);
  errors += errs.length;
  warnings += r.warnings.length;
  for (const [n, c] of Object.entries(r.usage)) {
    if (n in coverage) {
      coverage[n] += c;
      where[n].add(file.replace(/\.json$/, ''));
    }
  }
}

console.log(`\n${index.showcases.length} showcases · coverage (component definitions per catalog component):`);
const rows = COMPONENT_NAMES.map((n) => [n, coverage[n], where[n].size]).sort((a, b) => b[1] - a[1]);
for (const [n, c, s] of rows) console.log(`  ${n.padEnd(13)} ${String(c).padStart(4)}  in ${s} showcase${s === 1 ? '' : 's'}`);
const zero = rows.filter((r) => r[1] === 0).map((r) => r[0]);
if (zero.length) { errors++; console.log(`\nERROR: components with 0 uses: ${zero.join(', ')}`); }
console.log(`\n${errors} error(s), ${warnings} warning(s)`);
process.exit(errors ? 1 : 0);
