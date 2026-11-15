import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
const require = createRequire(import.meta.url);
const context = { module: { exports: {} }, require: name => name === '@prisma/client' ? {} : name === 'googleapis' ? {} : require(name), console, Buffer, process, URL };
vm.runInNewContext(fs.readFileSync(new URL('../ops/item79-video-gate.cjs', import.meta.url), 'utf8'), context);
const { uploadPath, goodVideo, refs } = context.module.exports;
test('only canonical owned video uploads are accepted', () => {
  assert.equal(uploadPath('https://postiz.item79.com/uploads/2026/11/13/abcd.mp4'), '/uploads/2026/11/13/abcd.mp4');
  assert.equal(uploadPath('https://other.com/uploads/2026/11/13/abcd.mp4'), null);
  assert.equal(uploadPath('/uploads/2026/11/13/a.jpg'), null);
  assert.throws(() => uploadPath('/uploads/2026/11/13/%2e%2e%2fsecret.mp4'));
});
test('public processed correct-channel past retention is required', () => {
  const now = Date.now();
  const v = { snippet: { channelId: 'owned', publishedAt: new Date(now - 8 * 86400000).toISOString() }, status: { privacyStatus: 'public', uploadStatus: 'processed' }, processingDetails: { processingStatus: 'succeeded' }, contentDetails: {} };
  assert.equal(goodVideo(v, 'owned', now), true);
  for (const changed of [ { ...v, status: { ...v.status, privacyStatus: 'private' } }, { ...v, status: { ...v.status, publishAt: 'future' } }, { ...v, processingDetails: {} }, { ...v, snippet: { ...v.snippet, publishedAt: new Date(now).toISOString() } }, { ...v, contentDetails: { regionRestriction: { blocked: ['KR'] } } } ]) assert.equal(!!goodVideo(changed, 'owned', now), false);
  assert.equal(!!goodVideo(v, 'other', now), false);
});
test('nested settings and media IDs participate in reference protection', () => {
  const result = refs({ settings: [{ id: 'media', nested: { source: '/uploads/2026/11/13/abcd.mp4' } }] });
  assert.equal(result.paths.has('/uploads/2026/11/13/abcd.mp4'), true);
  assert.equal(result.ids.has('media'), true);
});

