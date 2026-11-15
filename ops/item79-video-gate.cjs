/* Run inside the existing web container. Credentials never leave this process. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { PrismaClient } = require('@prisma/client');
const { google } = require('googleapis');
const ORG = 'd12fad39-e950-4f96-8d7a-58cd1e580d22';
const IDS = ['cmweat59e0001o47f4n3hb7x3', 'cmwef8i230001pd7wcv85jj3i', 'cmwece9dg0004o47fzk35186s'];
const DAYS = 7 * 86400000;
function uploadPath(value) {
  if (typeof value !== 'string') return null;
  const u = new URL(value, 'https://postiz.item79.com');
  if (u.origin !== 'https://postiz.item79.com') return null;
  if (!u.pathname.startsWith('/uploads/')) return null;
  const p = decodeURIComponent(u.pathname);
  if (!p.startsWith('/uploads/')) return null;
  if (!/\.(mp4|mov|m4v|webm)$/i.test(p)) return null;
  if (!/^\/uploads\/\d{4}\/\d{1,2}\/\d{1,2}\/[a-f0-9]+\.(mp4|mov|m4v|webm)$/i.test(p)) throw Error('Noncanonical upload');
  return p;
}
function refs(value, paths = new Set(), ids = new Set()) {
  if (typeof value === 'string') {
    for (const token of value.match(/https?:\/\/[^\s"'<>]+|\/uploads\/[^\s"'<>]+/g) || []) {
      const p = uploadPath(token.replace(/[),;]+$/, '')); if (p) paths.add(p);
    }
  }
  else if (Array.isArray(value)) value.forEach(v => refs(v, paths, ids));
  else if (value && typeof value === 'object') {
    if (typeof value.id === 'string') ids.add(value.id);
    Object.values(value).forEach(v => refs(v, paths, ids));
  }
  return { paths, ids };
}
function parse(value) { return value ? JSON.parse(value) : []; }
function goodVideo(v, channel, now) {
  return v && v.snippet?.channelId === channel && v.status?.privacyStatus === 'public' &&
    v.status?.uploadStatus === 'processed' && v.processingDetails?.processingStatus === 'succeeded' &&
    !v.status?.publishAt && Number.isFinite(Date.parse(v.snippet?.publishedAt)) &&
    Date.parse(v.snippet.publishedAt) <= now - DAYS &&
    !v.contentDetails?.regionRestriction;
}
function fileProof(p) {
  const absolute = path.resolve(p);
  if (absolute !== p || !p.startsWith('/uploads/') || fs.realpathSync(p) !== p) throw Error('Unsafe file path');
  const stat = fs.lstatSync(p);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 || stat.size > 512 * 1024 ** 2) throw Error('Unsafe file');
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(p, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const buffer = Buffer.alloc(1024 * 1024); let bytes;
    while ((bytes = fs.readSync(fd, buffer, 0, buffer.length, null))) hash.update(buffer.subarray(0, bytes));
    const after = fs.fstatSync(fd);
    if (after.ino !== stat.ino || after.size !== stat.size || after.mtimeMs !== stat.mtimeMs) throw Error('File changed');
  } finally { fs.closeSync(fd); }
  return { sha256: hash.digest('hex'), bytes: stat.size, ino: stat.ino, mtimeMs: stat.mtimeMs };
}
async function snapshot(db, input, cached) {
  const integrations = await db.integration.findMany({ where: { id: { in: IDS }, organizationId: ORG, providerIdentifier: 'youtube', deletedAt: null } });
  if (integrations.length !== IDS.length) throw Error('Channel scope changed');
  // Include every organization: an outside reservation referencing the same bytes protects them.
  const posts = await db.post.findMany({ select: { id: true, integrationId: true, organizationId: true, state: true, deletedAt: true, releaseId: true, image: true, settings: true, content: true, title: true, description: true, intervalInDays: true, updatedAt: true, error: true } });
  const media = await db.media.findMany({ select: { id: true, path: true, organizationId: true, deletedAt: true, status: true, thumbnail: true,
    _count: { select: { agencies: true, userPicture: true, oauthApps: true } } } });
  const auxiliary = refs([
    await db.comments.findMany({ select: { content: true, anchorQuote: true } }),
    await db.messages.findMany({ select: { content: true, special: true } }),
    await db.plugs.findMany({ select: { data: true } }),
  ]);
  const mediaPaths = new Map(media.map(m => [m.id, uploadPath(m.path)]));
  for (const p of posts) {
    p.refs = refs([parse(p.image), parse(p.settings), p.content, p.title, p.description]);
    for (const id of p.refs.ids) { const mp = mediaPaths.get(id); if (mp) p.refs.paths.add(mp); }
  }
  const now = Date.now(), candidates = [], publicIds = [], protectedCounts = {};
  const observed = input.observed || {};
  const videos = cached?.videos || new Map();
  if (cached && Date.now() - cached.at > 60000) throw Error('Provider evidence expired');
  for (const i of cached ? [] : integrations) {
    const ids = [...new Set(posts.filter(p => p.integrationId === i.id && p.state === 'PUBLISHED' && !p.deletedAt).map(p => p.releaseId).filter(id => /^[\w-]{11}$/.test(id || '')))];
    if (!ids.length) continue;
    const client = new google.auth.OAuth2({ clientId: process.env.YOUTUBE_CLIENT_ID, clientSecret: process.env.YOUTUBE_CLIENT_SECRET, forceRefreshOnFailure: true });
    client.setCredentials({ access_token: i.token, refresh_token: i.refreshToken, expiry_date: i.tokenExpiration?.getTime() });
    for (let n = 0; n < ids.length; n += 50) {
      const result = await google.youtube({ version: 'v3', auth: client }).videos.list({ id: ids.slice(n, n + 50), part: ['snippet', 'status', 'processingDetails', 'contentDetails'] }, { timeout: 20000 });
      for (const v of result.data.items || []) {
        if (v.snippet?.channelId === i.internalId && v.status?.privacyStatus === 'public' && v.status?.uploadStatus === 'processed') publicIds.push(i.id + ':' + v.id);
        videos.set(i.id + ':' + v.id, v);
      }
    }
  }
  const paths = new Set(media.filter(m => m.organizationId === ORG).map(m => uploadPath(m.path)).filter(Boolean));
  for (const p of paths) {
    if (!fs.existsSync(p) && !(input.mode === 'local-check' && input.expected?.path === p)) continue;
    const linked = posts.filter(post => post.refs.paths.has(p));
    let reason = null;
    if (!linked.length) reason = 'unreferenced_without_provenance';
    else if (media.some(m => uploadPath(m.path) === p && (m.status !== 'ready' || Object.values(m._count || {}).some(Boolean))) || media.some(m => uploadPath(m.thumbnail) === p)) reason = 'media_processing_or_other_use';
    else if (auxiliary.paths.has(p)) reason = 'auxiliary_reference';
    else if (linked.some(post => post.organizationId !== ORG || !IDS.includes(post.integrationId) || post.state !== 'PUBLISHED' || post.deletedAt || post.error || post.intervalInDays)) reason = 'active_or_unknown_reference';
    else if (linked.some(post => {
      const key = post.integrationId + ':' + post.releaseId;
      return !goodVideo(videos.get(key), integrations.find(i => i.id === post.integrationId)?.internalId, now) ||
        !Number.isFinite(Date.parse(observed[key])) || Date.parse(observed[key]) > now - DAYS;
    })) reason = 'publication_or_seven_day_hold';
    if (reason) { protectedCounts[reason] = (protectedCounts[reason] || 0) + 1; continue; }
    // An outside Media record may be selected in an uncommitted/new post later. Protect shared ownership.
    if (media.some(m => uploadPath(m.path) === p && m.organizationId !== ORG)) throw Error('Shared media ownership');
    const proof = fs.existsSync(p) ? fileProof(p) : { sha256: input.expected.sha256, bytes: input.expected.bytes, ino: input.expected.ino, mtimeMs: input.expected.mtimeMs };
    candidates.push({ path: p, ...proof, postIds: linked.map(post => post.id).sort(), mediaIds: media.filter(m => uploadPath(m.path) === p).map(m => m.id).sort() });
  }
  return { capturedAt: new Date().toISOString(), publicIds, candidates, protectedCounts, _cached: { at: Date.now(), videos } };
}
const JOURNAL = '/uploads/.item79-cleanup';
function saveReceipt(id, value) {
  if (!/^[a-f0-9]{32}$/.test(id)) throw Error('Invalid operation ID');
  fs.mkdirSync(JOURNAL, { recursive: true, mode: 0o700 });
  if (fs.realpathSync(JOURNAL) !== JOURNAL) throw Error('Unsafe journal');
  const file = JOURNAL + '/' + id + '.json';
  const fd = fs.openSync(file + '.pending', 'w', 0o600);
  try { fs.writeFileSync(fd, JSON.stringify(value)); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(file + '.pending', file);
  if (process.platform === 'linux') { const dir = fs.openSync(JOURNAL, 'r'); try { fs.fsyncSync(dir); } finally { fs.closeSync(dir); } }
}
function receipt(id) {
  if (!/^[a-f0-9]{32}$/.test(id)) throw Error('Invalid operation ID');
  const file = JOURNAL + '/' + id + '.json';
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : { state: 'NOT_STARTED', operationId: id };
}
function restoreInterrupted() {
  if (!fs.existsSync(JOURNAL)) return;
  if (fs.realpathSync(JOURNAL) !== JOURNAL) throw Error('Unsafe journal');
  for (const name of fs.readdirSync(JOURNAL).filter(n => /^[a-f0-9]{32}\.json$/.test(n))) {
    const prior = receipt(name.slice(0, -5));
    if (['REMOVED', 'RESTORED'].includes(prior.state)) continue;
    const p = uploadPath(prior.expected.path), quarantine = JOURNAL + '/' + prior.operationId + '.video';
    if (fs.existsSync(quarantine)) {
      const proof = fileProof(quarantine);
      if (fs.existsSync(p)) throw Error('Interrupted cleanup requires reconciliation');
      fs.renameSync(quarantine, p);
    } else if (!fs.existsSync(p)) {
      // Crash after unlink: exact persisted intent + independent backup identifies what was removed.
      if (prior.state !== 'COMMITTED') throw Error('Missing quarantine requires reconciliation');
      prior.state = 'REMOVED'; saveReceipt(prior.operationId, prior); continue;
    }
    prior.state = 'RESTORED'; saveReceipt(prior.operationId, prior);
  }
}
async function main(input) {
  const db = new PrismaClient();
  try {
    restoreInterrupted();
    if (input.mode === 'receipt') return receipt(input.operationId);
    if (input.mode === 'inspect') { const result = await snapshot(db, input); delete result._cached; return result; }
    if (input.mode === 'local-check') {
      const current = await snapshot(db, input);
      const found = current.candidates.find(c => c.path === input.expected.path);
      return { permitted: !!found && JSON.stringify(found) === JSON.stringify(input.expected) };
    }
    if (input.mode !== 'remove' || !input.expected || !input.recovery?.restoredAndHashed) throw Error('Invalid apply request');
    const preflight = await snapshot(db, input);
    const e = input.expected;
    const initial = preflight.candidates.find(c => c.path === e.path);
    if (!initial || JSON.stringify(initial) !== JSON.stringify(e) || input.recovery.sha256 !== e.sha256 || input.recovery.bytes !== e.bytes) throw Error('Eligibility changed');
    const id = input.operationId;
    const prior = receipt(id);
    if (prior.state !== 'NOT_STARTED') throw Error('Operation already exists');
    // Commit the media-picker tombstone first. A failed DB commit never removes bytes.
    await db.$transaction(async tx => {
      await tx.$executeRawUnsafe('LOCK TABLE "Post", "Media", "Integration", "Comments", "Messages", "Plugs" IN SHARE ROW EXCLUSIVE MODE');
      const current = await snapshot(tx, input, preflight._cached);
      if (JSON.stringify(current.candidates.find(c => c.path === e.path)) !== JSON.stringify(e)) throw Error('References changed');
      await tx.media.updateMany({ where: { id: { in: e.mediaIds }, organizationId: ORG }, data: { deletedAt: new Date() } });
    }, { maxWait: 1000, timeout: 10000 });
    const record = { state: 'PREPARED', operationId: id, expected: e, recovery: input.recovery, at: new Date().toISOString() };
    saveReceipt(id, record);
    const quarantine = JOURNAL + '/' + id + '.video';
    try {
      await db.$transaction(async tx => {
        await tx.$executeRawUnsafe('LOCK TABLE "Post", "Media", "Integration", "Comments", "Messages", "Plugs" IN SHARE MODE');
        const current = await snapshot(tx, input, preflight._cached);
        if (JSON.stringify(current.candidates.find(c => c.path === e.path)) !== JSON.stringify(e)) throw Error('References changed');
        if (fs.existsSync(quarantine)) throw Error('Quarantine exists');
        fs.renameSync(e.path, quarantine);
        const moved = fileProof(quarantine);
        if (JSON.stringify(moved) !== JSON.stringify({ sha256: e.sha256, bytes: e.bytes, ino: e.ino, mtimeMs: e.mtimeMs })) throw Error('File replaced before quarantine');
        record.state = 'QUARANTINED'; saveReceipt(id, record);
      }, { maxWait: 1000, timeout: 10000 });
    } catch (error) { restoreInterrupted(); throw error; }
    record.state = 'COMMITTED'; saveReceipt(id, record);
    fs.unlinkSync(quarantine);
    record.state = 'REMOVED'; saveReceipt(id, record);
    return { removed: e.path, operationId: id, ...e, recovery: input.recovery };
  } finally { await db.$disconnect(); }
}
module.exports = { uploadPath, refs, goodVideo, fileProof, main };
if (require.main === module) {
  const input = JSON.parse(Buffer.from(process.argv[2], 'base64').toString());
  main(input).then(result => console.log(JSON.stringify(result))).catch(() => { console.error('Video gate failed closed'); process.exitCode = 1; });
}
