// 콘티 API — 계정 · 팀 · 초대. Vercel 서버리스 함수 하나(api/index.js)에 작은 라우터.
// vercel.json 의 rewrite 가 /api/* 를 /api?p=<경로> 로 보내고, 여기서 p(또는 원래 pathname)로 라우팅합니다.
// 로컬: npm run dev (scripts/dev.mjs가 이 핸들러를 /api/* 에 그대로 붙임)
import { q, one } from '../lib/db.js';
import { sessionUserId, sessionCookie, clearSessionCookie, randomToken } from '../lib/session.js';
import { hashPassword, verifyPassword, USERNAME_RE, PASSWORD_MIN } from '../lib/password.js';
import { putBlob, delBlobs } from '../lib/blob.js';
import { ocrBands, visionConfigured } from '../lib/vision.js';

class HttpError extends Error { constructor(status, code, message) { super(message || code); this.status = status; this.code = code; } }
const bad = (m) => new HttpError(400, 'bad_request', m);
const noAuth = () => new HttpError(401, 'unauthorized', '로그인이 필요해요');
const forbidden = (m) => new HttpError(403, 'forbidden', m || '권한이 없어요');
const notFound = (m) => new HttpError(404, 'not_found', m || '없어요');

/* ---------- 요청/응답 도우미 ---------- */
async function readBody(req) {
  if (req.body !== undefined && req.body !== null) return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body;
  return new Promise((res, rej) => {
    let s = ''; req.setEncoding('utf8');
    req.on('data', (c) => { s += c; if (s.length > 1e6) rej(bad('요청이 너무 커요')); });
    req.on('end', () => { try { res(s ? JSON.parse(s) : {}); } catch { rej(bad('JSON이 아니에요')); } });
    req.on('error', rej);
  });
}
async function readRaw(req, max = 80 * 1024 * 1024) {
  if (req.body !== undefined && req.body !== null && Buffer.isBuffer(req.body)) return req.body;
  return new Promise((res, rej) => {
    const chunks = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n > max) { rej(new HttpError(413, 'too_large', '파일이 너무 커요 (80MB 이하)')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => res(Buffer.concat(chunks)));
    req.on('error', rej);
  });
}
function send(res, status, data, headers) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  for (const k in headers || {}) res.setHeader(k, headers[k]);
  res.end(JSON.stringify(data));
}
const str = (v, max = 200) => (typeof v === 'string' ? v.trim().slice(0, max) : '');
const strList = (v) => Array.isArray(v) ? v.map((s) => str(s, 40)).filter(Boolean).slice(0, 30) : null;

/* ---------- 도메인 ---------- */
const memberView = (t, m) => ({
  teamId: t.id, teamName: t.name, sessions: t.sessions, phrases: t.phrases,
  invite: m.role === 'leader' ? t.invite_token : undefined,
  me: { userId: m.user_id, name: m.name, session: m.session, role: m.role },
});
async function membership(uid, teamId) {
  return one(`select t.*, m.user_id, m.name as mname, m.session, m.role from members m join teams t on t.id=m.team_id
              where m.user_id=$1 ${teamId ? 'and m.team_id=$2' : ''} order by m.created_at asc limit 1`, teamId ? [uid, teamId] : [uid]);
}
const viewOf = (row) => row && memberView(row, { user_id: row.user_id, name: row.mname, session: row.session, role: row.role });
async function requireMember(uid, teamId, role) {
  const m = await membership(uid, teamId);
  if (!m) throw forbidden('이 팀의 멤버가 아니에요');
  if (role === 'leader' && m.role !== 'leader') throw forbidden('인도자만 할 수 있어요');
  return m;
}
async function meView(uid) {
  const u = await one('select id, username, display_name from users where id=$1', [uid]);
  if (!u) throw noAuth();
  const rows = await q(`select t.*, m.user_id, m.name as mname, m.session, m.role from members m join teams t on t.id=m.team_id
                        where m.user_id=$1 order by m.created_at asc`, [uid]);
  return { user: { id: u.id, username: u.username, name: u.display_name }, team: rows[0] ? viewOf(rows[0]) : null, teams: rows.map(viewOf) };
}
function pickSession(team, s) {
  const list = team.sessions || [];
  return list.includes(s) ? s : (list[0] || '');
}

/* ---------- 라우트 ---------- */
const routes = [];
const on = (method, pattern, fn) => routes.push({ method, re: new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn });

