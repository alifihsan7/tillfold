const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/lib/transactionCalendar.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const source = new Module(filename, module);
source._compile(compiled, filename);
const { monthCells, shiftCalendarMonth, compactRupiah, expenseHeatLevel, todayWib } = source.exports;
const november = monthCells(2026, 11);
assert.equal(november.length, 42);
assert.deepEqual(november.slice(0, 6), Array(6).fill(null));
assert.equal(november[6], '2026-11-01');
assert.equal(november.filter(Boolean).length, 30);
assert.equal(monthCells(2024, 2).filter(Boolean).length, 29);
assert.equal(monthCells(2025, 2).filter(Boolean).length, 28);
assert.equal(monthCells(2000, 2).filter(Boolean).length, 29);
assert.equal(monthCells(2100, 2).filter(Boolean).length, 28);
assert.equal(monthCells(1, 1)[0], '0001-01-01');
assert.equal(monthCells(9999, 12).filter(Boolean).at(-1), '9999-12-31');
assert.deepEqual(shiftCalendarMonth(2026, 12, 1), { year: 2027, month: 1 });
assert.deepEqual(shiftCalendarMonth(2026, 1, -1), { year: 2025, month: 12 });
assert.equal(shiftCalendarMonth(1, 1, -1), null);
assert.equal(shiftCalendarMonth(9999, 12, 1), null);
assert.equal(compactRupiah(75000), '75rb');
assert.equal(compactRupiah(1500000), '1,5jt');
assert.equal(compactRupiah(0), '0');
assert.equal(expenseHeatLevel(0, 100), 0);
assert.equal(expenseHeatLevel(-10, 100), 0);
assert.equal(expenseHeatLevel(10, 0), 0);
assert.equal(expenseHeatLevel(NaN, 100), 0);
assert.equal(expenseHeatLevel(10, Infinity), 0);
assert.deepEqual([1, 25, 26, 50, 51, 75, 76, 100, 200].map(value => expenseHeatLevel(value, 100)), [1, 1, 2, 2, 3, 3, 4, 4, 4]);
for (const [instant, expected] of [
  ['2026-11-07T16:59:59Z', '2026-11-07'],
  ['2026-11-07T17:00:00Z', '2026-11-08'],
  ['2026-11-08T00:00:00Z', '2026-11-08'],
  ['2026-11-30T17:00:00Z', '2026-12-01'],
  ['2026-12-31T17:00:00Z', '2027-01-01'],
  ['2024-02-28T17:00:00Z', '2024-02-29'],
]) assert.equal(todayWib(new Date(instant)), expected);
console.log('PASS: calendar grids, heatmap and WIB midnight/month/year/leap-day boundaries.');
