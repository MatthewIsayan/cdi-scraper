import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cache = path.join(root, 'exports/license-details-cache');
const rows = JSON.parse(await fs.readFile(path.join(cache, 'source-rows.json'), 'utf8').then(s => s.replace(/^\uFEFF/, '')));
const analysis = JSON.parse(await fs.readFile(path.join(cache, 'analysis.json'), 'utf8'));
const lookup = new Map(analysis.map(r => [r.license_number, r]));
const originalColumns = Object.keys(rows[0]);
const addedColumns = ['agent_analysis', 'license_checked_on', 'lookup_status'];
const columns = [...originalColumns, ...addedColumns];
const matrix = [columns, ...rows.map(row => {
  const detail = lookup.get(row.license_number);
  if (!detail) throw new Error(`Missing analysis for ${row.license_number}`);
  return [...originalColumns.map(c => row[c] ?? ''), ...addedColumns.map(c => detail[c])];
})];
const workbook = Workbook.create();
const sheet = workbook.worksheets.add('Agents');
const range = sheet.getRangeByIndexes(0, 0, matrix.length, columns.length);
range.values = matrix;
range.setNumberFormat('@');
workbook.recalculate();
const stored = range.values;
for (let r = 0; r < matrix.length; r++) {
  for (let c = 0; c < columns.length; c++) {
    if (String(stored[r][c] ?? '') !== matrix[r][c]) throw new Error(`Value changed at row ${r}, column ${c}`);
  }
}
console.log((await workbook.inspect({kind:'table', range:'Agents!J1:L3', include:'values', tableMaxRows:3, tableMaxCols:3, maxChars:1600})).ndjson);
// CSV has no presentation formatting. Verify its exact cell values before serialization.
const quote = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
const output = path.join(root, 'exports/cdi-agents-analyzed.csv');
const csv = '\uFEFF' + stored.map(row => row.map(quote).join(',')).join('\r\n') + '\r\n';
await fs.writeFile(output + '.tmp', csv, 'utf8');
await fs.rename(output + '.tmp', output);
console.log(JSON.stringify({output, agents:rows.length, verified:analysis.filter(r => r.lookup_status === 'verified').length, unavailable:analysis.filter(r => r.lookup_status !== 'verified').length}));