on('GET', '/health', async () => ({ ok: true, app: 'conti' }));

on('POST', '/auth/signup', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), password = String(body.password || ''), name = str(body.name, 40);
  if (!USERNAME_RE.test(username)) throw bad('아이디는 3~20자, 영문 소문자·숫자·. _ - 만 쓸 수 있어요');
  if (password.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  if (!name) throw bad('이름을 적어 주세요');
  if (await one('select 1 from users where username=$1', [username])) throw new HttpError(409, 'taken', '이미 쓰는 아이디예요');
  const u = await one('insert into users(username, password_hash, display_name, last_login_at) values($1,$2,$3,now()) returning id', [username, hashPassword(password), name]);
  return { data: await meView(u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

on('POST', '/auth/login', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), password = String(body.password || '');
  try {
    const la = await one('select n, last from login_attempts where username=$1', [username]);
    if (la && la.n >= 8 && Date.now() - new Date(la.last).getTime() < 15 * 60 * 1000) throw new HttpError(429, 'locked', '로그인 시도가 너무 많아요. 15분 뒤에 다시 해 주세요');
  } catch (e) { if (e instanceof HttpError) throw e; }
  const u = await one('select id, password_hash from users where username=$1', [username]);
  if (!u || !verifyPassword(password, u.password_hash)) {
    try { await q(`insert into login_attempts(username, n, last) values($1, 1, now()) on conflict (username) do update set n = case when login_attempts.last < now() - interval '15 minutes' then 1 else login_attempts.n + 1 end, last = now()`, [username]); } catch (e) {}
    throw new HttpError(401, 'bad_login', '아이디 또는 비밀번호가 맞지 않아요');
  }
  try { await q('delete from login_attempts where username=$1', [username]); } catch (e) {}
  await q('update users set last_login_at=now() where id=$1', [u.id]);
  return { data: await meView(u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

on('POST', '/auth/logout', async ({ req }) => ({ data: { ok: true }, headers: { 'Set-Cookie': clearSessionCookie(req) } }));

on('POST', '/auth/password', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const cur = String(body.current || ''), next = String(body.next || '');
  if (next.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  const u = await one('select password_hash from users where id=$1', [uid]);
  if (!verifyPassword(cur, u.password_hash)) throw new HttpError(401, 'bad_login', '현재 비밀번호가 맞지 않아요');
  await q('update users set password_hash=$2 where id=$1', [uid, hashPassword(next)]);
  return { ok: true };
});

on('GET', '/me', async ({ uid }) => { if (!uid) throw noAuth(); return meView(uid); });

// 내 이름·세션(팀 안에서) 바꾸기
on('PATCH', '/me', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const name = str(body.name, 40) || m.mname, session = pickSession(m, str(body.session, 40) || m.session);
  await q('update members set name=$3, session=$4 where user_id=$1 and team_id=$2', [uid, teamId, name, session]);
  await q('update users set display_name=$2 where id=$1', [uid, name]);
  return viewOf(await membership(uid, teamId));
});

on('POST', '/teams', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const name = str(body.name, 60), myName = str(body.myName, 40);
  if (!name) throw bad('팀 이름을 적어 주세요');
  if (!myName) throw bad('내 이름을 적어 주세요');
  const t = await one('insert into teams(name, invite_token, created_by) values($1,$2,$3) returning *', [name, randomToken(12), uid]);
  const session = pickSession(t, str(body.session, 40) || '인도자');
  await q('insert into members(user_id, team_id, name, session, role) values($1,$2,$3,$4,$5)', [uid, t.id, myName, session, 'leader']);
  return viewOf(await membership(uid, t.id));
});

on('GET', '/teams/:id', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const members = await q('select user_id as "userId", name, session, role, created_at as "joinedAt" from members where team_id=$1 order by created_at asc', [params.id]);
  return { ...viewOf(m), members };
});

on('PATCH', '/teams/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const name = str(body.name, 60), sessions = strList(body.sessions), phrases = strList(body.phrases);
  if (sessions && !sessions.length) throw bad('세션은 하나 이상 있어야 해요');
  await q(`update teams set name=coalesce(nullif($2,''), name), sessions=coalesce($3::jsonb, sessions), phrases=coalesce($4::jsonb, phrases) where id=$1`,
    [params.id, name, sessions ? JSON.stringify(sessions) : null, phrases ? JSON.stringify(phrases) : null]);
  if (sessions) await q(`update members set session=$2 where team_id=$1 and not (session = any($3::text[]))`, [params.id, sessions[0], sessions]);
  return viewOf(await membership(uid, params.id));
});

on('POST', '/teams/:id/invite/rotate', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  await q('update teams set invite_token=$2 where id=$1', [params.id, randomToken(12)]);
  return viewOf(await membership(uid, params.id));
});

