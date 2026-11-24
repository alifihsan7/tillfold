const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/lib/dashboardData.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const source = new Module(filename, module);
source._compile(compiled, filename);
const { loadDashboardData, DashboardLoadError } = source.exports;
const json = (value) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const base = (url) => url.includes('/transactions?') ? json([{ id: 1 }])
  : url.includes('/analytics/summary?') ? json({ total_balance: 100, start_date: '2026-11-01' }) : json([]);

(async () => {
  const urls = [];
  const result = await loadDashboardData(async (url) => { urls.push(url); return base(url); }, {
    type: 'custom', start: '2026-11-01', end: '2026-11-30',
  });
  assert.equal(result.summary.total_balance, 100);
  assert.equal(new URL(urls.find((url) => url.includes('/transactions?')), 'http://local').searchParams.get('end_date'), '2026-11-30');
  assert.equal(new URL(urls.find((url) => url.includes('/summary?')), 'http://local').searchParams.get('start'), '2026-11-01');

  const partial = await loadDashboardData(async (url) => {
    if (url.endsWith('/subscriptions')) throw new Error('Offline');
    if (url.endsWith('/goals')) return new Response('<html>proxy</html>');
    if (url.endsWith('/categories')) return new Response('', { status: 503 });
    return base(url);
  }, { type: 'cycle' });
  assert.equal(partial.summary.total_balance, 100);
  assert.equal(partial.subscriptions, null);
  assert.equal(partial.goals, null);
  assert.equal(partial.categories, null);

  await assert.rejects(loadDashboardData(async (url) => url.includes('/transactions?')
    ? new Response('', { status: 500 }) : base(url), { type: 'cycle' }),
    (error) => error instanceof DashboardLoadError && error.status === 500 && error.message.includes('transaksi'));
  await assert.rejects(loadDashboardData(async (url) => url.includes('/summary?')
    ? new Response('', { status: 401 }) : base(url), { type: 'cycle' }),
    (error) => error.status === 401 && error.message.includes('Masuk kembali'));
  await assert.rejects(loadDashboardData(async (url) => url.endsWith('/goals')
    ? new Response('', { status: 401 }) : base(url), { type: 'cycle' }),
    (error) => error instanceof DashboardLoadError && error.status === 401);
  console.log('Dashboard data: period filters, optional failures, primary failure and expired session passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
