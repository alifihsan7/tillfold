const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const filename = path.resolve(__dirname, "../src/lib/api.ts");
const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const source = new Module(filename, module);
source._compile(compiled, filename);
const { authFetch } = source.exports;
const originalFetch = global.fetch;

(async () => {
  try {
    for (const status of [200, 404, 502]) {
      global.fetch = async () => new Response("<!DOCTYPE html><html>Fallback</html>", {
        status, headers: { "Content-Type": "text/html; charset=utf-8" },
      });
      await assert.rejects(authFetch("/api/v1/accounts/1/reconciliation"),
        error => error.message.includes("Layanan data belum tersedia"));
    }
    global.fetch = async () => new Response('{"balance":100}', {
      headers: { "Content-Type": "application/json" },
    });
    assert.deepEqual(await (await authFetch("/api/v1/accounts/1/reconciliation")).json(), { balance: 100 });
    global.fetch = async () => new Response('{"detail":"Saldo berubah"}', {
      status: 409, headers: { "Content-Type": "application/json" },
    });
    const conflict = await authFetch("/api/v1/accounts/1/reconciliation");
    assert.equal(conflict.status, 409);
    assert.equal((await conflict.json()).detail, "Saldo berubah");
    console.log("PASS: HTML fallbacks produce a readable error; JSON responses retain their bodies.");
  } finally {
    global.fetch = originalFetch;
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
