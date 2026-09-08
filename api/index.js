// 콘티 API — 계정 · 팀 · 초대. Vercel 서버리스 함수 하나(api/index.js)에 작은 라우터.
// vercel.json 의 rewrite 가 /api/* 를 /api?p=<경로> 로 보내고, 여기서 p(또는 원래 pathname)로 라우팅합니다.
// 로컬: npm run dev (scripts/dev.mjs가 이 핸들러를 /api/* 에 그대로 붙임)
import { q, one } from '../lib/db.js';
import { sessionClaims, sessionCookie, clearSessionCookie, randomToken } from '../lib/session.js';
import { hashPassword, verifyPassword, USERNAME_RE, PASSWORD_MIN } from '../lib/password.js';
import { putBlob, delBlobs, readUrls, presignPut, headBlob } from '../lib/blob.js';
import { ocrBands, visionConfigured } from '../lib/vision.js';
import { transcribeSheet, geminiConfigured, geminiModel, estimateUSD } from '../lib/gemini.js';

class HttpError extends Error { constructor(status, code, message) { super(message || code); this.status = status; this.code = code; } }
const bad = (m) => new HttpError(400, 'bad_request', m);
const noAuth = () => new HttpError(401, 'unauthorized', '로그인이 필요해요');
const forbidden = (m) => new HttpError(403, 'forbidden', m || '권한이 없어요');
const notFound = (m) => new HttpError(404, 'not_found', m || '없어요');

