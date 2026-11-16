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


const { renderGoalIcon, summarizeGoals } = loadComponent(path.resolve(__dirname, "../src/components/GoalsView.tsx"));
const icon = (...args) => renderToStaticMarkup(React.createElement(React.Fragment, null, renderGoalIcon(...args)));

// A picked emoji must render even though every goal defaults to the "Tabungan" category.
assert.match(icon("🏝️", "Liburan Bali"), /🏝️/);
assert.match(icon("💍", "Biaya nikah"), /💍/);
assert.doesNotMatch(icon("💍", "Tabungan nikah"), /lucide-shield/);
// Known emoji map to their line icon; the default icon falls back to the name.
assert.match(icon("💻", "Apa saja"), /lucide-laptop/);
assert.match(icon("🎯", "Laptop baru"), /lucide-laptop/);
assert.match(icon("🎯", "Dana dingin"), /lucide-shield/);
assert.match(icon("🎯", "Biaya nikah"), /lucide-target/);
assert.match(icon("", "Biaya nikah"), /lucide-target/);
console.log("PASS: the goal icon the user picked wins over name and category keywords.");

const totals = summarizeGoals([
  { target_amount: 6_000_000, current_amount: 6_400_000 },
  { target_amount: 10_000_000, current_amount: 2_500_000 },
  { target_amount: 4_000_000, current_amount: 0 },
]);
assert.deepEqual(totals, {
  target: 20_000_000, collected: 8_500_000, surplus: 400_000, remaining: 11_500_000,
  averagePercentage: 41.7,
});
assert.deepEqual(summarizeGoals([]), { target: 0, collected: 0, surplus: 0, remaining: 0, averagePercentage: 0 });
console.log("PASS: collected total is capped per goal, surplus is apart, average is per goal.");