function fixture(t, options = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'item79-cleanup-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const p = '/uploads/2026/11/13/abcd.mp4';
  const actual = value => typeof value === 'string' && value.startsWith('/uploads') ? root + value.slice(8) : value;
  const file = actual(p); fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, 'approved video');
  let inTransaction = false, transactions = 0;
  const state = { file, p, apiCallsInTransaction: 0 };
  const proxyFs = { ...fs };
  for (const method of ['existsSync', 'mkdirSync', 'readdirSync', 'lstatSync', 'openSync', 'readFileSync', 'unlinkSync']) proxyFs[method] = (v, ...args) => fs[method](actual(v), ...args);
  proxyFs.realpathSync = v => fs.realpathSync(actual(v)).replaceAll('\\', '/').replace(root.replaceAll('\\', '/'), '/uploads');
  proxyFs.renameSync = (a, b) => {
    if (options.replaceBeforeRename && a === p) fs.writeFileSync(file, 'replacement video');
    return fs.renameSync(actual(a), actual(b));
  };
  proxyFs.writeFileSync = (fd, data, ...args) => {
    if (options.crashAfterUnlink && typeof data === 'string' && data.includes('"state":"REMOVED"')) throw Error('Simulated process loss');
    return fs.writeFileSync(actual(fd), data, ...args);
  };
  const ids = ['cmweat59e0001o47f4n3hb7x3', 'cmwef8i230001pd7wcv85jj3i', 'cmwece9dg0004o47fzk35186s'];
  const org = 'd12fad39-e950-4f96-8d7a-58cd1e580d22', videoId = 'abcdefghijk';
  const rows = [{ id: 'p1', organizationId: org, integrationId: ids[0], state: 'PUBLISHED', image: JSON.stringify([{ id: 'm1', path: p }]), settings: '{}', releaseId: videoId }];
  if (options.queuedContentReference) rows.push({ id: 'queued', state: 'QUEUE', content: 'Read https://postiz.item79.com' + p, settings: '{}', image: '[]' });
  if (options.repeating) rows[0].intervalInDays = 7;
  const db = {
    integration: { findMany: async () => ids.map(id => ({ id, internalId: 'owned', organizationId: org })) },
    post: { findMany: async () => rows },
    media: { findMany: async () => [{ id: 'm1', path: p, organizationId: org, status: 'ready', _count: {} }], updateMany: async () => ({ count: 1 }) },
    comments: { findMany: async () => [] }, messages: { findMany: async () => [] }, plugs: { findMany: async () => [] },
    $executeRawUnsafe: async () => {}, $disconnect: async () => {},
    $transaction: async fn => {
      transactions++; inTransaction = true;
      try { const r = await fn(db); if (transactions === options.failCommit) throw Error('Commit failed'); return r; }
      finally { inTransaction = false; }
    },
  };
  const old = new Date(Date.now() - 9 * 86400000).toISOString();
  const google = { auth: { OAuth2: class { setCredentials() {} } }, youtube: () => ({ videos: { list: async () => {
    if (inTransaction) { state.apiCallsInTransaction++; throw Error('Network inside transaction'); }
    return { data: { items: [{ id: videoId, snippet: { channelId: 'owned', publishedAt: old }, status: { privacyStatus: 'public', uploadStatus: 'processed' }, processingDetails: { processingStatus: 'succeeded' }, contentDetails: {} }] } };
  } } }) };
  const sandbox = { module: { exports: {} }, require: name => name === 'node:fs' ? proxyFs : name === 'node:path' ? path.posix : name === '@prisma/client' ? { PrismaClient: class { constructor() { return db; } } } : name === 'googleapis' ? { google } : require(name), console, Buffer, process, URL };
  vm.runInNewContext(fs.readFileSync(new URL('../ops/item79-video-gate.cjs', import.meta.url), 'utf8'), sandbox);
  const gate = sandbox.module.exports;
  const observed = { [ids[0] + ':' + videoId]: old };
  return { ...state, options, gate, observed, async request() {
    const result = await gate.main({ mode: 'inspect', observed });
    const expected = result.candidates[0];
    return { mode: 'remove', observed, expected, recovery: { restoredAndHashed: true, sha256: expected.sha256, bytes: expected.bytes }, operationId: 'a'.repeat(32) };
  } };
}
test('failed tombstone commit preserves the original file', async t => {
  const f = fixture(t, { failCommit: 1 });
  await assert.rejects(f.gate.main(await f.request()));
  assert.equal(fs.readFileSync(f.file, 'utf8'), 'approved video');
});
test('failed quarantine commit restores bytes and leaves a resumable receipt', async t => {
  const f = fixture(t, { failCommit: 2 }); const request = await f.request();
  await assert.rejects(f.gate.main(request));
  assert.equal(fs.readFileSync(f.file, 'utf8'), 'approved video');
  assert.equal((await f.gate.main({ mode: 'receipt', operationId: request.operationId })).state, 'RESTORED');
});
test('concurrent file replacement is restored and never unlinked', async t => {
  const f = fixture(t, { replaceBeforeRename: true });
  await assert.rejects(f.gate.main(await f.request()));
  assert.equal(fs.readFileSync(f.file, 'utf8'), 'replacement video');
});
test('acknowledgement loss after unlink reconciles exact server intent', async t => {
  const f = fixture(t, { crashAfterUnlink: true }); const request = await f.request();
  await assert.rejects(f.gate.main(request));
  assert.equal(fs.existsSync(f.file), false);
  // Simulate a restart without the injected crash.
  // Saved COMMITTED + absent quarantine distinguishes post-unlink acknowledgement loss.
  // Directly inspect the durable on-disk journal, then normal restart is tested below.
  const journal = path.join(path.dirname(path.dirname(path.dirname(f.file))), '..', '.item79-cleanup', request.operationId + '.json');
  assert.equal(JSON.parse(fs.readFileSync(journal)).state, 'COMMITTED');
  f.options.crashAfterUnlink = false;
  assert.equal((await f.gate.main({ mode: 'receipt', operationId: request.operationId })).state, 'REMOVED');
});
test('successful cleanup hides media then removes only the pinned file; API stays outside locks', async t => {
  const f = fixture(t); const request = await f.request();
  const result = await f.gate.main(request);
  assert.equal(result.operationId, request.operationId);
  assert.equal(result.sha256, request.expected.sha256);
  assert.equal(fs.existsSync(f.file), false);
  assert.equal((await f.gate.main({ mode: 'receipt', operationId: request.operationId })).state, 'REMOVED');
});
test('queued text references and repeating published posts protect media', async t => {
  for (const option of [{ queuedContentReference: true }, { repeating: true }]) {
    const f = fixture(t, option);
    const result = await f.gate.main({ mode: 'inspect', observed: f.observed });
    assert.equal(result.candidates.length, 0);
    assert.equal(fs.existsSync(f.file), true);
  }
});