/* ---------- 요청/응답 도우미 ---------- */
async function readBody(req, max = 1e6) {
  if (req.body !== undefined && req.body !== null) return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body;
  return new Promise((res, rej) => {
    let s = ''; req.setEncoding('utf8');
    req.on('data', (c) => { s += c; if (s.length > max) rej(bad('요청이 너무 커요')); });
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
const nowSec = () => Math.floor(Date.now() / 1000);
const strList = (v) => Array.isArray(v) ? v.map((s) => str(s, 40)).filter(Boolean).slice(0, 30) : null;

/* ---------- 도메인 ---------- */
const mySessions = (m) => (Array.isArray(m.msessions) && m.msessions.length ? m.msessions : (m.session ? [m.session] : []));
const memberView = (t, m) => ({
  teamId: t.id, teamName: t.name, sessions: t.sessions, phrases: t.phrases,
  invite: m.role === 'leader' ? t.invite_token : undefined,
  settings: { ...DEF_SETTINGS, ...(t.settings || {}) },
  me: { userId: m.user_id, name: m.name, session: m.session, mySessions: mySessions(m), role: m.role, capo: +m.capo || 0 },
});
const teamUserIds = async (teamId, { exceptRole, except } = {}) =>
  (await q('select user_id, role from members where team_id=$1', [teamId]))
    .filter((m) => m.role !== exceptRole && m.user_id !== except).map((m) => m.user_id);
const mdOf = (d) => { const m = String(d || '').match(/^\d{4}-(\d{2})-(\d{2})/); return m ? `${+m[1]}/${+m[2]}` : ''; };
// 조사 붙이기: 한글 받침과 숫자 읽는 소리를 보고 이/가, 을/를 을 고른다
const DIGIT_BATCHIM = [true, true, false, true, false, false, true, true, true, false]; // 영 일 이 삼 사 오 육 칠 팔 구
function hasBatchim(s) {
  const t = String(s || '').trim(); if (!t) return false;
  const c = t.charCodeAt(t.length - 1);
  if (c >= 0xac00 && c <= 0xd7a3) return (c - 0xac00) % 28 !== 0;
  if (c >= 0x30 && c <= 0x39) return DIGIT_BATCHIM[c - 0x30];
  return false;
}
const josa = (s, withB, withoutB) => `${s}${hasBatchim(s) ? withB : withoutB}`;
async function membership(uid, teamId) {
  return one(`select t.*, m.user_id, m.name as mname, m.session, m.sessions as msessions, m.role, m.capo from members m join teams t on t.id=m.team_id
              where m.user_id=$1 ${teamId ? 'and m.team_id=$2' : ''} order by m.created_at asc limit 1`, teamId ? [uid, teamId] : [uid]);
}
const viewOf = (row) => row && memberView(row, { user_id: row.user_id, name: row.mname, session: row.session, msessions: row.msessions, role: row.role, capo: row.capo });
async function requireMember(uid, teamId, role) {
  const m = await membership(uid, teamId);
  if (!m) throw forbidden('이 팀의 멤버가 아니에요');
  if (role === 'leader' && m.role !== 'leader') throw forbidden('인도자만 할 수 있어요');
  return m;
}
async function meView(uid) {
  const u = await one('select id, username, display_name from users where id=$1', [uid]);
  if (!u) throw noAuth();
  const rows = await q(`select t.*, m.user_id, m.name as mname, m.session, m.sessions as msessions, m.role, m.capo from members m join teams t on t.id=m.team_id
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

on('POST', '/auth/password', async ({ req, uid, body }) => {
  if (!uid) throw noAuth();
  const cur = String(body.current || ''), next = String(body.next || '');
  if (next.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  const u = await one('select password_hash from users where id=$1', [uid]);
  if (!verifyPassword(cur, u.password_hash)) throw new HttpError(401, 'bad_login', '현재 비밀번호가 맞지 않아요');
  // 다른 기기의 로그인은 끊고, 이 기기는 새 쿠키로 이어간다
  await q('update users set password_hash=$2, auth_epoch=to_timestamp($3) where id=$1', [uid, hashPassword(next), nowSec()]);
  return { data: { ok: true }, headers: { 'Set-Cookie': sessionCookie(req, uid) } };
});

on('GET', '/me', async ({ uid }) => { if (!uid) throw noAuth(); const r = await meView(uid); const u = await one('select recovery_hash is not null as has from users where id=$1', [uid]); r.user.hasRecovery = !!(u && u.has); return r; });

// 복구 코드 발급 (로그인 상태). 코드는 한 번만 보여주고 해시만 저장
on('POST', '/auth/recovery', async ({ uid }) => {
  if (!uid) throw noAuth();
  const alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'; const raw = randomToken(18); let code = '';
  for (let i = 0; i < 12; i++) { code += alphabet[raw.charCodeAt(i) % alphabet.length]; if (i === 3 || i === 7) code += '-'; }
  await q('update users set recovery_hash=$2 where id=$1', [uid, hashPassword(code)]);
  return { code };
});
// 복구 코드로 비밀번호 재설정 → 로그인. 코드는 폐기
on('POST', '/auth/recover', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), code = str(body.code, 20).toLowerCase().replace(/\s/g, ''), next = String(body.next || '');
  if (next.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  const u = await one('select id, recovery_hash from users where username=$1', [username]);
  if (!u || !u.recovery_hash || !verifyPassword(code, u.recovery_hash)) throw new HttpError(401, 'bad_recovery', '아이디 또는 복구 코드가 맞지 않아요');
  await q('update users set password_hash=$2, recovery_hash=null, last_login_at=now(), auth_epoch=to_timestamp($3) where id=$1', [u.id, hashPassword(next), nowSec()]);
  return { data: await meView(u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

// 내 이름·세션(팀 안에서) 바꾸기
on('PATCH', '/me', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const name = str(body.name, 40) || m.mname, session = pickSession(m, str(body.session, 40) || m.session);
  const capo = body.capo == null ? (+m.capo || 0) : Math.max(0, Math.min(9, Math.round(+body.capo) || 0));
  // 겸임 세션 (§3): 팀 세션 목록에 있는 것만, 대표 세션은 항상 포함
  const asked = strList(body.mySessions);
  const sessions = asked
    ? [...new Set([session, ...asked])].filter((s) => s && (m.sessions || []).includes(s))
    : mySessions(m);
  await q('update members set name=$3, session=$4, capo=$5, sessions=$6 where user_id=$1 and team_id=$2', [uid, teamId, name, session, capo, sessions]);
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
  const t = await one('select settings from teams where id=$1', [params.id]);
  return { ...viewOf(m), members, settings: { ...DEF_SETTINGS, ...(t && t.settings || {}) } };
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
  if (!['leader', 'session_lead', 'member', 'pastor'].includes(role)) throw bad('역할이 이상해요');
  if (params.userId === uid && role !== 'leader') {
    const n = await one('select count(*)::int as n from members where team_id=$1 and role=$2', [params.id, 'leader']);
    if (n.n <= 1) throw bad('인도자가 한 명뿐이라 역할을 내릴 수 없어요. 먼저 다른 사람을 인도자로 지정하세요');
  }
  // 목회자는 팀당 2명까지 (§0)
  if (role === 'pastor') {
    const n = await one(`select count(*)::int as n from members where team_id=$1 and role='pastor' and user_id<>$2`, [params.id, params.userId]);
    if (n.n >= 2) throw bad('목회자는 팀에 두 명까지예요');
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
  // 계정은 팀 밖의 전역 객체다. 다른 팀에도 속한 계정을 이 팀 인도자가 초기화하면 그 팀들의 자료까지 열리므로 막는다
  const elsewhere = await one('select count(*)::int as n from members where user_id=$1 and team_id<>$2', [params.userId, params.id]);
  if (elsewhere && elsewhere.n > 0) throw forbidden('이 멤버는 다른 팀에도 속해 있어 여기서 초기화할 수 없어요. 본인이 복구 코드로 바꾸게 해 주세요');
  const alphabet = 'abcdefghjkmnpqrstuvwxyz23456789';
  const bytes = randomToken(12); let pw = '';
  for (let i = 0; i < 8; i++) pw += alphabet[bytes.charCodeAt(i) % alphabet.length];
  // 비밀번호가 바뀌면 그 계정의 기존 로그인은 전부 끊는다 (auth_epoch 이전에 발급된 세션은 무효)
  await q('update users set password_hash=$2, auth_epoch=to_timestamp($3) where id=$1', [params.userId, hashPassword(pw), nowSec()]);
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
  const m = await membership(uid, teamId);
  if (m && m.role === 'leader') { try { await autoCreateServices(teamId); } catch (e) { console.error('autoCreate', e); } } // D-N주 날짜의 콘티 초안 자동 생성 (§2.2)
  const drafts = m && m.role === 'leader' ? await q('select id, updated_at as "updatedAt" from drafts where team_id=$1', [teamId]) : [];
  return { services: await q('select id, name, date, version, updated_at as "updatedAt" from services where team_id=$1 order by date desc', [teamId]), drafts };
});

// 발행본 하나 + 참조 파일 URL
on('GET', '/services/:id', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const wantDraft = url.searchParams.get('draft') === '1';
  const row = wantDraft
    ? await one('select doc, 0 as version, updated_at as "updatedAt" from drafts where team_id=$1 and id=$2', [teamId, params.id])
    : await one('select doc, version, updated_at as "updatedAt" from services where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) throw notFound(wantDraft ? '초안이 없어요' : '발행된 콘티가 없어요');
  const ids = blobIdsOf(row.doc);
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  const w = await one('select word, updated_at as "updatedAt" from service_words where team_id=$1 and service_id=$2', [teamId, params.id]);
  const rd = await one('select rev from service_reads where team_id=$1 and service_id=$2 and user_id=$3', [teamId, params.id, uid]);
  return { doc: row.doc, version: row.version, updatedAt: row.updatedAt, blobs: await readUrls(blobs), word: wordView(w && w.word, await membership(uid, teamId)), readRev: rd ? rd.rev : 0 };
});
// 말씀 (§4.1): 본문·제목·한 줄은 항상 전체 공개, 목회자 메모는 memoPublic 이 아니면 인도자에게만
function wordView(w, m) {
  if (!w || !(w.passage || w.title || w.line)) return null;
  const canSeeMemo = w.memoPublic || (m && (m.role === 'leader' || m.role === 'pastor'));
  return { passage: w.passage || '', title: w.title || '', line: w.line || '', memo: canSeeMemo ? (w.memo || '') : '', memoPublic: !!w.memoPublic, from: w.from || null, receivedAt: w.receivedAt || null, updatedAt: w.updatedAt || null };
}
const wordKey = (w) => w ? [w.passage, w.title, w.line, w.memo, w.memoPublic ? 1 : 0].map((x) => String(x == null ? '' : x)).join('') : '';

// 말씀 저장 (§4.2·§4.3): 인도자는 직접 입력, 목회자는 말씀 탭에서. 저장 즉시 전원에게 보인다
on('PUT', '/services/:id/word', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  if (m.role !== 'leader' && m.role !== 'pastor') throw forbidden('인도자와 목회자만 말씀을 적을 수 있어요');
  const b = body.word || {};
  const prev = await one('select word from service_words where team_id=$1 and service_id=$2', [teamId, params.id]);
  const word = {
    passage: str(b.passage, 60), title: str(b.title, 40), line: str(b.line, 80),
    memo: str(b.memo, 1000), memoPublic: !!b.memoPublic,
    from: { type: m.role === 'pastor' ? 'pastor' : 'leader', memberId: uid, name: m.mname || '' },
    receivedAt: (prev && prev.word && prev.word.receivedAt) || new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
  await q(`insert into service_words(team_id, service_id, word, updated_by, updated_at) values($1,$2,$3,$4,now())
           on conflict (team_id, service_id) do update set word=excluded.word, updated_by=excluded.updated_by, updated_at=now()`,
    [teamId, params.id, JSON.stringify(word), uid]);
  // §1 word.received: 목회자가 저장하면 인도자에게
  if (m.role === 'pastor' && wordKey(word) !== wordKey(prev && prev.word)) {
    try {
      const svc = await one('select name, date::text as date from services where team_id=$1 and id=$2', [teamId, params.id]);
      const leaders = (await q(`select user_id from members where team_id=$1 and role='leader'`, [teamId])).map((r) => r.user_id);
      const who = /[님사]$/.test(m.mname || '') ? m.mname : `${m.mname || '목사'}님`;
      await notify(teamId, leaders, 'word.received', params.id, { title: `${josa(who, '이', '가')} ${svc ? mdOf(svc.date) : ''} 말씀을 보냈어요`.replace(/\s+/g, ' '), body: [word.passage, word.title].filter(Boolean).join(' · '), link: '#/edit/' + params.id });
    } catch (e) { console.error('notify word.received', e); }
  }
  return { ok: true, word: wordView(word, m) };
});

// §4.5 예배 노트: 어디까지 읽었는지 (기기 + 서버)
on('POST', '/services/:id/read', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId);
  const rev = Math.max(0, Math.round(+body.rev || 0));
  await q(`insert into service_reads(team_id, service_id, user_id, rev, at) values($1,$2,$3,$4,now())
           on conflict (team_id, service_id, user_id) do update set rev=greatest(service_reads.rev, excluded.rev), at=now()`, [teamId, params.id, uid, rev]);
  return { ok: true };
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
  const cur = await one('select version, doc from services where team_id=$1 and id=$2', [teamId, params.id]);
  if (cur && cur.version >= (+doc.version || 0)) throw new HttpError(409, 'version_conflict', `다른 기기에서 v${cur.version}이 이미 발행됐어요. 새로고침으로 받은 뒤 다시 발행하세요`);
  await q(`insert into services(team_id, id, doc, version, name, date, updated_by, updated_at) values($1,$2,$3,$4,$5,$6,$7,now())
           on conflict (team_id, id) do update set doc=excluded.doc, version=excluded.version, name=excluded.name, date=excluded.date, updated_by=excluded.updated_by, updated_at=now()`,
    [teamId, params.id, JSON.stringify(doc), +doc.version || 0, str(doc.name, 120), str(doc.date, 20), uid]);
  // §1 알림: publish(팀 전원, 발행자 제외) · note.updated(인도자의 글이 이전 발행과 다를 때)
  try {
    const version = +doc.version || 0, md = mdOf(doc.date), name = str(doc.name, 60) || '예배';
    const label = name.startsWith(md) ? name : `${md} ${name}`; // 이름 규칙에 이미 날짜가 들어 있으면 겹쳐 쓰지 않음
    const titles = doc.items.map((it) => str(it && it.title, 40)).filter(Boolean);
    const body = titles.length ? (titles.length > 1 ? `${titles[0]} ~ ${titles[titles.length - 1]}` : titles[0]) : '곡 없음';
    const to = await teamUserIds(teamId, { except: uid });
    await notify(teamId, to, 'publish', params.id, { title: `${label} 콘티 v${version}`, body, link: '#/view/' + params.id });
    const prevMsg = cur && cur.doc ? String(cur.doc.message || '') : '';
    const prevWord = cur && cur.doc ? wordKey(cur.doc.word) : '';
    if (cur && (String(doc.message || '') !== prevMsg || wordKey(doc.word) !== prevWord) && (String(doc.message || '').trim() || wordKey(doc.word)))
      await notify(teamId, to, 'note.updated', params.id, { title: `${label} 인도자의 글이 바뀌었어요`, body: String(doc.message).split('\n')[0], link: '#/view/' + params.id });
    await linkDate(teamId, params.id, doc.date, name);
  } catch (e) { console.error('notify publish', e); }
  return { ok: true, version: +doc.version || 0 };
});

on('GET', '/services/:id/draft', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const row = await one('select doc, updated_at as "updatedAt" from drafts where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) return { doc: null };
  const ids = blobIdsOf(row.doc);
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return { doc: row.doc, updatedAt: row.updatedAt, blobs: await readUrls(blobs) };
});
on('PUT', '/services/:id/draft', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const doc = body.doc;
  if (!doc || !Array.isArray(doc.items)) throw bad('초안이 비어 있어요');
  await q(`insert into drafts(team_id, id, doc, updated_by, updated_at) values($1,$2,$3,$4,now())
           on conflict (team_id, id) do update set doc=excluded.doc, updated_by=excluded.updated_by, updated_at=now()`, [teamId, params.id, JSON.stringify(doc), uid]);
  try { await linkDate(teamId, params.id, doc.date, str(doc.name, 60)); } catch (e) { console.error('linkDate', e); }
  return { ok: true };
});

on('DELETE', '/services/:id', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const row = await one('select doc from services where team_id=$1 and id=$2', [teamId, params.id]);
  await q('delete from services where team_id=$1 and id=$2', [teamId, params.id]);
  await q('delete from drafts where team_id=$1 and id=$2', [teamId, params.id]);
  await q('delete from notes where team_id=$1 and service_id=$2', [teamId, params.id]);
  let freed = 0;
  if (row) {
    const mine = blobIdsOf(row.doc);
    if (mine.length) {
      const others = (await q('select doc from services where team_id=$1', [teamId])).concat(await q('select doc from drafts where team_id=$1', [teamId]));
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
  const force = url.searchParams.get('force') === '1';
  const existing = await one('select url, pathname from blobs where team_id=$1 and id=$2', [teamId, params.id]);
  if (existing && !force) return { url: existing.url, existed: true };
  if (existing) { try { await delBlobs([existing.url]); } catch (e) {} await q('delete from blobs where team_id=$1 and id=$2', [teamId, params.id]); }
  const buf = await readRaw(req);
  if (!buf.length) throw bad('빈 파일이에요');
  const type = str(req.headers['content-type'], 100) || 'application/octet-stream';
  const ext = type.includes('jpeg') ? '.jpg' : type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : type.startsWith('audio/') ? '.audio' : '';
  const up = await putBlob(`teams/${teamId}/${params.id}${ext}`, buf, type);
  await q('insert into blobs(team_id, id, url, pathname, type, size) values($1,$2,$3,$4,$5,$6) on conflict (team_id, id) do nothing', [teamId, params.id, up.url, up.pathname, type, buf.length]);
  return { url: up.url };
});

/* ---------- §5 합주 녹음 ---------- */
const ROLE_RANK = { member: 0, session_lead: 1, pastor: 0, leader: 2 };
const canUploadRehearsal = (m, st) => m.role !== 'pastor' && ROLE_RANK[m.role] >= ROLE_RANK[st.rehearsalUploadRole || 'member'];
const REHEARSAL_MAX = 150 * 1024 * 1024, REHEARSAL_KEEP_DAYS = 90;

// 브라우저가 Blob 으로 바로 올릴 서명 URL (서버리스 본문 한도 4.5MB 우회)
on('POST', '/rehearsals/upload-url', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const st = { ...DEF_SETTINGS, ...(m.settings || {}) };
  if (!canUploadRehearsal(m, st)) throw forbidden('녹음을 올릴 권한이 없어요');
  const size = Math.max(0, Math.round(+body.size || 0));
  if (size > REHEARSAL_MAX) throw new HttpError(413, 'too_large', '녹음은 150MB 이하만 올릴 수 있어요');
  const mime = /^audio\//.test(str(body.mime, 60)) ? str(body.mime, 60) : 'audio/mp4';
  const blobId = 'r' + randomToken(12).replace(/[^A-Za-z0-9]/g, '').slice(0, 16).toLowerCase();
  const ext = mime.includes('mp4') || mime.includes('m4a') ? '.m4a' : mime.includes('webm') ? '.webm' : mime.includes('mpeg') ? '.mp3' : '.audio';
  const pathname = `teams/${teamId}/rehearsals/${blobId}${ext}`;
  const p = await presignPut(pathname, mime, 30);
  return { blobId, pathname, uploadUrl: p.url, mime };
});

// 올린 뒤 등록 (파일이 실제로 있는지 확인하고 DB 에 기록)
on('POST', '/rehearsals', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const st = { ...DEF_SETTINGS, ...(m.settings || {}) };
  if (!canUploadRehearsal(m, st)) throw forbidden('녹음을 올릴 권한이 없어요');
  const serviceId = str(body.serviceId, 64); if (!serviceId) throw bad('어느 예배인지 알 수 없어요');
  const pathname = str(body.pathname, 300); const blobId = str(body.blobId, 64);
  if (!pathname.startsWith(`teams/${teamId}/rehearsals/`)) throw bad('경로가 이상해요');
  const h = await headBlob(pathname);
  if (!h) throw bad('파일이 올라오지 않았어요. 다시 시도해 주세요');
  if (h.size > REHEARSAL_MAX) { await delBlobs([h.url]); throw new HttpError(413, 'too_large', '녹음은 150MB 이하만 올릴 수 있어요'); }
  const date = /^\d{4}-\d{2}-\d{2}$/.test(str(body.date, 10)) ? str(body.date, 10) : new Date().toISOString().slice(0, 10);
  const label = str(body.label, 20) || `${mdOf(date)} 연습`;
  const expires = new Date(Date.now() + REHEARSAL_KEEP_DAYS * 86400000);
  await q('insert into blobs(team_id, id, url, pathname, type, size) values($1,$2,$3,$4,$5,$6) on conflict (team_id, id) do nothing',
    [teamId, blobId, h.url, h.pathname, h.contentType || 'audio/mp4', h.size]);
  const r = await one(`insert into rehearsals(team_id, service_id, date, label, blob_id, mime, duration, size_bytes, uploaded_by, expires_at)
                       values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) returning id, date::text as date, label, blob_id as "blobId", mime, duration, size_bytes as "sizeBytes", keep, expires_at as "expiresAt", created_at as "createdAt"`,
    [teamId, serviceId, date, label, blobId, h.contentType || 'audio/mp4', Math.max(0, Math.round(+body.duration || 0)), h.size, uid, expires]);
  // §1 rehearsal.uploaded: 편성된 사람, 없으면 전원
  try {
    const d = await one('select lineup from service_dates where team_id=$1 and service_id=$2', [teamId, serviceId]);
    let to = d ? [...new Set(cleanLineup(d.lineup).map((x) => x.memberId).filter(Boolean))] : [];
    if (!to.length) to = await teamUserIds(teamId, { exceptRole: 'pastor' });
    to = to.filter((x) => x !== uid);
    const mm = Math.floor((+body.duration || 0) / 60), ss = Math.round((+body.duration || 0) % 60);
    await notify(teamId, to, 'rehearsal.uploaded', r.id, { title: `${label} 녹음이 올라왔어요`, body: (+body.duration ? `${mm}:${String(ss).padStart(2, '0')}` : '') , link: '#/view/' + serviceId });
  } catch (e) { console.error('notify rehearsal', e); }
  return { ok: true, rehearsal: { ...r, uploadedBy: uid, uploaderName: m.mname } };
});

// 목록 (재생 URL 포함)
on('GET', '/rehearsals', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64), serviceId = str(url.searchParams.get('service'), 64);
  await requireMember(uid, teamId);
  const me0 = await membership(uid, teamId);
  const rows = (await q(`select r.id, r.date::text as date, r.label, r.blob_id as "blobId", r.mime, r.duration, r.size_bytes as "sizeBytes",
                               r.keep, r.expires_at as "expiresAt", r.created_at as "createdAt", r.uploaded_by as "uploadedBy", r.notes, m.name as "uploaderName"
                        from rehearsals r left join members m on m.team_id=r.team_id and m.user_id=r.uploaded_by
                        where r.team_id=$1 ${serviceId ? 'and r.service_id=$2' : ''} order by r.created_at desc`, serviceId ? [teamId, serviceId] : [teamId]))
    .map((r) => ({ ...r, notes: (Array.isArray(r.notes) ? r.notes : []).filter((n) => rehNoteVisible(n, me0)) }));
  const blobs = rows.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, rows.map((r) => r.blobId)]) : [];
  return { rehearsals: rows, urls: await readUrls(blobs) };
});

// 녹음 타임라인 메모: 범위(전체·세션·나만)에 따라 보이는 것만 내려준다
const rehNoteVisible = (n, m) => n.layer === 'leader' || m.role === 'leader' || (n.layer === 'session' && mySessions(m).includes(n.session)) || n.authorId === m.user_id;
on('POST', '/rehearsals/:id/notes', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const r = await one('select notes from rehearsals where id=$1 and team_id=$2', [params.id, teamId]);
  if (!r) throw notFound('녹음이 없어요');
  const b = body.note || {};
  const layer = ['leader', 'session', 'mine'].includes(str(b.layer, 10)) ? str(b.layer, 10) : 'mine';
  if (layer === 'leader' && m.role !== 'leader') throw forbidden('전체 메모는 인도자만 쓸 수 있어요');
  const n = { id: str(b.id, 40) || randomToken(8), t: Math.max(0, Math.round(+b.t || 0)), text: str(b.text, 60), layer,
    session: layer === 'session' ? str(b.session, 40) : null, itemId: str(b.itemId, 64) || null,
    authorId: uid, author: m.mname, createdAt: new Date().toISOString() };
  if (!n.text) throw bad('내용을 적어 주세요');
  const list = [...(Array.isArray(r.notes) ? r.notes : []).filter((x) => x.id !== n.id), n].slice(-300);
  await q('update rehearsals set notes=$2 where id=$1', [params.id, JSON.stringify(list)]);
  return { ok: true, note: n };
});
on('DELETE', '/rehearsals/:id/notes/:noteId', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const m = await requireMember(uid, teamId);
  const r = await one('select notes from rehearsals where id=$1 and team_id=$2', [params.id, teamId]);
  if (!r) throw notFound('녹음이 없어요');
  const list = (Array.isArray(r.notes) ? r.notes : []).filter((x) => !(x.id === params.noteId && (m.role === 'leader' || x.authorId === uid)));
  await q('update rehearsals set notes=$2 where id=$1', [params.id, JSON.stringify(list)]);
  return { ok: true };
});

// 이름 바꾸기 · 보관 잠금 (인도자)
on('PATCH', '/rehearsals/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const r = await one('select id, keep from rehearsals where id=$1 and team_id=$2', [params.id, teamId]);
  if (!r) throw notFound('녹음이 없어요');
  const label = body.label != null ? str(body.label, 20) : null;
  const keep = body.keep == null ? null : !!body.keep;
  await q(`update rehearsals set label=coalesce($3, label), keep=coalesce($4, keep),
           expires_at = case when $4 is null then expires_at when $4 then null else now() + interval '${REHEARSAL_KEEP_DAYS} days' end,
           warned_at = case when $4 then null else warned_at end
           where id=$1 and team_id=$2`, [params.id, teamId, label, keep]);
  return { ok: true };
});

on('DELETE', '/rehearsals/:id', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const r = await one('select blob_id as "blobId" from rehearsals where id=$1 and team_id=$2', [params.id, teamId]);
  if (!r) throw notFound('녹음이 없어요');
  await q('delete from rehearsals where id=$1 and team_id=$2', [params.id, teamId]);
  await dropBlobs(teamId, [r.blobId]);
  return { ok: true };
});
// blobs 행과 실제 파일을 같이 지운다 (다른 곳에서 안 쓰는 것만)
async function dropBlobs(teamId, ids) {
  if (!ids.length) return 0;
  const still = new Set((await q('select blob_id from rehearsals where team_id=$1 and blob_id = any($2::text[])', [teamId, ids])).map((r) => r.blob_id));
  const gone = ids.filter((x) => !still.has(x));
  if (!gone.length) return 0;
  const rows = await q('select url from blobs where team_id=$1 and id = any($2::text[])', [teamId, gone]);
  await q('delete from blobs where team_id=$1 and id = any($2::text[])', [teamId, gone]);
  await delBlobs(rows.map((r) => r.url));
  return gone.length;
}

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

// 채보 OMR (인도자): 악보 한 장 → 코드 차트(제목·키·박자·섹션·마디별 코드·가사). Gemini 키는 서버 환경변수에만 있고 클라이언트엔 내려가지 않음
on('GET', '/omr', async ({ uid }) => { if (!uid) throw noAuth(); return { available: geminiConfigured(), model: geminiConfigured() ? geminiModel() : null, mock: process.env.GEMINI_API_KEY === 'mock' }; });
on('POST', '/omr', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  if (!geminiConfigured()) throw new HttpError(503, 'no_omr', '채보 엔진이 아직 연결되지 않았어요 (GEMINI_API_KEY)');
  const b64 = String(body.b64 || '');
  const mime = /^image\/(jpeg|png|webp)$/.test(String(body.mime || '')) ? String(body.mime) : 'image/jpeg';
  if (b64.length < 100) throw bad('이미지가 비어 있어요');
  if (b64.length > 9e6) throw new HttpError(413, 'too_large', '이미지가 너무 커요 (6MB 이하)');
  let r;
  try { r = await transcribeSheet({ b64, mime }); }
  catch (e) {
    if (e.status === 429) throw new HttpError(429, 'omr_quota', '채보 한도에 걸렸어요. 잠시 뒤 다시 해 주세요');
    throw new HttpError(502, 'omr_failed', '채보 실패: ' + (e.message || ''));
  }
  return { songs: r.songs, model: r.model, usage: r.usage, cost: estimateUSD(r.model, r.usage) };
});

// 코드 OCR (인도자): 클라이언트가 자른 코드 띠 이미지들을 Vision 에 넘김
on('GET', '/ocr', async ({ uid }) => { if (!uid) throw noAuth(); return { available: visionConfigured(), mock: process.env.GOOGLE_VISION_KEY === 'mock' }; });
on('POST', '/ocr', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  if (!visionConfigured()) throw new HttpError(503, 'no_ocr', '코드 인식 엔진이 아직 연결되지 않았어요 (GOOGLE_VISION_KEY)');
  const images = (Array.isArray(body.images) ? body.images : []).slice(0, 16).map((im) => ({ b64: String(im.b64 || ''), mime: str(im.mime, 40), w: +im.w || 0, h: +im.h || 0, kind: str(im.kind, 10) })).filter((im) => im.b64.length > 100);
  if (!images.length) throw bad('이미지가 없어요');
  if (images.reduce((n, im) => n + im.b64.length, 0) > 12 * 1024 * 1024) throw new HttpError(413, 'too_large', '이미지가 너무 커요');
  const results = await ocrBands(images);
  return { results };
});

/* ---------- §2 정기 예배 · 사역 날짜 ---------- */
const DEF_SETTINGS = { serviceAutoCreateWeeks: 4, nameRule: '{월}/{일} {이름}', reminderDay: 25, wordRequestDay: 2, rehearsalUploadRole: 'member' };
const WD = ['일', '월', '화', '수', '목', '금', '토'];

// 알림 (§1): 알림함에 남기고, 같은 (type, targetId, user) 키가 24시간 안에 다시 오면 갱신만(읽음 상태 유지). actionable 이면 홈 카드에 뜸
async function notify(teamId, userIds, type, targetId, { title, body = '', link = '', actionable = false, expiresAt = null }) {
  for (const u of [...new Set(userIds)]) {
    await q(`insert into notifications(team_id, user_id, type, target_id, title, body, link, actionable, expires_at)
             values($1,$2,$3,$4,$5,$6,$7,$8,$9)
             on conflict (team_id, user_id, type, target_id) do update set
               title=excluded.title, body=excluded.body, link=excluded.link, actionable=excluded.actionable, expires_at=excluded.expires_at,
               read_at = case when notifications.updated_at > now() - interval '24 hours' then notifications.read_at else null end,
               acknowledged_at = case when excluded.type = 'lineup.changed' or notifications.updated_at <= now() - interval '24 hours' then null else notifications.acknowledged_at end,
               updated_at = now()`,
      [teamId, u, type, String(targetId || ''), str(title, 120), str(body, 300), str(link, 200), !!actionable, expiresAt]);
  }
}
// 콘티(발행본·초안)를 같은 날짜의 사역 날짜에 연결한다. 없으면 manual 날짜를 만든다 (§2.2)
async function linkDate(teamId, serviceId, date, label) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date || ''))) return;
  if (await one('select id from service_dates where team_id=$1 and service_id=$2', [teamId, serviceId])) return;
  const free = await one(`select id from service_dates where team_id=$1 and date=$2 and service_id is null order by (source='recurring') desc, created_at asc limit 1`, [teamId, date]);
  if (free) await q('update service_dates set service_id=$2 where id=$1', [free.id, serviceId]);
  else await q(`insert into service_dates(team_id, date, label, source, open, service_id) values($1,$2,$3,'manual',true,$4)
                on conflict (team_id, date, label) do update set service_id=coalesce(service_dates.service_id, excluded.service_id)`, [teamId, date, str(label, 40) || '예배', serviceId]);
}
// D-N주 안의 열린 날짜에 콘티가 없으면 초안을 자동 생성한다 (§2.2). 이름 = 팀 이름 규칙
async function autoCreateServices(teamId) {
  const t = await one('select settings from teams where id=$1', [teamId]);
  const st = { ...DEF_SETTINGS, ...(t && t.settings || {}) };
  const rows = await q(`select id, date::text as date, label from service_dates where team_id=$1 and open and service_id is null
                        and date >= current_date and date < current_date + ($2::int * interval '1 day') order by date`, [teamId, st.serviceAutoCreateWeeks * 7]);
  let n = 0;
  for (const r of rows) {
    const id = 'a' + randomToken(9).replace(/[^A-Za-z0-9]/g, '').slice(0, 10).toLowerCase();
    const doc = { id, name: fmtName(st.nameRule, r.date, r.label), date: r.date, notice: '', message: '', messageRev: 0, version: 0, editedAt: Date.now(), items: [], auto: true, dateId: r.id };
    await q('insert into drafts(team_id, id, doc, updated_at) values($1,$2,$3,now()) on conflict (team_id, id) do nothing', [teamId, id, JSON.stringify(doc)]);
    await q('update service_dates set service_id=$2 where id=$1', [r.id, id]);
    try { await fillDefaultLineup(teamId, r.id, r.date, st); } catch (e) { console.error('defaultLineup', e); }
    n++;
  }
  return n;
}
// §3.6 기본 편성 채우기: 그 날 '불가능'인 사람은 비운다. 이미 편성이 있으면 손대지 않는다
async function fillDefaultLineup(teamId, dateId, date, st) {
  const row = await one('select lineup from service_dates where id=$1', [dateId]);
  if (row && Array.isArray(row.lineup) && row.lineup.length) return 0;
  const def = (st && st.defaultLineup) || {};
  if (!Object.keys(def).length) return 0;
  const no = new Set((await q(`select user_id from availability where team_id=$1 and date=$2 and state='no'`, [teamId, date])).map((r) => r.user_id));
  const out = [];
  for (const [session, ids] of Object.entries(def)) for (const mid of (Array.isArray(ids) ? ids : [])) out.push({ session, memberId: no.has(mid) ? '' : mid, notifiedAt: null, acknowledgedAt: null });
  await q('update service_dates set lineup=$2 where id=$1', [dateId, JSON.stringify(out)]);
  return out.length;
}
function fmtName(rule, d, label) {
  const dt = new Date(d + 'T00:00:00');
  return String(rule || DEF_SETTINGS.nameRule)
    .replace(/\{월\}/g, dt.getMonth() + 1).replace(/\{일\}/g, dt.getDate())
    .replace(/\{요일\}/g, WD[dt.getDay()]).replace(/\{이름\}/g, label || '')
    .replace(/\s+/g, ' ').trim();
}
function isoDate(dt) { return dt.toISOString().slice(0, 10); }

// 정기 예배 하나가 앞으로 13주 안에 놓는 날짜들을 채운다 (빠진 것만 insert)
async function fillDates(teamId, rec, weeks = 13) {
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const end = new Date(start); end.setDate(end.getDate() + weeks * 7);
  const t = await one('select settings from teams where id=$1', [teamId]);
  const rule = (t && t.settings && t.settings.nameRule) || DEF_SETTINGS.nameRule;
  const d = new Date(start);
  d.setDate(d.getDate() + ((rec.weekday - d.getDay() + 7) % 7));
  for (; d < end; d.setDate(d.getDate() + 7)) {
    const iso = isoDate(d);
    await q(`insert into service_dates(team_id, date, label, time, source, recurring_id, open)
             values($1,$2,$3,$4,'recurring',$5,true) on conflict (team_id, date, label) do nothing`,
      [teamId, iso, rec.label, rec.time || null, rec.id]);
  }
}

on('GET', '/teams/:id/dates', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id);
  const rows = await q(`select id, date::text as date, label, time, source, recurring_id as "recurringId", open, service_id as "serviceId"
                        from service_dates where team_id=$1 and date >= (current_date - interval '1 day') order by date asc`, [params.id]);
  const rec = await q('select id, weekday, label, time, active from recurring where team_id=$1 order by weekday', [params.id]);
  return { dates: rows, recurring: rec };
});

on('POST', '/teams/:id/recurring', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const weekday = Math.max(0, Math.min(6, Math.round(+body.weekday)));
  const label = str(body.label, 40); if (!label) throw bad('이름을 적어 주세요');
  const time = /^\d{1,2}:\d{2}$/.test(String(body.time || '')) ? String(body.time) : null;
  const rec = await one('insert into recurring(team_id, weekday, label, time) values($1,$2,$3,$4) returning id, weekday, label, time, active', [params.id, weekday, label, time]);
  await fillDates(params.id, rec);
  try { await autoCreateServices(params.id); } catch (e) { console.error('autoCreate', e); }
  return { ok: true, recurring: rec };
});

on('PATCH', '/teams/:id/recurring/:rid', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const rec = await one('select * from recurring where id=$1 and team_id=$2', [params.rid, params.id]);
  if (!rec) throw notFound('정기 예배가 없어요');
  if (typeof body.active === 'boolean' && !body.active) {
    // 비활성: 미래의 콘티 없는 날짜 삭제, 콘티/답 있는 날짜는 닫기만
    await q(`delete from service_dates where team_id=$1 and recurring_id=$2 and date > current_date and service_id is null`, [params.id, params.rid]);
    await q(`update service_dates set open=false where team_id=$1 and recurring_id=$2 and date > current_date`, [params.id, params.rid]);
    await q('update recurring set active=false where id=$1', [params.rid]);
    return { ok: true };
  }
  const label = str(body.label, 40) || rec.label;
  const time = body.time == null ? rec.time : (/^\d{1,2}:\d{2}$/.test(String(body.time)) ? String(body.time) : null);
  await q('update recurring set label=$2, time=$3, active=true where id=$1', [params.rid, label, time]);
  const nrec = await one('select id, weekday, label, time, active from recurring where id=$1', [params.rid]);
  await fillDates(params.id, nrec);
  try { await autoCreateServices(params.id); } catch (e) { console.error('autoCreate', e); }
  return { ok: true, recurring: nrec };
});

on('DELETE', '/teams/:id/recurring/:rid', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  await q(`delete from service_dates where team_id=$1 and recurring_id=$2 and date > current_date and service_id is null`, [params.id, params.rid]);
  await q(`update service_dates set open=false, recurring_id=null where team_id=$1 and recurring_id=$2`, [params.id, params.rid]);
  await q('delete from recurring where id=$1 and team_id=$2', [params.rid, params.id]);
  return { ok: true };
});

// 인도자가 날짜 열기 (manual)
on('POST', '/teams/:id/dates', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const date = str(body.date, 10); if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw bad('날짜가 이상해요');
  const label = str(body.label, 40); if (!label) throw bad('이름을 적어 주세요');
  const time = /^\d{1,2}:\d{2}$/.test(String(body.time || '')) ? String(body.time) : null;
  const row = await one(`insert into service_dates(team_id, date, label, time, source, open) values($1,$2,$3,$4,'manual',true)
                         on conflict (team_id, date, label) do update set open=true returning id, date::text as date, label, time, open`, [params.id, date, label, time]);
  // §1 date.opened: 팀 전원(목회자 제외), 홈 카드. 그 날이 지나면 카드는 사라짐
  try {
    const to = await teamUserIds(params.id, { exceptRole: 'pastor', except: uid });
    await notify(params.id, to, 'date.opened', row.id, { title: `${mdOf(row.date)} ${row.label} 일정이 열렸어요`, body: row.time ? `${row.time} · 참여 가능한지 알려주세요` : '참여 가능한지 알려주세요', link: '#/home', actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00') });
  } catch (e) { console.error('notify date.opened', e); }
  return { ok: true, date: row };
});

// 날짜 열기·닫기
on('PATCH', '/teams/:id/dates/:did', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const row = await one('select * from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  if (typeof body.open === 'boolean') {
    if (!body.open && row.service_id) throw bad('콘티가 있는 날짜는 닫을 수 없어요. 먼저 콘티를 삭제하세요');
    await q('update service_dates set open=$2 where id=$1', [params.did, body.open]);
    if (body.open !== !!row.open) { // §1 date.opened / date.closed
      try {
        const md = mdOf(row.date instanceof Date ? row.date.toISOString().slice(0, 10) : String(row.date));
        if (body.open) await notify(params.id, await teamUserIds(params.id, { exceptRole: 'pastor', except: uid }), 'date.opened', row.id, { title: `${md} ${row.label} 일정이 열렸어요`, body: row.time ? `${row.time} · 참여 가능한지 알려주세요` : '참여 가능한지 알려주세요', link: '#/home', actionable: true, expiresAt: new Date(String(row.date).slice(0, 10) + 'T23:59:59+09:00') });
        else await notify(params.id, await teamUserIds(params.id, { except: uid }), 'date.closed', row.id, { title: `${md} ${row.label}는 이번 주 쉽니다`, body: '', link: '#/home' });
      } catch (e) { console.error('notify date', e); }
    }
  }
  if (body.label != null || body.time != null) {
    await q('update service_dates set label=coalesce(nullif($2,\'\'),label), time=$3 where id=$1',
      [params.did, str(body.label, 40), /^\d{1,2}:\d{2}$/.test(String(body.time || '')) ? String(body.time) : row.time]);
  }
  return { ok: true };
});

// 팀 설정 읽기/쓰기
on('PATCH', '/teams/:id/settings', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const cur = (await one('select settings from teams where id=$1', [params.id])).settings || {};
  const next = { ...DEF_SETTINGS, ...cur };
  if (body.serviceAutoCreateWeeks != null) next.serviceAutoCreateWeeks = Math.max(1, Math.min(8, Math.round(+body.serviceAutoCreateWeeks)));
  if (body.nameRule != null) next.nameRule = str(body.nameRule, 60);
  if (body.reminderDay != null) next.reminderDay = Math.max(20, Math.min(28, Math.round(+body.reminderDay)));
  if (body.wordRequestDay != null) next.wordRequestDay = Math.max(0, Math.min(6, Math.round(+body.wordRequestDay)));
  if (body.rehearsalUploadRole != null && ['member', 'session_lead', 'leader'].includes(body.rehearsalUploadRole)) next.rehearsalUploadRole = body.rehearsalUploadRole;
  // §3.6 세션 정원 · 기본 편성
  const team = await one('select sessions from teams where id=$1', [params.id]);
  const list = team.sessions || [];
  if (body.slots && typeof body.slots === 'object') { const s = {}; for (const k of list) if (body.slots[k] != null) s[k] = Math.max(0, Math.min(9, Math.round(+body.slots[k]) || 0)); next.slots = { ...(next.slots || {}), ...s }; }
  if (body.defaultLineup && typeof body.defaultLineup === 'object') { const d = {}; for (const k of list) if (Array.isArray(body.defaultLineup[k])) d[k] = body.defaultLineup[k].map((x) => str(x, 64)).slice(0, 9); next.defaultLineup = { ...(next.defaultLineup || {}), ...d }; }
  await q('update teams set settings=$2 where id=$1', [params.id, JSON.stringify(next)]);
  return { ok: true, settings: next };
});

// 매일 03:00 크론: 13주 앞 유지
/* ---------- §3 편성 스케줄링 ---------- */
const AV = ['ok', 'maybe', 'no'];
const teamMembers = (teamId) => q(`select user_id as "userId", name, session, sessions as msessions, role from members where team_id=$1 order by created_at asc`, [teamId]);
const memberSessions = (m) => (Array.isArray(m.msessions) && m.msessions.length ? m.msessions : (m.session ? [m.session] : []));
const cleanLineup = (v, teamSessions) => (Array.isArray(v) ? v : []).slice(0, 60)
  .map((r) => ({ session: str(r && r.session, 40), memberId: str(r && r.memberId, 64), notifiedAt: r && r.notifiedAt ? String(r.notifiedAt) : null, acknowledgedAt: r && r.acknowledgedAt ? String(r.acknowledgedAt) : null }))
  .filter((r) => r.session && (!teamSessions || teamSessions.includes(r.session)));
const lineupKey = (l) => (l || []).map((r) => r.session + ':' + r.memberId).sort().join(',');

// 달력·표에 필요한 것을 한 번에: 사역 날짜(편성 포함) + 가능 여부(인도자는 전원, 멤버는 자기 것) + 멤버 목록
on('GET', '/teams/:id/schedule', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const from = /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get('from') || '') ? url.searchParams.get('from') : null;
  const to = /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get('to') || '') ? url.searchParams.get('to') : null;
  const range = from && to ? 'and date between $2 and $3' : "and date >= current_date - interval '1 month'";
  const args = from && to ? [params.id, from, to] : [params.id];
  const dates = await q(`select id, date::text as date, label, time, source, open, service_id as "serviceId", lineup
                         from service_dates where team_id=$1 ${range} order by date asc`, args);
  const av = m.role === 'leader'
    ? await q(`select user_id as "userId", date::text as date, state, memo from availability where team_id=$1 ${range}`, args)
    : await q(`select user_id as "userId", date::text as date, state, memo from availability where team_id=$1 and user_id=$${args.length + 1} ${range}`, [...args, uid]);
  return { dates, availability: av, members: await teamMembers(params.id), role: m.role };
});

// 가능 여부: 탭 한 번에 저장. 'unset'이면 행을 지운다
on('PUT', '/teams/:id/availability', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  if (m.role === 'pastor') throw forbidden('목회자는 편성에 들어가지 않아요');
  const date = str(body.date, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw bad('날짜가 이상해요');
  const state = str(body.state, 10), memo = str(body.memo, 40);
  if (state === 'unset' || !state) { await q('delete from availability where team_id=$1 and user_id=$2 and date=$3', [params.id, uid, date]); return { ok: true, state: 'unset' }; }
  if (!AV.includes(state)) throw bad('상태가 이상해요');
  await q(`insert into availability(team_id, user_id, date, state, memo) values($1,$2,$3,$4,$5)
           on conflict (team_id, user_id, date) do update set state=excluded.state, memo=excluded.memo, updated_at=now()`, [params.id, uid, date, state, memo]);
  // §1 avail.conflict: 편성된 날을 불가능으로 바꾸면 인도자에게
  if (state === 'no') {
    try {
      const d = await one('select id, date::text as date, label, lineup from service_dates where team_id=$1 and date=$2 and open order by created_at asc limit 1', [params.id, date]);
      const mine = d && cleanLineup(d.lineup).filter((r) => r.memberId === uid);
      if (mine && mine.length) {
        const leaders = (await q(`select user_id from members where team_id=$1 and role='leader'`, [params.id])).map((r) => r.user_id);
        await notify(params.id, leaders, 'avail.conflict', d.id + ':' + uid, {
          title: `${josa(m.mname, '이', '가')} ${josa(mdOf(date), '을', '를')} 불가능으로 바꿨어요`, body: [memo ? `"${memo}"` : '', `${mine.map((r) => r.session).join('·')}으로 편성돼 있음`].filter(Boolean).join(' · '),
          link: '#/lineup/' + d.id, actionable: true, expiresAt: new Date(date + 'T23:59:59+09:00'),
        });
      }
    } catch (e) { console.error('notify avail.conflict', e); }
  }
  return { ok: true, state, memo };
});

// 그날 편성 저장 (인도자)
on('PUT', '/teams/:id/dates/:did/lineup', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id, 'leader');
  const row = await one('select id, lineup from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  const prev = cleanLineup(row.lineup);
  const next = cleanLineup(body.lineup, m.sessions || null).map((r) => {
    const old = prev.find((p) => p.session === r.session && p.memberId === r.memberId);
    return { ...r, notifiedAt: old ? old.notifiedAt : null, acknowledgedAt: old ? old.acknowledgedAt : null };
  });
  await q('update service_dates set lineup=$2 where id=$1', [params.did, JSON.stringify(next)]);
  return { ok: true, lineup: next, changed: lineupKey(prev) !== lineupKey(next) };
});

// 통보하기 / 변경 통보 (§3.4)
on('POST', '/teams/:id/dates/:did/notify', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const row = await one('select id, date::text as date, label, time, lineup, service_id as "serviceId" from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  const lineup = cleanLineup(row.lineup);
  const md = mdOf(row.date), where = `${md} ${row.label}`;
  const link = row.serviceId ? '#/view/' + row.serviceId : '#/home';
  const now = new Date().toISOString();
  const firstTime = !lineup.some((r) => r.notifiedAt);
  const already = new Set(lineup.filter((r) => r.notifiedAt).map((r) => r.memberId));
  const nowIn = new Set(lineup.map((r) => r.memberId).filter(Boolean));
  const added = [...nowIn].filter((x) => !already.has(x));
  const dropped = [...already].filter((x) => !nowIn.has(x));
  const sessionsOf = (mid) => lineup.filter((r) => r.memberId === mid).map((r) => r.session).join('·');
  const timeLine = row.time ? `${row.time} 시작` : '';
  let sent = 0;
  for (const mid of (firstTime ? [...nowIn] : added)) {
    await notify(params.id, [mid], firstTime ? 'lineup.notify' : 'lineup.changed', row.id, {
      title: `${where} · ${josa(sessionsOf(mid), '으로', '로')} 섭니다`, body: timeLine, link, actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00'),
    });
    sent++;
  }
  for (const mid of dropped) {
    await notify(params.id, [mid], 'lineup.changed', row.id, { title: `${md} 편성에서 빠졌어요`, body: row.label, link: '#/home', actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00') });
    sent++;
  }
  await q('update service_dates set lineup=$2 where id=$1', [params.did, JSON.stringify(lineup.map((r) => ({ ...r, notifiedAt: r.notifiedAt || now })))]);
  return { ok: true, sent, added: added.length, dropped: dropped.length, firstTime };
});

// 카톡용 편성 문구
on('GET', '/teams/:id/dates/:did/text', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const row = await one('select date::text as date, label, time, lineup from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  const ms = await teamMembers(params.id);
  const nameOf = (id) => (ms.find((x) => x.userId === id) || {}).name || '';
  const byS = {};
  for (const r of cleanLineup(row.lineup)) if (r.memberId) (byS[r.session] || (byS[r.session] = [])).push(nameOf(r.memberId));
  const lines = [`[${mdOf(row.date)} ${row.label}${row.time ? ' ' + row.time : ''} 편성]`, ...Object.entries(byS).map(([s, n]) => `${s} ${n.join(', ')}`)];
  return { text: lines.join('\n') };
});

// §1 알림함: 내 알림 목록(90일), 읽음, 처리(actionable 카드 닫기)
on('GET', '/notifications', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const rows = await q(`select id, type, target_id as "targetId", title, body, link, actionable, read_at as "readAt", acknowledged_at as "ackAt", expires_at as "expiresAt", updated_at as "at"
                        from notifications where team_id=$1 and user_id=$2 and updated_at > now() - interval '90 days' order by updated_at desc limit 100`, [teamId, uid]);
  return { notifications: rows, unread: rows.filter((r) => !r.readAt).length };
});
// §3.3 "다시 요청": 미선택이 많은 멤버에게 가능 여부를 다시 묻는다 (24시간 1회)
on('POST', '/notifications/ask', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const target = str(body.userId, 64);
  if (!(await one('select 1 from members where team_id=$1 and user_id=$2', [teamId, target]))) throw notFound('그 멤버가 없어요');
  const month = /^\d{4}-\d{2}$/.test(str(body.month, 7)) ? str(body.month, 7) : new Date().toISOString().slice(0, 7);
  const recent = await one(`select 1 from notifications where team_id=$1 and user_id=$2 and type='avail.request' and target_id=$3 and updated_at > now() - interval '24 hours'`, [teamId, target, month]);
  if (recent) throw bad('이미 24시간 안에 요청했어요');
  const [y, mo] = month.split('-').map(Number);
  const from = `${month}-01`, to = new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
  const dates = await q('select date::text as date from service_dates where team_id=$1 and open and date between $2 and $3', [teamId, from, to]);
  const answered = await one('select count(*)::int as n from availability where team_id=$1 and user_id=$2 and date between $3 and $4', [teamId, target, from, to]);
  await notify(teamId, [target], 'avail.request', month, { title: `${mo}월 스케줄 알려주세요`, body: `사역일 ${dates.length}일 · 아직 미선택 ${Math.max(0, dates.length - (answered ? answered.n : 0))}일`, link: '#/cal/' + month, actionable: true, expiresAt: new Date(to + 'T23:59:59+09:00') });
  return { ok: true };
});

on('POST', '/notifications/read', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId);
  const ids = Array.isArray(body.ids) ? body.ids.map((x) => str(x, 64)).filter(Boolean) : [];
  const r = body.all
    ? await q('update notifications set read_at=now() where team_id=$1 and user_id=$2 and read_at is null returning id', [teamId, uid])
    : await q('update notifications set read_at=coalesce(read_at, now()) where team_id=$1 and user_id=$2 and id::text = any($3::text[]) returning id', [teamId, uid, ids]);
  return { ok: true, read: r.length };
});
on('POST', '/notifications/:id/ack', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId);
  const r = await q('update notifications set acknowledged_at=now(), read_at=coalesce(read_at, now()) where team_id=$1 and user_id=$2 and id::text=$3 returning id', [teamId, uid, str(params.id, 64)]);
  if (!r.length) throw notFound('알림이 없어요');
  return { ok: true };
});

// §1 avail.request (매월 reminderDay) · avail.maybe (보류 D-14) · word.request (매주 wordRequestDay)
async function scheduleReminders(teamId, st) {
  const now = new Date(Date.now() + 9 * 3600 * 1000); // KST 기준 날짜·요일
  const day = now.getUTCDate(), dow = now.getUTCDay();
  let asked = 0, maybes = 0;
  // 다음 달 사역일 가능 여부 요청
  if (day === (+st.reminderDay || 25)) {
    const y = now.getUTCFullYear(), mo = now.getUTCMonth();
    const from = new Date(Date.UTC(y, mo + 1, 1)).toISOString().slice(0, 10);
    const to = new Date(Date.UTC(y, mo + 2, 0)).toISOString().slice(0, 10);
    const dates = await q('select date::text as date from service_dates where team_id=$1 and open and date between $2 and $3', [teamId, from, to]);
    if (dates.length) {
      const members = (await q(`select user_id from members where team_id=$1 and role<>'pastor'`, [teamId])).map((r) => r.user_id);
      const answered = await q('select user_id, count(*)::int as n from availability where team_id=$1 and date between $2 and $3 group by user_id', [teamId, from, to]);
      const cnt = Object.fromEntries(answered.map((r) => [r.user_id, r.n]));
      const label = `${new Date(from + 'T00:00:00Z').getUTCMonth() + 1}월`;
      for (const mid of members) {
        const left = dates.length - (cnt[mid] || 0);
        if (left <= 0) continue;
        await notify(teamId, [mid], 'avail.request', from.slice(0, 7), { title: `${label} 스케줄 알려주세요`, body: `사역일 ${dates.length}일 · 아직 미선택 ${left}일`, link: '#/cal/' + from.slice(0, 7), actionable: true, expiresAt: new Date(to + 'T23:59:59+09:00') });
        asked++;
      }
    }
  }
  // 보류(maybe)인 날짜가 2주 앞으로 다가오면 그 사람에게만
  const d14 = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 14)).toISOString().slice(0, 10);
  for (const r of await q(`select a.user_id, a.date::text as date, sd.label from availability a
                           join service_dates sd on sd.team_id=a.team_id and sd.date=a.date and sd.open
                           where a.team_id=$1 and a.state='maybe' and a.date=$2`, [teamId, d14])) {
    await notify(teamId, [r.user_id], 'avail.maybe', r.date, { title: `${mdOf(r.date)} 아직 보류예요. 정해졌나요?`, body: `${r.label} · D-14`, link: '#/cal/' + r.date.slice(0, 7), actionable: true, expiresAt: new Date(r.date + 'T23:59:59+09:00') });
    maybes++;
  }
  // 그 주 예배 중 말씀 미입력이 있으면 목회자에게
  if (dow === (st.wordRequestDay == null ? 2 : +st.wordRequestDay)) {
    const pastors = (await q(`select user_id from members where team_id=$1 and role='pastor'`, [teamId])).map((r) => r.user_id);
    if (pastors.length) {
      const upto = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 7)).toISOString().slice(0, 10);
      const need = await q(`select sd.date::text as date, sd.label from service_dates sd
                            left join service_words w on w.team_id=sd.team_id and w.service_id=sd.service_id
                            where sd.team_id=$1 and sd.open and sd.date between current_date and $2 and (w.word is null or w.word->>'passage' is null or w.word->>'passage'='')`, [teamId, upto]);
      if (need.length) await notify(teamId, pastors, 'word.request', upto, { title: '이번 주 말씀 알려주세요', body: need.map((r) => `${mdOf(r.date)} ${r.label}`).join(', '), link: '#/word', actionable: true, expiresAt: new Date(upto + 'T23:59:59+09:00') });
    }
  }
  return { asked, maybes };
}

on('GET', '/cron/dates', async ({ req }) => {
  // Vercel 크론은 CRON_SECRET 이 설정돼 있으면 Authorization: Bearer <secret> 를 붙여 부른다. 미설정이면 아예 막는다 (위조 가능한 헤더로는 통과 불가)
  if (!process.env.CRON_SECRET || req.headers['authorization'] !== `Bearer ${process.env.CRON_SECRET}`) throw forbidden('크론 전용');
  const recs = await q('select * from recurring where active=true');
  let n = 0;
  for (const rec of recs) { await fillDates(rec.team_id, rec); n++; }
  // D-N주 콘티 자동 생성 (모든 팀) + 월간 스케줄 요청 + 보류 D-14 확인 + 90일 지난 알림 정리
  let created = 0, asked = 0, maybes = 0;
  for (const t of await q('select id, settings from teams')) {
    try { created += await autoCreateServices(t.id); } catch (e) { console.error('autoCreate', t.id, e); }
    try { const r = await scheduleReminders(t.id, { ...DEF_SETTINGS, ...(t.settings || {}) }); asked += r.asked; maybes += r.maybes; } catch (e) { console.error('reminders', t.id, e); }
  }
  const purged = (await q(`delete from notifications where updated_at < now() - interval '90 days' returning id`)).length;
  // §5.4 녹음 보관: 만료 7일 전 인도자에게 알림함 항목, 지난 것은 파일까지 삭제
  let warned = 0, dropped = 0;
  for (const r of await q(`select id, team_id, service_id, label, date::text as date, expires_at from rehearsals
                           where keep=false and warned_at is null and expires_at is not null and expires_at < now() + interval '7 days'`)) {
    const leaders = (await q(`select user_id from members where team_id=$1 and role='leader'`, [r.team_id])).map((x) => x.user_id);
    await notify(r.team_id, leaders, 'rehearsal.expiring', r.id, { title: `${r.label} 녹음이 7일 뒤 삭제돼요`, body: '보관하려면 잠금', link: '#/view/' + r.service_id });
    await q('update rehearsals set warned_at=now() where id=$1', [r.id]);
    warned++;
  }
  for (const r of await q(`select id, team_id, blob_id from rehearsals where keep=false and expires_at is not null and expires_at < now()`)) {
    await q('delete from rehearsals where id=$1', [r.id]);
    await dropBlobs(r.team_id, [r.blob_id]);
    dropped++;
  }
  return { ok: true, recurring: n, created, asked, maybes, purged, warned, dropped };
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
    const body = (method === 'GET' || /^\/blobs\//.test(path)) ? {} : await readBody(req, /^\/(ocr|omr)$/.test(path) ? 12e6 : 1e6); // 이미지 base64 를 실어 보내는 경로만 크게
    // 세션: 서명·만료 검사 후, 비밀번호 변경(auth_epoch) 이전에 발급된 토큰은 무효 처리
    let uid = null; const claims = sessionClaims(req);
    if (claims) {
      const ep = await one('select extract(epoch from auth_epoch)::bigint as e from users where id=$1', [claims.uid]);
      if (ep && (ep.e == null || (claims.iat && claims.iat >= Number(ep.e)))) uid = claims.uid;
    }
    const out = await route.fn({ req, uid, params, body, url });
    if (out && out.headers && 'data' in out) return send(res, 200, out.data, out.headers);
    return send(res, 200, out);
  } catch (e) {
    if (e instanceof HttpError) return send(res, e.status, { error: e.code, message: e.message });
    console.error(e);
    return send(res, 500, { error: 'server', message: '서버 오류가 났어요' });
  }
}
