const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/lib/newTransactionHighlight.ts');
const source = new Module(filename, module);
source._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, filename);
const { trackNewTransactions: track } = source.exports;
const rows = (...ids) => ids.map(id => ({ id }));
const initial = track(null, rows(10, 9), 'all');
assert.deepEqual(initial.newIds, []);
assert.deepEqual(track(initial.snapshot, rows(10, 9), 'all').newIds, []);
const added = track(initial.snapshot, rows(12, 11, 10), 'all');
assert.deepEqual(added.newIds, [12, 11]);
assert.deepEqual(track(added.snapshot, rows(12, 10), 'all').newIds, []);
assert.deepEqual(track(added.snapshot, rows(12, 11, 10), 'all').newIds, []);
assert.deepEqual(track(added.snapshot, rows(99, 98), 'account:bank').newIds, []);
assert.deepEqual(track(added.snapshot, rows(99, 98), 'page:2').newIds, []);
assert.deepEqual(track(added.snapshot, rows(2, 1), 'all').newIds, []);
assert.deepEqual(track(added.snapshot, [{ id: 12, amount: 500000 }], 'all').newIds, []);
const empty = track(null, [], 'all');
assert.deepEqual(track(empty.snapshot, rows(1), 'all').newIds, [1]);
assert.deepEqual(track(initial.snapshot, rows(11, 11, 10), 'all').newIds, [11]);
console.log('PASS: initial load, edits, deletes, refresh, paging and filters stay quiet; only higher new IDs highlight.');
