const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

function loadComponent(filename) {
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  const componentModule = new Module(filename, module);
  componentModule.filename = filename;
  componentModule.paths = Module._nodeModulePaths(path.dirname(filename));
  const nativeRequire = componentModule.require.bind(componentModule);
  componentModule.require = (name) => {
    if (!name.startsWith(".") && !name.startsWith("@/")) return nativeRequire(name);
    const source = name.startsWith("@/")
      ? path.resolve(__dirname, "../src", name.slice(2))
      : path.resolve(path.dirname(filename), name);
    const resolved = [source + ".tsx", source + ".ts", source].find((candidate) => fs.existsSync(candidate));
    return loadComponent(resolved);
  };
  componentModule._compile(compiled, filename);
  return componentModule.exports;
}


const { cashFlowDays, cashFlowCeiling } = loadComponent(path.resolve(__dirname, "../src/lib/dailyCashFlow.ts"));
const days = cashFlowDays([
  { date: "2026-11-24", income: 3000000, expense: 40000 },
  { date: "2026-11-26", income: 0, expense: 250000 },
], "2026-11-24", "2026-11-27");
assert.equal(days.length, 4);
assert.deepEqual(days[1], { date: "2026-11-25", income: 0, expense: 0 });
assert.equal(days.reduce((sum, day) => sum + day.income, 0), 3000000);
assert.equal(days.reduce((sum, day) => sum + day.expense, 0), 290000);
assert.equal(cashFlowCeiling(days), 4000000);
assert.equal(cashFlowCeiling(days.map(day => ({ ...day, income: 0 }))), 400000);
assert.equal(cashFlowCeiling([]), 1);
assert.equal(cashFlowDays([], "2024-02-28", "2024-03-01")[1].date, "2024-02-29");
assert.equal(cashFlowDays([], "2026-12-31", "2027-01-01")[1].date, "2027-01-01");
assert.equal(cashFlowDays([], "", "").length, 0);
console.log("PASS: daily chart preserves quiet dates, money totals, leap days and year boundaries; focused scales retain small expenses.");
const { DailyCashFlowChart } = loadComponent(path.resolve(__dirname, "../src/components/DailyCashFlowChart.tsx"));
const props = { start: "2026-11-24", end: "2026-11-27", formatRupiah: amount => "Rp " + new Intl.NumberFormat("id-ID").format(amount) };
const empty = renderToStaticMarkup(React.createElement(DailyCashFlowChart, { ...props, days: [] }));
assert.match(empty, /Belum ada arus kas/);
assert.doesNotMatch(empty, /fold-report-day-detail|fold-report-y-axis/);
const populated = renderToStaticMarkup(React.createElement(DailyCashFlowChart, { ...props, days }));
assert.match(populated, /Rincian hari terpilih/);
assert.match(populated, /−Rp 250.000/);
assert.match(populated, /aria-pressed="true" tabindex="0" aria-label="26 Nov/);
assert.match(populated, /Transfer dan saldo awal di luar arus kas/);
console.log("PASS: empty periods show no invented chart; populated periods expose a keyboard selection and signed daily detail.");

const { cashFlowBuckets } = loadComponent(path.resolve(__dirname, "../src/lib/dailyCashFlow.ts"));
const yearDays = cashFlowDays([{ date: "2026-01-01", income: 100, expense: 3 }, { date: "2026-12-31", income: 25, expense: 7 }], "2026-01-01", "2026-12-31");
for (const grouping of ["weekly", "monthly"]) {
  const buckets = cashFlowBuckets(yearDays, grouping);
  assert.equal(buckets.reduce((sum, item) => sum + item.income, 0), 125);
  assert.equal(buckets.reduce((sum, item) => sum + item.expense, 0), 10);
  assert.equal(buckets[0].date, "2026-01-01");
  assert.equal(buckets.at(-1).endDate, "2026-12-31");
}
assert.equal(cashFlowBuckets(yearDays, "monthly").length, 12);
const monday = cashFlowBuckets(cashFlowDays([], "2026-12-27", "2027-01-04"), "weekly");
assert.deepEqual(monday.map(item => [item.date, item.endDate]), [["2026-12-27", "2026-12-27"], ["2026-12-28", "2027-01-03"], ["2027-01-04", "2027-01-04"]]);
console.log("PASS: weekly/monthly grouping preserves totals and clips partial weeks/months to the selected period.");