on('PATCH', '/teams/:id/members/:userId', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const role = str(body.role, 20);
  if (!['leader', 'session_lead', 'member'].includes(role)) throw bad('역할이 이상해요');
  if (params.userId === uid && role !== 'leader') {
    const n = await one('select count(*)::int as n from members where team_id=$1 and role=$2', [params.id, 'leader']);
    if (n.n <= 1) throw bad('인도자가 한 명뿐이라 역할을 내릴 수 없어요. 먼저 다른 사람을 인도자로 지정하세요');
  }
  const r = await q('update members set role=$3 where team_id=$1 and user_id=$2 returning user_id', [params.id, params.userId, role]);
  if (!r.length) throw notFound('그 멤버가 없어요');
  return { ok: true };
});

on('POST', '/teams/:id/members/:userId/reset', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  if (params.userId === uid) throw bad('내 비밀번호는 설정에서 바꿔 주세요');
  const target = await one('select user_id from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
  if (!target) throw notFound('그 멤버가 없어요');
  const alphabet = 'abcdefghjkmnpqrstuvwxyz23456789';
  const bytes = randomToken(12); let pw = '';
  for (let i = 0; i < 8; i++) pw += alphabet[bytes.charCodeAt(i) % alphabet.length];
  await q('update users set password_hash=$2 where id=$1', [params.userId, hashPassword(pw)]);
  return { password: pw };
});

on('DELETE', '/teams/:id/members/:userId', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const self = params.userId === uid;
  if (!self && m.role !== 'leader') throw forbidden('인도자만 내보낼 수 있어요');
  if (self && m.role === 'leader') {
    const n = await one('select count(*)::int as n from members where team_id=$1 and role=$2', [params.id, 'leader']);
    if (n.n <= 1) throw bad('인도자가 한 명뿐이라 나갈 수 없어요. 먼저 다른 사람을 인도자로 지정하세요');
  }
  await q('delete from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
  return { ok: true };
});

on('GET', '/invite/:token', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const t = await one('select id, name, sessions from teams where invite_token=$1', [params.token]);
  if (!t) throw notFound('초대 링크가 만료됐거나 잘못됐어요');
  const n = await one('select count(*)::int as n from members where team_id=$1', [t.id]);
  const mine = await membership(uid, t.id);
  return { teamName: t.name, sessions: t.sessions, count: n.n, alreadyMember: !!mine };
});

on('POST', '/invite/:token/join', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const t = await one('select * from teams where invite_token=$1', [params.token]);
  if (!t) throw notFound('초대 링크가 만료됐거나 잘못됐어요');
  const name = str(body.name, 40);
  if (!name) throw bad('이름을 적어 주세요');
  const session = pickSession(t, str(body.session, 40));
  await q(`insert into members(user_id, team_id, name, session, role) values($1,$2,$3,$4,'member')
           on conflict (user_id, team_id) do update set name=excluded.name, session=excluded.session`, [uid, t.id, name, session]);
  await q('update users set display_name=$2 where id=$1', [uid, name]);
  return viewOf(await membership(uid, t.id));
});


/* ---------- 발행본 · 파일 · 메모 동기화 ---------- */
// 팀의 발행본 목록
on('GET', '/services', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  return { services: await q('select id, name, date, version, updated_at as "updatedAt" from services where team_id=$1 order by date desc', [teamId]) };
});

