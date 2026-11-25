const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/lib/api.ts');
const source = new Module(filename, module);
source._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, filename);
const { authFetch, setAuthToken, getAuthToken, setStoredUser, getStoredUser, SESSION_EXPIRED_EVENT, apiErrorMessage, hasRecentFederatedSignIn } = source.exports;
const values = new Map();
global.localStorage = { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
global.window = new EventTarget();
let expired = 0;
window.addEventListener(SESSION_EXPIRED_EVENT, () => expired++);
(async () => {
  setAuthToken('old-session'); setStoredUser({ id: 1, username: 'first' });
  global.fetch = async () => new Response('{"detail":"expired"}', { status:401, headers:{'Content-Type':'application/json'} });
  await authFetch('/api/v1/accounts');
  assert.equal(getAuthToken(), null); assert.equal(getStoredUser(), null); assert.equal(expired, 1);
  await authFetch('/api/v1/goals'); assert.equal(expired, 1);

  let finish;
  global.fetch = () => new Promise(resolve => { finish = resolve; });
  setAuthToken('previous-session');
  const previous = authFetch('/api/v1/accounts');
  setAuthToken('new-session'); setStoredUser({ id: 2, username: 'second' });
  finish(new Response('{}', { status:401 })); await assert.rejects(previous, /Akun telah berubah/);
  assert.equal(getAuthToken(), 'new-session'); assert.equal(getStoredUser().id, 2); assert.equal(expired, 1);

  setAuthToken('account-before-logout');
  const oldSuccess = authFetch('/api/v1/accounts');
  setAuthToken(null); setStoredUser(null);
  finish(new Response('[{"name":"Private old account"}]', {status:200}));
  await assert.rejects(oldSuccess, /Akun telah berubah/);
  let releaseBody;
  setAuthToken('streaming-session');
  global.fetch = async () => new Response(new ReadableStream({ start(controller) { releaseBody = controller; } }));
  const streaming = await authFetch('/api/v1/accounts');
  const pendingBody = streaming.json();
  setAuthToken('new-owner');
  releaseBody.enqueue(new TextEncoder().encode('[{"name":"Private old account"}]')); releaseBody.close();
  await assert.rejects(pendingBody, /Akun telah berubah/);

  const now = 1700000000000;
  const proof = (method, age) => 'header.' + Buffer.from(JSON.stringify({ amr: method, iat: now / 1000, auth_time: now / 1000 - age })).toString('base64url') + '.signature';
  assert.equal(hasRecentFederatedSignIn(proof('google', 299), now), true);
  assert.equal(hasRecentFederatedSignIn(proof('telegram', 300), now), true);
  assert.equal(hasRecentFederatedSignIn(proof('google', 301), now), false);
  assert.equal(hasRecentFederatedSignIn(proof('google', -1), now), false);
  assert.equal(hasRecentFederatedSignIn(proof('password', 0), now), false);
  assert.equal(hasRecentFederatedSignIn('invalid', now), false);

  assert.equal(apiErrorMessage({ detail:[{ type:'string_too_short', loc:['body','password'], msg:'Too short' }] }, 'Fallback'), 'Password minimal 8 karakter.');
  assert.equal(apiErrorMessage({ detail:{ code:'google_link_required', message:'Prove ownership' } }, 'Fallback'), 'Prove ownership');
  assert.equal(apiErrorMessage({ detail:[{ msg:'Value error, Total alokasi harus 100%.' }] }, 'Fallback'), 'Total alokasi harus 100%.');
  assert.equal(apiErrorMessage({ detail:{} }, 'Fallback'), 'Fallback');
  console.log('PASS: session expiry clears credentials once; delayed old 401 cannot clear a new login; structured validation and Google-link errors remain readable.');
})().catch(error => { console.error(error); process.exitCode=1; });