// 발행본 하나 + 참조 파일 URL
on('GET', '/services/:id', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const row = await one('select doc, version, updated_at as "updatedAt" from services where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) throw notFound('발행된 콘티가 없어요');
  const ids = blobIdsOf(row.doc);
  const blobs = ids.length ? await q('select id, url, type from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return { doc: row.doc, version: row.version, updatedAt: row.updatedAt, blobs: Object.fromEntries(blobs.map((b) => [b.id, b.url])) };
});
function blobIdsOf(doc) {
  const ids = new Set();
  for (const it of (doc && doc.items) || []) {
    for (const p of it.pieces || []) if (p.blob) ids.add(p.blob);
    for (const m of it.media || []) if (m.type === 'audio' && m.blob) ids.add(m.blob);
  }
  return [...ids];
}

// 발행 (인도자): 스냅샷 upsert
on('PUT', '/services/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const doc = body.doc;
  if (!doc || !Array.isArray(doc.items)) throw bad('발행본이 비어 있어요');
  const missing = blobIdsOf(doc);
  const have = missing.length ? (await q('select id from blobs where team_id=$1 and id = any($2::text[])', [teamId, missing])).map((r) => r.id) : [];
  const notUploaded = missing.filter((id) => !have.includes(id));
  if (notUploaded.length) throw bad('아직 올라가지 않은 파일이 있어요: ' + notUploaded.length + '개');
  await q(`insert into services(team_id, id, doc, version, name, date, updated_by, updated_at) values($1,$2,$3,$4,$5,$6,$7,now())
           on conflict (team_id, id) do update set doc=excluded.doc, version=excluded.version, name=excluded.name, date=excluded.date, updated_by=excluded.updated_by, updated_at=now()`,
    [teamId, params.id, JSON.stringify(doc), +doc.version || 0, str(doc.name, 120), str(doc.date, 20), uid]);
  return { ok: true, version: +doc.version || 0 };
});

on('DELETE', '/services/:id', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const row = await one('select doc from services where team_id=$1 and id=$2', [teamId, params.id]);
  await q('delete from services where team_id=$1 and id=$2', [teamId, params.id]);
  await q('delete from notes where team_id=$1 and service_id=$2', [teamId, params.id]);
  let freed = 0;
  if (row) {
    const mine = blobIdsOf(row.doc);
    if (mine.length) {
      const others = await q('select doc from services where team_id=$1', [teamId]);
      const used = new Set(); others.forEach((o) => blobIdsOf(o.doc).forEach((id) => used.add(id)));
      const orphan = mine.filter((id) => !used.has(id));
      if (orphan.length) {
        const rows = await q('delete from blobs where team_id=$1 and id = any($2::text[]) returning url', [teamId, orphan]);
        await delBlobs(rows.map((r) => r.url)); freed = rows.length;
      }
    }
  }
  return { ok: true, freedFiles: freed };
});

// 파일: 어떤 id가 이미 있는지
on('GET', '/blobs', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const ids = str(url.searchParams.get('ids'), 4000).split(',').filter(Boolean).slice(0, 200);
  const rows = ids.length ? await q('select id, url from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return { blobs: Object.fromEntries(rows.map((r) => [r.id, r.url])) };
});

// 파일 올리기 (인도자): 본문이 파일 그 자체
on('POST', '/blobs/:id', async ({ req, uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  if (!/^[A-Za-z0-9_-]{4,40}$/.test(params.id)) throw bad('파일 id가 이상해요');
  const existing = await one('select url from blobs where team_id=$1 and id=$2', [teamId, params.id]);
  if (existing) return { url: existing.url, existed: true };
  const buf = await readRaw(req);
  if (!buf.length) throw bad('빈 파일이에요');
  const type = str(req.headers['content-type'], 100) || 'application/octet-stream';
  const ext = type.includes('jpeg') ? '.jpg' : type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : type.startsWith('audio/') ? '.audio' : '';
  const blobUrl = await putBlob(`teams/${teamId}/${params.id}${ext}`, buf, type);
  await q('insert into blobs(team_id, id, url, type, size) values($1,$2,$3,$4,$5) on conflict (team_id, id) do nothing', [teamId, params.id, blobUrl, type, buf.length]);
  return { url: blobUrl };
});

// 메모: 내가 볼 수 있는 것 = 인도자 메모 전부 + 내 세션 공유 메모 + 내 메모
on('GET', '/notes', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64), svcId = str(url.searchParams.get('service'), 64);
  const m = await requireMember(uid, teamId);
  const rows = await q(`select id, item_id as "itemId", marker_id as "markerId", media_id as "mediaId", t, layer, session, text, author_id as "authorId", author_name as "authorName", created_at as "createdAt"
                        from notes where team_id=$1 and service_id=$2 and (layer='leader' or (layer='session' and session=$4) or author_id=$3) order by created_at asc`, [teamId, svcId, uid, m.session]);
  return { notes: rows, me: uid };
});

on('POST', '/notes', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64), svcId = str(body.serviceId, 64);
  const m = await requireMember(uid, teamId);
  const list = Array.isArray(body.notes) ? body.notes.slice(0, 200) : [];
  let n = 0;
  for (const x of list) {
    const id = str(x.id, 40), itemId = str(x.itemId, 40), layer = str(x.layer, 10), text = str(x.text, 200);
    if (!/^[A-Za-z0-9_-]{4,40}$/.test(id) || !itemId || !text) continue;
    if (!['leader', 'session', 'mine'].includes(layer)) continue;
    if (layer === 'leader' && m.role !== 'leader') continue;
    const session = layer === 'session' ? m.session : layer === 'leader' ? (str(x.session, 40) || null) : null;
    await q(`insert into notes(id, team_id, service_id, item_id, marker_id, media_id, t, layer, session, text, author_id, author_name, created_at)
             values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) on conflict (id) do nothing`,
      [id, teamId, svcId, itemId, str(x.markerId, 40) || null, str(x.mediaId, 40) || null, x.t == null ? null : +x.t, layer, session, text, uid, layer === 'leader' ? '인도자' : m.name, x.at ? new Date(+x.at) : new Date()]);
    n++;
  }
  return { ok: true, saved: n };
});

on('DELETE', '/notes', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const ids = (Array.isArray(body.ids) ? body.ids : []).map((x) => str(x, 40)).filter(Boolean).slice(0, 200);
  if (!ids.length) return { ok: true, deleted: 0 };
  const r = m.role === 'leader'
    ? await q('delete from notes where team_id=$1 and id = any($2::text[]) returning id', [teamId, ids])
    : await q('delete from notes where team_id=$1 and id = any($2::text[]) and author_id=$3 returning id', [teamId, ids, uid]);
  return { ok: true, deleted: r.length };
});

// 코드 OCR (인도자): 클라이언트가 자른 코드 띠 이미지들을 Vision 에 넘김
on('GET', '/ocr', async ({ uid }) => { if (!uid) throw noAuth(); return { available: visionConfigured(), mock: process.env.GOOGLE_VISION_KEY === 'mock' }; });
on('POST', '/ocr', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  if (!visionConfigured()) throw new HttpError(503, 'no_ocr', '코드 인식 엔진이 아직 연결되지 않았어요 (GOOGLE_VISION_KEY)');
  const images = (Array.isArray(body.images) ? body.images : []).slice(0, 16).map((im) => ({ b64: String(im.b64 || ''), mime: str(im.mime, 40), w: +im.w || 0, h: +im.h || 0 })).filter((im) => im.b64.length > 100);
  if (!images.length) throw bad('이미지가 없어요');
  if (images.reduce((n, im) => n + im.b64.length, 0) > 12 * 1024 * 1024) throw new HttpError(413, 'too_large', '이미지가 너무 커요');
  const results = await ocrBands(images);
  return { results };
});

/* ---------- 진입점 ---------- */
export default async function handler(req, res) {
  try {
    const url = new URL(req.url, 'http://local');
    const raw = url.searchParams.has('p') ? '/' + url.searchParams.get('p') : url.pathname.replace(/^\/api/, '');
    const path = raw.replace(/\/+$/, '').replace(/^\/*/, '/') || '/';
    const method = req.method.toUpperCase();
    const route = routes.find((r) => r.method === method && r.re.test(path));
    if (!route) {
      if (routes.some((r) => r.re.test(path))) throw new HttpError(405, 'method_not_allowed', '허용되지 않는 방식이에요');
      throw notFound('그런 API는 없어요');
    }
    if (method !== 'GET' && req.headers['x-conti'] !== '1') throw forbidden('앱에서만 호출할 수 있어요');
    const params = path.match(route.re).groups || {};
    const body = (method === 'GET' || /^\/blobs\//.test(path)) ? {} : await readBody(req);
    const uid = sessionUserId(req);
    const out = await route.fn({ req, uid, params, body, url });
    if (out && out.headers && 'data' in out) return send(res, 200, out.data, out.headers);
    return send(res, 200, out);
  } catch (e) {
    if (e instanceof HttpError) return send(res, e.status, { error: e.code, message: e.message });
    console.error(e);
    return send(res, 500, { error: 'server', message: '서버 오류가 났어요' });
  }
}
