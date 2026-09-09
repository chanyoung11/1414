// 콘티 API — 계정 · 팀 · 초대. Vercel 서버리스 함수 하나(api/index.js)에 작은 라우터.
// vercel.json 의 rewrite 가 /api/* 를 /api?p=<경로> 로 보내고, 여기서 p(또는 원래 pathname)로 라우팅합니다.
// 로컬: npm run dev (scripts/dev.mjs가 이 핸들러를 /api/* 에 그대로 붙임)
import { q, one } from '../lib/db.js';
import { sessionClaims, sessionCookie, clearSessionCookie, randomToken } from '../lib/session.js';
import { hashPassword, verifyPassword, USERNAME_RE, PASSWORD_MIN } from '../lib/password.js';
import { putBlob, delBlobs, readUrls, presignPut, headBlob } from '../lib/blob.js';
import { ocrBands, visionConfigured } from '../lib/vision.js';
import { transcribeSheet, transcribeScore, geminiConfigured, geminiModel, estimateUSD } from '../lib/gemini.js';
import { norm as normSong, cho as choSong } from '../lib/song.js';

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
  plan: t.plan || 'free',
  billingUserId: t.billing_user_id || t.created_by,
  deletedAt: t.deleted_at || null,
  me: { userId: m.user_id, name: m.name, session: m.session, mySessions: mySessions(m), role: m.role, capo: +m.capo || 0, active: m.active !== false },
});
const teamUserIds = async (teamId, { exceptRole, except } = {}) =>
  (await q('select user_id, role from members where team_id=$1 and active', [teamId]))
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
  return one(`select t.*, m.user_id, m.name as mname, m.session, m.sessions as msessions, m.role, m.capo, m.active from members m join teams t on t.id=m.team_id
              where m.user_id=$1 ${teamId ? 'and m.team_id=$2' : ''} order by m.active desc, m.created_at asc limit 1`, teamId ? [uid, teamId] : [uid]);
}
const viewOf = (row) => row && memberView(row, { user_id: row.user_id, name: row.mname, session: row.session, msessions: row.msessions, role: row.role, capo: row.capo });
// 관리 동작만 남긴다 (누가 인도자를 넘겼는지, 누구를 비활성으로 뒀는지)
async function audit(teamId, actorId, action, target, meta) {
  try { await q('insert into team_audit(team_id, actor_id, action, target, meta) values($1,$2,$3,$4,$5)',
    [teamId, actorId, action, target ? String(target) : null, JSON.stringify(meta || {})]); }
  catch (e) { console.error('audit', e.message); }
}
async function requireMember(uid, teamId, role) {
  const m = await membership(uid, teamId);
  if (!m) throw forbidden('이 팀의 멤버가 아니에요');
  if (m.active === false) throw forbidden('이 팀에서 비활성 상태예요. 인도자에게 문의해 주세요');
  if (role === 'leader' && m.role !== 'leader') throw forbidden('인도자만 할 수 있어요');
  return m;
}
async function meView(uid) {
  const u = await one('select id, username, display_name from users where id=$1', [uid]);
  if (!u) throw noAuth();
  q(`update members set last_seen_at=now() where user_id=$1 and (last_seen_at is null or last_seen_at < now() - interval '1 hour')`, [uid]).catch(() => {});
  const rows = await q(`select t.*, m.user_id, m.name as mname, m.session, m.sessions as msessions, m.role, m.capo, m.active from members m join teams t on t.id=m.team_id
                        where m.user_id=$1 order by m.active desc, m.created_at asc`, [uid]);
  // 비활성인 팀은 목록에 넣지 않는다. 다만 그 팀뿐이면 왜 안 보이는지 알려 준다 (B.4.3)
  const live = rows.filter((r) => r.active !== false);
  const out = { user: { id: u.id, username: u.username, name: u.display_name }, team: live[0] ? viewOf(live[0]) : null, teams: live.map(viewOf) };
  if (!live.length && rows.length) out.blocked = { teamName: rows[0].name };
  return out;
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

// 계정 삭제 (§7): 아이디·비밀번호로 두 번 확인. 인도자로 남아 있는 팀이 있으면 먼저 넘기게 한다
on('POST', '/auth/delete', async ({ req, uid, body }) => {
  if (!uid) throw noAuth();
  const u = await one('select id, username, password_hash from users where id=$1', [uid]);
  if (!u) throw noAuth();
  if (str(body.username, 40).toLowerCase() !== u.username) throw bad('아이디가 맞지 않아요');
  if (!verifyPassword(String(body.password || ''), u.password_hash)) throw new HttpError(401, 'bad_login', '비밀번호가 맞지 않아요');
  const stuck = await q(`select t.name from members m join teams t on t.id=m.team_id
                         where m.user_id=$1 and m.role='leader'
                           and (select count(*) from members m2 where m2.team_id=m.team_id and m2.role='leader') = 1
                           and (select count(*) from members m3 where m3.team_id=m.team_id) > 1`, [uid]);
  if (stuck.length) throw bad(`${stuck.map((r) => r.name).join(', ')} 팀의 인도자예요. 다른 사람을 인도자로 지정한 뒤 다시 시도해 주세요`);
  // '누가 했는지'만 가리키는 칸을 먼저 비운다 (지운 계정을 참조하면 삭제가 막히므로)
  for (const [t, c] of [['services', 'updated_by'], ['drafts', 'updated_by'], ['service_words', 'updated_by'], ['rehearsals', 'uploaded_by'], ['word_links', 'created_by'], ['library', 'updated_by']]) {
    try { await q(`update ${t} set ${c}=null where ${c}=$1`, [uid]); } catch (e) { console.error('null out', t, e.message); }
  }
  // 팀을 만든 사람 칸은 not null 이라 비울 수 없다 → 남은 인도자(없으면 가장 오래된 멤버)에게 넘긴다
  for (const t of await q('select id from teams where created_by=$1', [uid])) {
    const heir = await one(`select user_id from members where team_id=$1 and user_id<>$2 order by (role='leader') desc, created_at asc limit 1`, [t.id, uid]);
    if (heir) await q('update teams set created_by=$2 where id=$1', [t.id, heir.user_id]);
  }
  await q('delete from notes where author_id=$1', [uid]);
  // 혼자 있는 팀은 팀째로 지운다. 파일 삭제는 계정이 실제로 지워진 뒤에 (중간에 실패해도 파일이 남도록)
  const solo = await q(`select m.team_id from members m where m.user_id=$1 and (select count(*) from members m2 where m2.team_id=m.team_id) = 1`, [uid]);
  const soloUrls = [];
  for (const t of solo) {
    for (const r of await q('select url from blobs where team_id=$1', [t.team_id])) soloUrls.push(r.url);
    await q('delete from teams where id=$1', [t.team_id]);
  }
  await q('delete from users where id=$1', [uid]);
  await delBlobs(soloUrls);
  return { data: { ok: true }, headers: { 'Set-Cookie': clearSessionCookie(req) } };
});

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
  const owned = await one(`select count(*)::int as n from teams where created_by=$1 and deleted_at is null`, [uid]);
  if (ENFORCE_PLAN && owned.n >= PLAN.free.teamsOwned) throw new HttpError(402, 'plan_limit', `무료로는 팀을 ${PLAN.free.teamsOwned}개까지 만들 수 있어요`);
  const t = await one('insert into teams(name, invite_token, created_by) values($1,$2,$3) returning *', [name, randomToken(12), uid]);
  const session = pickSession(t, str(body.session, 40) || '인도자');
  await q('insert into members(user_id, team_id, name, session, sessions, role) values($1,$2,$3,$4,$5,$6)', [uid, t.id, myName, session, [session], 'leader']);
  // 만들자마자 쓸 수 있는 기본 초대 링크 하나 (역할 멤버·만료 없음·무제한)
  await q('insert into invites(team_id, code, role, created_by) values($1,$2,$3,$4)', [t.id, t.invite_token, 'member', uid]);
  return viewOf(await membership(uid, t.id));
});

on('GET', '/teams/:id', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const members = await q(`select user_id as "userId", name, session, sessions as "mySessions", role, active,
      created_at as "joinedAt", last_seen_at as "lastSeenAt" from members where team_id=$1 order by created_at asc`, [params.id]);
  const t = await one('select settings from teams where id=$1', [params.id]);
  return { ...viewOf(m), members, settings: { ...DEF_SETTINGS, ...(t && t.settings || {}) } };
});

on('PATCH', '/teams/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const name = str(body.name, 30), sessions = strList(body.sessions), phrases = strList(body.phrases);
  if (sessions && !sessions.length) throw bad('세션은 하나 이상 있어야 해요');
  if (sessions && new Set(sessions).size !== sessions.length) throw bad('같은 이름의 세션이 두 개예요');
  if (sessions) { const t0 = await one('select plan from teams where id=$1', [params.id]);
    checkLimit(t0, 'sessions', sessions.length - 1, (cap) => `세션은 ${cap}개까지예요`); }
  // B.5.2 세션 이름을 바꾸면 멤버·정원·기본 편성·앞으로의 편성·메모가 함께 따라간다. 발행본은 그대로
  const rename = body.rename && typeof body.rename === 'object' ? body.rename : null;
  if (rename) await renameSessions(params.id, rename);
  await q(`update teams set name=coalesce(nullif($2,''), name), sessions=coalesce($3::jsonb, sessions), phrases=coalesce($4::jsonb, phrases) where id=$1`,
    [params.id, name, sessions ? JSON.stringify(sessions) : null, phrases ? JSON.stringify(phrases) : null]);
  if (sessions) {
    // 없어진 세션에 있던 사람은 그 세션에서만 빠진다. 세션이 하나도 안 남으면 팀의 첫 세션으로
    const rows = await q(`select user_id, sessions, session, role from members where team_id=$1`, [params.id]);
    for (const r of rows) {
      if (r.role === 'pastor') continue;
      const cur = (Array.isArray(r.sessions) && r.sessions.length ? r.sessions : [r.session]).filter(Boolean);
      const kept = cur.filter((x) => sessions.includes(x));
      const next = kept.length ? kept : [sessions[0]];
      if (next.join('\u0000') !== cur.join('\u0000'))
        await q('update members set sessions=$3, session=$4 where team_id=$1 and user_id=$2', [params.id, r.user_id, next, next[0]]);
    }
  }
  return viewOf(await membership(uid, params.id));
});

// 세션 이름 바꾸기의 연쇄. {옛이름: 새이름}
async function renameSessions(teamId, map) {
  const pairs = Object.entries(map).map(([a, b]) => [str(a, 40), str(b, 40)]).filter(([a, b]) => a && b && a !== b);
  if (!pairs.length) return;
  const at = (v) => { for (const [a, b] of pairs) if (v === a) return b; return v; };
  for (const r of await q('select user_id, sessions, session from members where team_id=$1', [teamId])) {
    const cur = (Array.isArray(r.sessions) && r.sessions.length ? r.sessions : [r.session]).filter(Boolean);
    const next = cur.map(at);
    if (next.join('\u0000') !== cur.join('\u0000'))
      await q('update members set sessions=$3, session=$4 where team_id=$1 and user_id=$2', [teamId, r.user_id, next, next[0] || '']);
  }
  const t = await one('select settings from teams where id=$1', [teamId]);
  const st = { ...(t.settings || {}) };
  for (const key of ['slots', 'defaultLineup']) {
    if (st[key] && typeof st[key] === 'object') {
      const o = {}; for (const k of Object.keys(st[key])) o[at(k)] = st[key][k];
      st[key] = o;
    }
  }
  await q('update teams set settings=$2 where id=$1', [teamId, JSON.stringify(st)]);
  // 앞으로의 편성
  for (const r of await q(`select id, lineup from service_dates where team_id=$1 and lineup is not null and date >= (now() at time zone 'Asia/Seoul')::date`, [teamId])) {
    const o = {}; for (const k of Object.keys(r.lineup || {})) o[at(k)] = r.lineup[k];
    await q('update service_dates set lineup=$2 where id=$1', [r.id, JSON.stringify(o)]);
  }
  // 메모의 세션 태그
  for (const [a, b] of pairs) await q(`update notes set session=$3 where team_id=$1 and session=$2`, [teamId, a, b]);
}

// B.7.1 팀 삭제: 30일 유예. 그 사이엔 전원에게 배너가 보이고 인도자가 되돌릴 수 있다
on('DELETE', '/teams/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id, 'leader');
  if (str(body && body.name, 60) !== m.name) throw bad('팀 이름을 정확히 적어 주세요');
  await q('update teams set deleted_at=now() where id=$1', [params.id]);
  await audit(params.id, uid, 'team.delete', params.id, {});
  await notify(params.id, await teamUserIds(params.id), 'team.delete', params.id,
    { title: `${m.name} 팀이 30일 뒤에 지워져요`, body: '인도자가 되돌릴 수 있어요', link: '#/team', actionable: true });
  return { ok: true };
});
on('POST', '/teams/:id/undelete', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  await q('update teams set deleted_at=null where id=$1', [params.id]);
  await q(`delete from notifications where team_id=$1 and type='team.delete'`, [params.id]);
  await audit(params.id, uid, 'team.undelete', params.id, {});
  return { ok: true };
});

/* ---------- B.3 초대 링크 ---------- */
// 팀당 하나뿐이던 링크를 여러 개로. 링크마다 역할·만료·횟수가 다르고 따로 회수한다
// B.9 플랜 한도. 결제가 아직 없어서 검사는 꺼 둔다 (ENFORCE_PLAN=1 이면 켜진다)
const PLAN = {
  free: { members: 10, pastors: 2, sessions: 10, invites: 2, teamsOwned: 1, songs: 25 },
  pro: { members: 25, pastors: 2, sessions: 14, invites: 5, teamsOwned: Infinity, songs: Infinity },
};
const planOf = (t) => PLAN[(t && t.plan) || 'free'] || PLAN.free;
const ENFORCE_PLAN = process.env.ENFORCE_PLAN === '1';
// 한도를 넘었는지 본다. 검사가 꺼져 있으면 언제나 통과 (컬럼과 자리만 미리 만들어 둔 것)
function checkLimit(team, key, count, msg) {
  if (!ENFORCE_PLAN) return;
  const cap = planOf(team)[key];
  if (cap != null && count >= cap) throw new HttpError(402, 'plan_limit', msg(cap));
}
const LIVE_INVITES = { free: PLAN.free.invites, pro: PLAN.pro.invites };
const inviteView = (r) => ({
  id: r.id, code: r.code, role: r.role, uses: r.uses,
  maxUses: r.max_uses, expiresAt: r.expires_at, createdAt: r.created_at,
  revoked: !!r.revoked_at,
  dead: !!r.revoked_at || (r.expires_at && new Date(r.expires_at) < new Date()) || (r.max_uses != null && r.uses >= r.max_uses),
});
on('GET', '/teams/:id/invites', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const rows = await q('select * from invites where team_id=$1 order by created_at desc limit 50', [params.id]);
  return { invites: rows.map(inviteView) };
});
on('POST', '/teams/:id/invites', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id, 'leader');
  const role = ['member', 'session_lead', 'pastor'].includes(str(body.role, 20)) ? str(body.role, 20) : 'member';
  const days = [7, 30, 0].includes(+body.days) ? +body.days : 30;         // 0 = 만료 없음
  const maxUses = +body.maxUses === 1 ? 1 : null;                          // 1회용 아니면 무제한
  const live = await q(`select id from invites where team_id=$1 and revoked_at is null
      and (expires_at is null or expires_at > now()) and (max_uses is null or uses < max_uses)`, [params.id]);
  const cap = LIVE_INVITES[m.plan || 'free'] || LIVE_INVITES.free;
  if (live.length >= cap) throw bad(`살아 있는 초대 링크는 ${cap}개까지예요. 안 쓰는 링크를 회수해 주세요`);
  const expires = days ? new Date(Date.now() + days * 86400e3).toISOString() : null;
  const r = await one(`insert into invites(team_id, code, role, expires_at, max_uses, created_by)
    values($1,$2,$3,$4,$5,$6) returning *`, [params.id, randomToken(12), role, expires, maxUses, uid]);
  await audit(params.id, uid, 'invite.create', r.id, { role, days, maxUses });
  return { invite: inviteView(r) };
});
on('DELETE', '/teams/:id/invites/:inviteId', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const r = await q('update invites set revoked_at=now() where team_id=$1 and id=$2 and revoked_at is null returning id', [params.id, params.inviteId]);
  if (!r.length) throw notFound('그 링크가 없어요');
  await audit(params.id, uid, 'invite.revoke', params.inviteId, {});
  return { ok: true };
});

// B.4.2 멤버 고치기: 이름·세션·역할·활성. 인도자는 여기서 만들 수 없다(넘기기로만)
on('PATCH', '/teams/:id/members/:userId', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const cur = await one('select * from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
  if (!cur) throw notFound('그 멤버가 없어요');
  const t = await one('select sessions from teams where id=$1', [params.id]);
  const teamSessions = Array.isArray(t && t.sessions) ? t.sessions : [];

  if (body.role !== undefined) {
    const role = str(body.role, 20);
    if (!['session_lead', 'member', 'pastor'].includes(role)) throw bad('인도자는 「인도자 넘기기」로만 바꿔요');
    if (cur.role === 'leader') throw bad('인도자는 「인도자 넘기기」로만 바꿔요');
    if (role === 'pastor') {
      const n = await one(`select count(*)::int as n from members where team_id=$1 and role='pastor' and user_id<>$2`, [params.id, params.userId]);
      if (n.n >= 2) throw bad('목회자는 팀에 두 명까지예요');
    }
    await q('update members set role=$3 where team_id=$1 and user_id=$2', [params.id, params.userId, role]);
    // 목회자가 되면 세션은 비운다. 목회자에서 내려오면 세션 하나는 있어야 한다
    if (role === 'pastor') await q(`update members set sessions='{}', session='' where team_id=$1 and user_id=$2`, [params.id, params.userId]);
    else if (cur.role === 'pastor') await q('update members set sessions=$3, session=$4 where team_id=$1 and user_id=$2',
      [params.id, params.userId, [teamSessions[0]].filter(Boolean), teamSessions[0] || '']);
  }
  if (body.name !== undefined) {
    const name = str(body.name, 12);
    if (!name) throw bad('이름을 적어 주세요');
    await q('update members set name=$3 where team_id=$1 and user_id=$2', [params.id, params.userId, name]);
  }
  if (body.sessions !== undefined) {
    const role = str(body.role, 20) || cur.role;
    const list = (strList(body.sessions) || []).filter((x) => teamSessions.includes(x));
    if (role !== 'pastor' && !list.length) throw bad('세션을 하나 이상 골라 주세요');
    await q('update members set sessions=$3, session=$4 where team_id=$1 and user_id=$2', [params.id, params.userId, list, list[0] || '']);
  }
  if (body.active !== undefined) {
    const on = !!body.active;
    if (!on && cur.role === 'leader') throw bad('인도자는 비활성으로 둘 수 없어요. 먼저 인도자를 넘기세요');
    if (!on && params.userId === uid) throw bad('나를 비활성으로 둘 수는 없어요');
    await q('update members set active=$3, deactivated_at=$4 where team_id=$1 and user_id=$2',
      [params.id, params.userId, on, on ? null : new Date().toISOString()]);
    if (!on) await clearFromLineups(params.id, params.userId);
    await audit(params.id, uid, on ? 'member.activate' : 'member.deactivate', params.userId, {});
  }
  return { ok: true };
});

// 비활성·삭제된 사람을 앞으로의 편성에서 뺀다. 지난 발행본은 그대로 둔다
async function clearFromLineups(teamId, userId) {
  const rows = await q(`select id, lineup from service_dates where team_id=$1 and date >= (now() at time zone 'Asia/Seoul')::date`, [teamId]);
  for (const r of rows) {
    const lu = r.lineup && typeof r.lineup === 'object' ? r.lineup : null;
    if (!lu) continue;
    let touched = false;
    const out = {};
    for (const k of Object.keys(lu)) {
      const v = Array.isArray(lu[k]) ? lu[k].filter((x) => x !== userId) : lu[k];
      if (Array.isArray(lu[k]) && v.length !== lu[k].length) touched = true;
      out[k] = v;
    }
    if (touched) await q('update service_dates set lineup=$2 where id=$1', [r.id, JSON.stringify(out)]);
  }
}

// B.6.1 인도자 넘기기: 팀 전체가 그대로 넘어간다. 결제 담당은 따라가지 않는다
on('POST', '/teams/:id/transfer', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const to = str(body.userId, 64);
  if (!to || to === uid) throw bad('넘길 사람을 골라 주세요');
  const target = await one('select * from members where team_id=$1 and user_id=$2', [params.id, to]);
  if (!target) throw notFound('그 멤버가 없어요');
  if (target.active === false) throw bad('비활성 멤버에게는 넘길 수 없어요');
  if (target.role === 'pastor') throw bad('목회자에게는 넘길 수 없어요');
  // 새 인도자를 먼저 세우면 유일 인덱스에 걸리니 옛 인도자를 먼저 내린다
  await q(`update members set role='session_lead' where team_id=$1 and user_id=$2`, [params.id, uid]);
  await q(`update members set role='leader' where team_id=$1 and user_id=$2`, [params.id, to]);
  await q('update teams set created_by=$2 where id=$1', [params.id, to]);
  await audit(params.id, uid, 'team.transfer', to, {});
  const all = await teamUserIds(params.id);
  await notify(params.id, all, 'team.transfer', to, { title: `인도자가 ${target.name}으로 바뀌었어요`, link: '#/team' });
  return { ok: true, billingUserId: (await one('select billing_user_id, created_by from teams where id=$1', [params.id])) };
});

// B.6.2 결제 담당 넘기기. 결제 연동 전이라 값만 바뀐다
on('POST', '/teams/:id/billing', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const t = await one('select billing_user_id, created_by from teams where id=$1', [params.id]);
  const owner = t.billing_user_id || t.created_by;
  if (owner !== uid) throw forbidden('결제 담당자만 넘길 수 있어요');
  const to = str(body.userId, 64);
  const target = await one('select name from members where team_id=$1 and user_id=$2 and active', [params.id, to]);
  if (!target) throw notFound('그 멤버가 없어요');
  await q('update teams set billing_user_id=$2 where id=$1', [params.id, to]);
  await audit(params.id, uid, 'team.billing', to, {});
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

// B.4.3 삭제 / B.4.4 팀 나가기
// 본인이 나가면 비활성으로 둔다(쓴 메모·지난 편성이 남게). 인도자가 내보내면 삭제하고 그 사람 메모도 지운다
on('DELETE', '/teams/:id/members/:userId', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  const self = params.userId === uid;
  if (!self && m.role !== 'leader') throw forbidden('인도자만 내보낼 수 있어요');
  const target = await one('select * from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
  if (!target) throw notFound('그 멤버가 없어요');
  if (target.role === 'leader') throw bad('인도자는 먼저 「인도자 넘기기」를 해야 해요');
  const t = await one('select billing_user_id, created_by from teams where id=$1', [params.id]);
  if ((t.billing_user_id || t.created_by) === params.userId) throw bad('결제 담당자예요. 먼저 결제 담당을 넘겨 주세요');

  await clearFromLineups(params.id, params.userId);
  if (self) {
    await q(`update members set active=false, deactivated_at=now() where team_id=$1 and user_id=$2`, [params.id, params.userId]);
    await audit(params.id, uid, 'member.leave', params.userId, {});
  } else {
    await q('delete from notes where team_id=$1 and author_id=$2', [params.id, params.userId]).catch(() => {});
    await q('delete from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
    await audit(params.id, uid, 'member.remove', params.userId, { name: target.name });
  }
  const leader = await one(`select user_id from members where team_id=$1 and role='leader' and active limit 1`, [params.id]);
  if (self && leader && leader.user_id !== uid) await notify(params.id, [leader.user_id], 'member.left', params.userId,
    { title: `${josa(target.name, '이', '가')} 팀에서 나갔어요`, link: '#/team' });
  return { ok: true, deactivated: self };
});

// 지울 때 함께 지워지는 것을 미리 세어 보여 준다 (B.4.3 2단계 확인)
on('GET', '/teams/:id/members/:userId/impact', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const notes = await one('select count(*)::int as n from notes where team_id=$1 and author_id=$2', [params.id, params.userId]).catch(() => ({ n: 0 }));
  const rows = await q(`select lineup from service_dates where team_id=$1 and lineup is not null`, [params.id]);
  let slots = 0;
  for (const r of rows) for (const k of Object.keys(r.lineup || {})) if (Array.isArray(r.lineup[k]) && r.lineup[k].includes(params.userId)) slots++;
  return { notes: (notes && notes.n) || 0, lineupSlots: slots };
});

// 링크를 열어 보는 단계. 왜 못 쓰는지 이유를 나눠서 알려 준다
async function inviteOf(token) {
  const r = await one('select * from invites where code=$1', [token]);
  if (!r) return { err: '초대 링크가 잘못됐어요' };
  const leader = await one(`select m.name from members m where m.team_id=$1 and m.role='leader' and m.active limit 1`, [r.team_id]);
  const who = leader ? `${leader.name}님에게` : '인도자에게';
  if (r.revoked_at) return { err: `이 링크는 회수됐어요. ${who} 새 링크를 받으세요` };
  if (r.expires_at && new Date(r.expires_at) < new Date()) return { err: `이 링크는 기한이 지났어요. ${who} 새 링크를 받으세요` };
  if (r.max_uses != null && r.uses >= r.max_uses) return { err: `이 링크는 이미 다 쓰였어요. ${who} 새 링크를 받으세요` };
  const t = await one('select * from teams where id=$1', [r.team_id]);
  if (!t) return { err: '초대 링크가 잘못됐어요' };
  if (t.deleted_at) return { err: '이 팀은 삭제 예정이에요' };
  return { invite: r, team: t };
}
on('GET', '/invite/:token', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const r = await inviteOf(params.token);
  if (r.err) throw notFound(r.err);
  const n = await one('select count(*)::int as n from members where team_id=$1 and active', [r.team.id]);
  const mine = await membership(uid, r.team.id);
  return { teamName: r.team.name, sessions: r.team.sessions, count: n.n, role: r.invite.role, alreadyMember: !!mine };
});

on('POST', '/invite/:token/join', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const r = await inviteOf(params.token);
  if (r.err) throw notFound(r.err);
  const t = r.team, inv = r.invite;
  const name = str(body.name, 40);
  if (!name) throw bad('이름을 적어 주세요');
  const already = await one('select role, active from members where team_id=$1 and user_id=$2', [t.id, uid]);
  // 비활성이던 사람이 다시 들어오면 원래 역할로 되살린다 (초대 링크의 역할이 아니라)
  if (already) {
    await q(`update members set name=$3, active=true, deactivated_at=null where team_id=$1 and user_id=$2`, [t.id, uid, name]);
    await q('update users set display_name=$2 where id=$1', [uid, name]);
    if (already.active === false) await audit(t.id, uid, 'member.rejoin', uid, {});
    return viewOf(await membership(uid, t.id));
  }
  const pastor = inv.role === 'pastor';
  if (pastor) {
    const n = await one(`select count(*)::int as n from members where team_id=$1 and role='pastor'`, [t.id]);
    if (n.n >= 2) throw bad('목회자는 팀에 두 명까지예요');
  } else if (ENFORCE_PLAN) {
    const n = await one(`select count(*)::int as n from members where team_id=$1 and active and role<>'pastor'`, [t.id]);
    const cap = planOf(t).members;
    if (n.n >= cap) {
      // 정원이 찼다는 것은 인도자가 알아야 한다
      const l = await one(`select user_id from members where team_id=$1 and role='leader' and active limit 1`, [t.id]);
      if (l) await notify(t.id, [l.user_id], 'invite.full', t.id,
        { title: `${t.name} 정원(${cap}명)이 찼어요`, body: '누군가 초대 링크로 들어오려다 막혔어요', link: '#/team', actionable: true });
      throw new HttpError(402, 'plan_limit', `${t.name}은 지금 ${cap}명까지예요. 인도자에게 알려 주세요`);
    }
  }
  const sessions = pastor ? [] : (strList(body.sessions) || [pickSession(t, str(body.session, 40))]).filter(Boolean);
  const session = pastor ? '' : (sessions[0] || pickSession(t, ''));
  await q(`insert into members(user_id, team_id, name, session, sessions, role) values($1,$2,$3,$4,$5,$6)`,
    [uid, t.id, name, session, sessions, inv.role]);
  await q('update users set display_name=$2 where id=$1', [uid, name]);
  await q('update invites set uses = uses + 1 where id=$1', [inv.id]);
  // 인도자에게 알림
  const leader = await one(`select user_id from members where team_id=$1 and role='leader' and active limit 1`, [t.id]);
  if (leader && leader.user_id !== uid) await notify(t.id, [leader.user_id], 'member.join', uid,
    { title: `${josa(name, '이', '가')} ${pastor ? '목회자로' : (session ? session + '으로' : '멤버로')} 들어왔어요`, link: '#/team' });
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
  // 발행본 안에 들어 있는 말씀은 스냅샷이라 메모까지 담겨 있을 수 있다 → 보는 사람 권한으로 다시 거른다
  if (row.doc && row.doc.word) row.doc = { ...row.doc, word: wordView(row.doc.word, await membership(uid, teamId)) };
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

// 말씀만 가볍게 (편집기·콘티 보기 진입 때). 발행본이 없어도 된다
on('GET', '/services/:id/word', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const m = await requireMember(uid, teamId);
  const w = await one('select word from service_words where team_id=$1 and service_id=$2', [teamId, params.id]);
  const rd = await one('select rev from service_reads where team_id=$1 and service_id=$2 and user_id=$3', [teamId, params.id, uid]);
  return { word: wordView(w && w.word, m), readRev: rd ? rd.rev : 0 };
});

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

// §4.2 말씀 탭: 목회자·인도자가 볼 다가오는 예배 목록 (콘티 있는 것 + 4주 안 사역 날짜)
on('GET', '/words', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const m = await requireMember(uid, teamId);
  if (m.role !== 'leader' && m.role !== 'pastor') throw forbidden('인도자와 목회자만 볼 수 있어요');
  const rows = await q(`select sd.id as "dateId", sd.date::text as date, sd.label, sd.service_id as "serviceId", w.word
                        from service_dates sd left join service_words w on w.team_id=sd.team_id and w.service_id=sd.service_id
                        where sd.team_id=$1 and sd.open and sd.date >= current_date - interval '30 days'
                          and sd.date < current_date + interval '28 days'
                        order by sd.date asc`, [teamId]);
  const svcNames = Object.fromEntries((await q('select id, name from services where team_id=$1', [teamId])).map((r) => [r.id, r.name]));
  const drafts = Object.fromEntries((await q('select id, doc from drafts where team_id=$1', [teamId])).map((r) => [r.id, r.doc && r.doc.name]));
  return {
    services: rows.map((r) => ({
      dateId: r.dateId, date: r.date, label: r.label, serviceId: r.serviceId,
      name: (r.serviceId && (svcNames[r.serviceId] || drafts[r.serviceId])) || `${mdOf(r.date)} ${r.label}`,
      past: r.date < new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10),
      word: wordView(r.word, m),
    })),
    role: m.role,
  };
});

// §4.6 목회자 링크 만들기 (인도자)
on('POST', '/services/:id/word-link', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId, 'leader');
  const token = randomToken(18);
  const expires = new Date(Date.now() + 7 * 86400000);
  await q('insert into word_links(token, team_id, service_id, created_by, expires_at) values($1,$2,$3,$4,$5)', [token, teamId, params.id, uid, expires]);
  const svc = await one('select name, date::text as date from services where team_id=$1 and id=$2', [teamId, params.id]);
  const d = await one('select date::text as date, label from service_dates where team_id=$1 and service_id=$2', [teamId, params.id]);
  const name = (svc && svc.name) || (d ? `${mdOf(d.date)} ${d.label}` : '예배');
  return { token, expiresAt: expires, teamName: m.name, leaderName: m.mname, serviceName: name };
});

// 링크 페이지: 로그인 없이 열고 한 번만 제출
on('GET', '/word-link/:token', async ({ params }) => {
  const l = await one('select w.*, t.name as "teamName" from word_links w join teams t on t.id=w.team_id where w.token=$1', [str(params.token, 64)]);
  if (!l) throw notFound('링크가 없어요');
  if (l.used_at) throw new HttpError(410, 'used', '이미 보낸 링크예요. 고치려면 인도자에게 새 링크를 받아 주세요');
  if (new Date(l.expires_at) < new Date()) throw new HttpError(410, 'expired', '만료된 링크예요. 인도자에게 새 링크를 받아 주세요');
  const svc = await one('select name, date::text as date from services where team_id=$1 and id=$2', [l.team_id, l.service_id]);
  const d = await one('select date::text as date, label from service_dates where team_id=$1 and service_id=$2', [l.team_id, l.service_id]);
  const leader = await one(`select name from members where team_id=$1 and role='leader' order by created_at asc limit 1`, [l.team_id]);
  return {
    teamName: l.teamName, leaderName: leader ? leader.name : '',
    serviceName: (svc && svc.name) || (d ? `${mdOf(d.date)} ${d.label}` : '예배'),
    date: (svc && svc.date) || (d && d.date) || null,
  };
});
on('POST', '/word-link/:token', async ({ params, body }) => {
  const token = str(params.token, 64);
  const l = await one('select * from word_links where token=$1', [token]);
  if (!l) throw notFound('링크가 없어요');
  if (l.used_at) throw new HttpError(410, 'used', '이미 보낸 링크예요');
  if (new Date(l.expires_at) < new Date()) throw new HttpError(410, 'expired', '만료된 링크예요');
  const name = str(body.name, 40); if (!name) throw bad('이름을 적어 주세요');
  const passage = str(body.passage, 60); if (!passage) throw bad('본문을 적어 주세요');
  const word = {
    passage, title: str(body.title, 40), line: str(body.line, 80),
    memo: str(body.memo, 1000), memoPublic: false,
    from: { type: 'link', name }, receivedAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
  await q(`insert into service_words(team_id, service_id, word, updated_at) values($1,$2,$3,now())
           on conflict (team_id, service_id) do update set word=excluded.word, updated_at=now()`, [l.team_id, l.service_id, JSON.stringify(word)]);
  await q('update word_links set used_at=now() where token=$1', [token]);
  try {
    const leaders = (await q(`select user_id from members where team_id=$1 and role='leader'`, [l.team_id])).map((r) => r.user_id);
    await notify(l.team_id, leaders, 'word.received', l.service_id, { title: `${josa(name, '이', '가')} 말씀을 보냈어요`, body: [passage, word.title].filter(Boolean).join(' · '), link: '#/edit/' + l.service_id });
  } catch (e) { console.error('notify word-link', e); }
  return { ok: true };
});

// §4.3 "수정 요청": 목회자에게 word.request 즉시 1회
on('POST', '/services/:id/word-request', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const pastors = (await q(`select user_id from members where team_id=$1 and role='pastor'`, [teamId])).map((r) => r.user_id);
  if (!pastors.length) throw bad('팀에 목회자가 없어요. 링크로 보내 주세요');
  const svc = await one('select name from services where team_id=$1 and id=$2', [teamId, params.id]);
  await notify(teamId, pastors, 'word.request', params.id, { title: '말씀을 다시 봐 주세요', body: (svc && svc.name) || '', link: '#/word', actionable: true });
  return { ok: true, sent: pastors.length };
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
  try { await syncUsages(teamId, params.id, doc, uid); } catch (e) { console.error('usages', e); }
  return { ok: true, version: +doc.version || 0 };
});

// 사용 이력은 발행본에서만 만든다 (명세 A.1.3). 다시 발행하면 이 예배 줄을 지우고 새로 쓴다
async function syncUsages(teamId, serviceId, doc, uid) {
  await q('delete from song_usages where team_id=$1 and service_id=$2', [teamId, serviceId]);
  const items = doc.items || [];
  const date = /^\d{4}-\d{2}-\d{2}$/.test(String(doc.date || '')) ? doc.date : null;
  const last = items.length - 1;
  for (let i = 0; i < items.length; i++) {
    const it = items[i] || {};
    let songId = str(it.songId, 64);
    // 라이브러리에 없는 임시 곡이면 이력도 남기지 않는다
    if (!songId && str(it.arrId, 64)) {
      const a = await one('select song_id from arrangements where id=$1 and team_id=$2', [it.arrId, teamId]);
      songId = a ? a.song_id : '';
    }
    if (!songId) continue;
    const ok = await one('select id from songs where id=$1 and team_id=$2', [songId, teamId]);
    if (!ok) continue;
    await q(`insert into song_usages(team_id, song_id, arrangement_id, service_id, service_date, service_name, position, is_application, key_used, via_medley, leader_id)
             values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) on conflict (song_id, service_id) do update set
               arrangement_id=excluded.arrangement_id, service_date=excluded.service_date, service_name=excluded.service_name,
               position=excluded.position, is_application=excluded.is_application, key_used=excluded.key_used`,
      [teamId, songId, str(it.arrId, 64) || null, serviceId, date, str(doc.name, 120), i, i === last, str(it.key, 12), !!it.medley, uid]);
  }
}

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
  await q('delete from song_usages where team_id=$1 and service_id=$2', [teamId, params.id]);   // 이력은 발행본에서만 나온다
  await q('update service_dates set service_id=null where team_id=$1 and service_id=$2', [teamId, params.id]); // 날짜를 다시 쓸 수 있게 (닫기·재생성)
  let freed = 0;
  if (row) {
    const mine = blobIdsOf(row.doc);
    if (mine.length) {
      const used = await teamBlobRefs(teamId);
      const orphan = mine.filter((id) => !used.has(id));
      if (orphan.length) {
        const rows = await q('delete from blobs where team_id=$1 and id = any($2::text[]) returning url', [teamId, orphan]);
        await delBlobs(rows.map((r) => r.url)); freed = rows.length;
      }
    }
  }
  return { ok: true, freedFiles: freed };
});
// 팀 안에서 아직 쓰이는 파일 id 전부 — 콘티·초안뿐 아니라 라이브러리·녹음까지 봐야 남의 파일을 지우지 않는다
async function teamBlobRefs(teamId) {
  const used = new Set();
  for (const r of await q('select doc from services where team_id=$1', [teamId])) blobIdsOf(r.doc).forEach((id) => used.add(id));
  for (const r of await q('select doc from drafts where team_id=$1', [teamId])) blobIdsOf(r.doc).forEach((id) => used.add(id));
  for (const r of await q('select song from library where team_id=$1 and deleted_at is null', [teamId])) songBlobIds(r.song).forEach((id) => used.add(id));
  for (const r of await q('select blob_id from rehearsals where team_id=$1', [teamId])) if (r.blob_id) used.add(r.blob_id);
  return used;
}

// 파일: 어떤 id가 이미 있는지
on('GET', '/blobs', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const ids = str(url.searchParams.get('ids'), 4000).split(',').filter(Boolean).slice(0, 200);
  const rows = ids.length ? await q('select id, url from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  const out = { blobs: Object.fromEntries(rows.map((r) => [r.id, r.url])) };
  // urls=1 이면 바로 읽을 수 있는 서명 URL 도 함께 (악보 다시 불러오기)
  if (url.searchParams.get('urls') === '1') out.urls = await readUrls(rows);
  return out;
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
  // 새 파일을 먼저 올려 성공한 뒤에 옛 파일을 지운다 (도중에 끊겨도 멀쩡한 원본이 사라지지 않게)
  const buf = await readRaw(req);
  if (!buf.length) throw bad('빈 파일이에요');
  const type = str(req.headers['content-type'], 100) || 'application/octet-stream';
  const ext = type.includes('jpeg') ? '.jpg' : type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : type.startsWith('audio/') ? '.audio' : '';
  const up = await putBlob(`teams/${teamId}/${params.id}${ext}`, buf, type);
  await q(`insert into blobs(team_id, id, url, pathname, type, size) values($1,$2,$3,$4,$5,$6)
           on conflict (team_id, id) do update set url=excluded.url, pathname=excluded.pathname, type=excluded.type, size=excluded.size`,
    [teamId, params.id, up.url, up.pathname, type, buf.length]);
  if (existing && existing.url !== up.url) { try { await delBlobs([existing.url]); } catch (e) {} }
  return { url: up.url };
});

/* ---------- 라이브러리 A부: 곡 → 편곡 → 사용 이력 ---------- */
const arrBlobIds = (a) => {
  const ids = new Set();
  for (const p of (a && a.pieces) || []) if (p && p.blob) ids.add(p.blob);
  for (const m of (a && a.media) || []) if (m && m.blob) ids.add(m.blob);
  return [...ids];
};
const arrView = (a) => ({
  id: a.id, songId: a.song_id, name: a.name, isDefault: a.is_default,
  medleySongIds: a.medley_song_ids || [], key: a.key, mod: a.mod, form: a.form,
  bpm: a.bpm, songNote: a.song_note, pieces: a.pieces || [], media: a.media || [],
  chart: a.chart || null, score: a.score || null, updatedAt: a.updated_at,
});
const songView = (s, extra) => ({
  id: s.id, title: s.title, aliases: s.aliases || [], artist: s.artist, origKey: s.orig_key,
  firstLine: s.first_line, tags: s.tags || [], tempo: s.tempo, archived: s.archived,
  notDupOf: s.not_dup_of || [], updatedAt: s.updated_at,
  titleNorm: s.title_norm, titleCho: s.title_cho, ...(extra || {}),
});
// 파생값 (명세 A.1.3). 목록에 붙여 내려보낸다
async function songStats(teamId) {
  const rows = await q(`select song_id, count(*)::int as n, max(service_date) as last, min(service_date) as first
                        from song_usages where team_id=$1 group by song_id`, [teamId]);
  const keys = await q(`select song_id, key_used, count(*)::int as n from song_usages
                        where team_id=$1 and key_used<>'' group by song_id, key_used`, [teamId]);
  const out = {};
  for (const r of rows) out[r.song_id] = { useCount: r.n, lastUsed: r.last, firstUsed: r.first, keyStats: {} };
  for (const k of keys) if (out[k.song_id]) out[k.song_id].keyStats[k.key_used] = k.n;
  return out;
}
// 같은 예배에서 바로 앞뒤에 온 곡 (2회 이상만)
async function companionsOf(teamId, songId) {
  const rows = await q(`select a.position as p, a.service_id, b.song_id as other, b.position as q, s.title
                        from song_usages a join song_usages b on b.service_id=a.service_id and b.team_id=a.team_id
                        join songs s on s.id=b.song_id
                        where a.team_id=$1 and a.song_id=$2 and abs(b.position - a.position)=1`, [teamId, songId]);
  const acc = {};
  for (const r of rows) {
    const dir = r.q > r.p ? 'next' : 'prev';
    const k = r.other + '|' + dir;
    acc[k] = acc[k] || { songId: r.other, title: r.title, dir, n: 0 };
    acc[k].n++;
  }
  return Object.values(acc).filter((x) => x.n >= 2).sort((a, b) => b.n - a.n).slice(0, 8);
}

// 목록 (전원). 검색은 브라우저가 하고 서버는 팀의 곡을 통째로 준다 — 팀당 곡이 500을 넘지 않는다
on('GET', '/songs', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const since = str(url.searchParams.get('since'), 40);
  const songs = since
    ? await q('select * from songs where team_id=$1 and updated_at > $2 order by updated_at asc', [teamId, since])
    : await q('select * from songs where team_id=$1 order by updated_at asc', [teamId]);
  const arrs = await q('select * from arrangements where team_id=$1 and deleted_at is null order by is_default desc, created_at asc', [teamId]);
  const stats = await songStats(teamId);
  const fixed = arrs.length ? await q(`select id, arrangement_id as "arrangementId", marker_label as "markerLabel", layer, session,
      author_id as "authorId", author_name as "authorName", text from arrangement_notes where arrangement_id = any($1::uuid[])`,
    [arrs.map((a) => a.id)]) : [];
  const notesBy = {};
  for (const n of fixed) (notesBy[n.arrangementId] = notesBy[n.arrangementId] || []).push(n);
  const byId = {};
  for (const a of arrs) (byId[a.song_id] = byId[a.song_id] || []).push({ ...arrView(a), notes: notesBy[a.id] || [] });
  const ids = [...new Set(arrs.flatMap(arrBlobIds))];
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return {
    songs: songs.filter((s) => !s.deleted_at).map((s) => songView(s, { arrangements: byId[s.id] || [], ...(stats[s.id] || { useCount: 0, lastUsed: null, firstUsed: null, keyStats: {} }) })),
    deleted: songs.filter((s) => s.deleted_at).map((s) => s.id),
    now: new Date().toISOString(),
    blobs: await readUrls(blobs),
  };
});

// 비슷한 곡 짝 (정리 카드)
on('GET', '/songs/dups', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const rows = await q('select id, title, title_norm, title_cho, not_dup_of from songs where team_id=$1 and deleted_at is null and not archived', [teamId]);
  const pairs = [];
  for (let i = 0; i < rows.length; i++) for (let j = i + 1; j < rows.length; j++) {
    const a = rows[i], b = rows[j];
    if ((a.not_dup_of || []).includes(b.id) || (b.not_dup_of || []).includes(a.id)) continue;
    if ((a.title_norm && a.title_norm === b.title_norm) || (a.title_cho && a.title_cho === b.title_cho)) pairs.push([a.id, b.id]);
  }
  return { pairs: pairs.slice(0, 50) };
});

// 곡 하나: 사용 이력·고정 메모·함께 부른 곡까지
on('GET', '/songs/:id', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const s = await one('select * from songs where id=$1 and team_id=$2 and deleted_at is null', [params.id, teamId]);
  if (!s) throw notFound('그 곡이 없어요');
  const arrs = await q('select * from arrangements where song_id=$1 and deleted_at is null order by is_default desc, created_at asc', [s.id]);
  const usages = await q(`select service_id as "serviceId", service_date as "serviceDate", service_name as "serviceName",
      position, is_application as "isApplication", key_used as "keyUsed", via_medley as "viaMedley", arrangement_id as "arrangementId"
      from song_usages where team_id=$1 and song_id=$2 order by service_date desc nulls last`, [teamId, s.id]);
  const notes = await q(`select id, arrangement_id as "arrangementId", marker_label as "markerLabel", layer, session,
      author_id as "authorId", author_name as "authorName", text, created_at as "createdAt"
      from arrangement_notes where arrangement_id = any($1::uuid[]) order by created_at asc`, [arrs.map((a) => a.id)]);
  const stats = (await songStats(teamId))[s.id] || { useCount: 0, lastUsed: null, firstUsed: null, keyStats: {} };
  const ids = [...new Set(arrs.flatMap(arrBlobIds))];
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return { song: songView(s, { arrangements: arrs.map(arrView), ...stats }), usages, notes,
    companions: await companionsOf(teamId, s.id), blobs: await readUrls(blobs) };
});

// 새 곡 (인도자). 편곡 하나를 기본으로 함께 만든다
on('POST', '/songs', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId, 'leader');
  const title = str(body.title, 120);
  if (!title) throw bad('곡 제목을 적어 주세요');
  if (ENFORCE_PLAN) {
    const n = await one('select count(*)::int as n from songs where team_id=$1 and not archived and deleted_at is null', [teamId]);
    const cap = planOf(m).songs;
    if (n.n >= cap) throw new HttpError(402, 'plan_limit', `무료는 ${cap}곡까지예요. 안 부르는 곡을 보관하면 자리가 생겨요`);
  }
  const tn = normSong(title);
  const s = await one(`insert into songs(team_id, title, title_norm, title_cho, artist, orig_key, tempo, tags, aliases, first_line, created_by)
    values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) returning *`,
    [teamId, title, tn, choSong(tn), str(body.artist, 60), str(body.origKey, 12), str(body.tempo, 8),
     strList(body.tags) || [], strList(body.aliases) || [], str(body.firstLine, 200), uid]);
  const a = await one(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, song_note, pieces, media)
    values($1,$2,'기본',true,$3,$4,$5,$6,$7,$8) returning *`,
    [s.id, teamId, str(body.key, 12), str(body.mod, 12), str(body.form, 500), str(body.songNote, 300),
     JSON.stringify(Array.isArray(body.pieces) ? body.pieces : []), JSON.stringify(Array.isArray(body.media) ? body.media : [])]);
  return { song: songView(s, { arrangements: [arrView(a)], useCount: 0, lastUsed: null, firstUsed: null, keyStats: {} }) };
});

// 곡 정보 고치기 · 보관 (인도자)
on('PATCH', '/songs/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const s = await one('select * from songs where id=$1 and team_id=$2', [params.id, teamId]);
  if (!s) throw notFound('그 곡이 없어요');
  const set = [], vals = [params.id];
  const put = (col, v) => { vals.push(v); set.push(`${col}=$${vals.length}`); };
  if (body.title !== undefined) {
    const t = str(body.title, 120); if (!t) throw bad('곡 제목을 적어 주세요');
    const tn = normSong(t); put('title', t); put('title_norm', tn); put('title_cho', choSong(tn));
  }
  if (body.artist !== undefined) put('artist', str(body.artist, 60));
  if (body.origKey !== undefined) put('orig_key', str(body.origKey, 12));
  if (body.tempo !== undefined) put('tempo', str(body.tempo, 8));
  if (body.firstLine !== undefined) put('first_line', str(body.firstLine, 200));
  if (body.tags !== undefined) put('tags', strList(body.tags) || []);
  if (body.aliases !== undefined) put('aliases', strList(body.aliases) || []);
  if (body.archived !== undefined) put('archived', !!body.archived);
  if (body.notDupOf !== undefined) put('not_dup_of', (Array.isArray(body.notDupOf) ? body.notDupOf : []).slice(0, 50));
  if (!set.length) return { ok: true };
  set.push('updated_at=now()');
  await q(`update songs set ${set.join(', ')} where id=$1`, vals);
  return { ok: true };
});

// 곡 지우기 (인도자). 이력이 있으면 보관을 권한다
on('DELETE', '/songs/:id', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const s = await one('select * from songs where id=$1 and team_id=$2', [params.id, teamId]);
  if (!s) throw notFound('그 곡이 없어요');
  const used = await one('select count(*)::int as n from song_usages where song_id=$1', [params.id]);
  if (used.n > 0 && url.searchParams.get('force') !== '1') {
    throw new HttpError(409, 'song_used', `${used.n}번 부른 곡이에요. 지우는 대신 보관하는 게 좋아요`);
  }
  await q('update songs set deleted_at=now(), updated_at=now() where id=$1', [params.id]);
  return { ok: true, usages: used.n };
});

// 편곡 만들기 (다른 키로 복제)
on('POST', '/songs/:id/arrangements', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const s = await one('select id from songs where id=$1 and team_id=$2 and deleted_at is null', [params.id, teamId]);
  if (!s) throw notFound('그 곡이 없어요');
  const from = str(body.fromId, 64) ? await one('select * from arrangements where id=$1 and song_id=$2', [body.fromId, s.id]) : null;
  const base = from || { key: '', mod: '', form: '', song_note: '', pieces: [], media: [], chart: null, score: null };
  const a = await one(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, song_note, pieces, media, chart, score)
    values($1,$2,$3,false,$4,$5,$6,$7,$8,$9,$10,$11) returning *`,
    [s.id, teamId, str(body.name, 40) || (str(body.key, 12) || '새 편곡'),
     str(body.key, 12) || base.key, base.mod, base.form, base.song_note,
     JSON.stringify(base.pieces || []), JSON.stringify(base.media || []),
     base.chart ? JSON.stringify(base.chart) : null, base.score ? JSON.stringify(base.score) : null]);
  return { arrangement: arrView(a) };
});

// 편곡 고치기 (인도자). 이 편곡을 쓰는 미발행 예배는 자동으로 따라온다 (참조라서)
on('PATCH', '/arrangements/:id', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const a = await one('select * from arrangements where id=$1 and team_id=$2 and deleted_at is null', [params.id, teamId]);
  if (!a) throw notFound('그 편곡이 없어요');
  const set = [], vals = [params.id];
  const put = (col, v) => { vals.push(v); set.push(`${col}=$${vals.length}`); };
  if (body.name !== undefined) put('name', str(body.name, 40) || '기본');
  if (body.key !== undefined) put('key', str(body.key, 12));
  if (body.mod !== undefined) put('mod', str(body.mod, 12));
  if (body.form !== undefined) put('form', str(body.form, 500));
  if (body.songNote !== undefined) put('song_note', str(body.songNote, 300));
  if (body.bpm !== undefined) put('bpm', +body.bpm || null);
  if (body.pieces !== undefined) put('pieces', JSON.stringify(Array.isArray(body.pieces) ? body.pieces : []));
  if (body.media !== undefined) put('media', JSON.stringify(Array.isArray(body.media) ? body.media : []));
  if (body.chart !== undefined) put('chart', body.chart ? JSON.stringify(body.chart) : null);
  if (body.score !== undefined) put('score', body.score ? JSON.stringify(body.score) : null);
  if (set.length) { set.push('updated_at=now()'); await q(`update arrangements set ${set.join(', ')} where id=$1`, vals); }
  // 기본 편곡 바꾸기는 유일 인덱스 때문에 순서가 있다: 내리고 올린다
  if (body.isDefault === true && !a.is_default) {
    await q('update arrangements set is_default=false where song_id=$1', [a.song_id]);
    await q('update arrangements set is_default=true where id=$1', [params.id]);
  }
  await q('update songs set updated_at=now() where id=$1', [a.song_id]);
  return { ok: true };
});

on('DELETE', '/arrangements/:id', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const a = await one('select * from arrangements where id=$1 and team_id=$2', [params.id, teamId]);
  if (!a) throw notFound('그 편곡이 없어요');
  const left = await one('select count(*)::int as n from arrangements where song_id=$1 and deleted_at is null and id<>$2', [a.song_id, params.id]);
  if (!left.n) throw bad('마지막 편곡은 지울 수 없어요. 곡을 보관하거나 지워 주세요');
  await q('update arrangements set deleted_at=now() where id=$1', [params.id]);
  if (a.is_default) {
    const next = await one('select id from arrangements where song_id=$1 and deleted_at is null order by created_at asc limit 1', [a.song_id]);
    if (next) await q('update arrangements set is_default=true where id=$1', [next.id]);
  }
  await q('update songs set updated_at=now() where id=$1', [a.song_id]);
  return { ok: true };
});

/* 고정 메모 (명세 A.6): 편곡에 붙어 이 곡을 넣을 때마다 따라온다 */
on('POST', '/arrangements/:id/notes', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const a = await one('select * from arrangements where id=$1 and team_id=$2 and deleted_at is null', [params.id, teamId]);
  if (!a) throw notFound('그 편곡이 없어요');
  const layer = ['all', 'session', 'mine'].includes(str(body.layer, 10)) ? str(body.layer, 10) : 'mine';
  const session = str(body.session, 40) || null;
  if (layer === 'all' && m.role !== 'leader') throw forbidden('전체 고정 메모는 인도자만 남길 수 있어요');
  if (layer === 'session' && m.role !== 'leader' && !mySessions(m).includes(session)) throw forbidden('내 세션에만 남길 수 있어요');
  const text = str(body.text, 60);
  if (!text) throw bad('메모를 적어 주세요');
  const r = await one(`insert into arrangement_notes(arrangement_id, team_id, marker_label, layer, session, author_id, author_name, text)
    values($1,$2,$3,$4,$5,$6,$7,$8) returning *`,
    [params.id, teamId, str(body.markerLabel, 8) || 'A', layer, layer === 'session' ? session : null, uid, m.mname || '', text]);
  return { note: { id: r.id, arrangementId: r.arrangement_id, markerLabel: r.marker_label, layer: r.layer, session: r.session, authorId: r.author_id, authorName: r.author_name, text: r.text, createdAt: r.created_at } };
});
on('DELETE', '/arrangements/:id/notes/:noteId', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const m = await requireMember(uid, teamId);
  const n = await one('select * from arrangement_notes where id=$1 and team_id=$2', [params.noteId, teamId]);
  if (!n) throw notFound('그 메모가 없어요');
  if (m.role !== 'leader' && n.author_id !== uid) throw forbidden('내가 쓴 메모만 지울 수 있어요');
  await q('delete from arrangement_notes where id=$1', [params.noteId]);
  return { ok: true };
});

/* 합치기 (명세 A.8.1): 많이 부른 쪽을 남기고 편곡·이력을 옮긴다 */
on('POST', '/songs/merge', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const a = await one('select * from songs where id=$1 and team_id=$2 and deleted_at is null', [str(body.a, 64), teamId]);
  const b = await one('select * from songs where id=$1 and team_id=$2 and deleted_at is null', [str(body.b, 64), teamId]);
  if (!a || !b || a.id === b.id) throw bad('합칠 두 곡을 골라 주세요');
  const cnt = async (id) => (await one('select count(*)::int as n from song_usages where song_id=$1', [id])).n;
  const [na, nb] = [await cnt(a.id), await cnt(b.id)];
  const keep = na >= nb ? a : b, drop = keep.id === a.id ? b : a;
  // 남는 곡에 기본 편곡이 이미 있으니 옮겨 오는 것은 전부 보조 편곡으로
  await q(`update arrangements set song_id=$1, is_default=false, name = name || ' (합침)', updated_at=now() where song_id=$2`, [keep.id, drop.id]);
  // 같은 예배에 두 곡이 다 있었다면 한 줄만 남는다
  await q(`delete from song_usages u where u.song_id=$1 and exists
           (select 1 from song_usages v where v.song_id=$2 and v.service_id=u.service_id)`, [drop.id, keep.id]);
  await q('update song_usages set song_id=$1 where song_id=$2', [keep.id, drop.id]);
  await q(`update songs set aliases = (select array(select distinct e from unnest(aliases || $2::text[] || array[$3::text]) e where e <> '')), updated_at=now() where id=$1`,
    [keep.id, drop.aliases || [], drop.title]);
  await q('update songs set deleted_at=now(), updated_at=now() where id=$1', [drop.id]);
  await audit(teamId, uid, 'song.merge', keep.id, { dropped: drop.id, title: drop.title });
  return { ok: true, keepId: keep.id, dropId: drop.id };
});

/* ---------- 라이브러리: 팀이 함께 쓰는 곡 보관함 ---------- */
const normTitle = (t) => String(t || '').toLowerCase().replace(/\([^)]*\)|\[[^\]]*\]/g, '').replace(/[\s\-–—_.,·'"“”‘’!?~]/g, '');
// 곡 하나에서 참조하는 파일 id
const songBlobIds = (s) => {
  const ids = new Set();
  for (const p of (s && s.pieces) || []) if (p && p.blob) ids.add(p.blob);
  for (const m of (s && s.media) || []) if (m && m.blob) ids.add(m.blob);
  return [...ids];
};
// 내려받기: since 이후 바뀐 것만 (삭제 포함)
on('GET', '/library', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const since = str(url.searchParams.get('since'), 40);
  const rows = since
    ? await q('select id, song, updated_at as "updatedAt", deleted_at as "deletedAt" from library where team_id=$1 and updated_at > $2 order by updated_at asc', [teamId, since])
    : await q('select id, song, updated_at as "updatedAt", deleted_at as "deletedAt" from library where team_id=$1 order by updated_at asc', [teamId]);
  const ids = [...new Set(rows.flatMap((r) => songBlobIds(r.song)))];
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return {
    songs: rows.filter((r) => !r.deletedAt).map((r) => ({ ...r.song, id: r.id, updatedAt: r.updatedAt })),
    deleted: rows.filter((r) => r.deletedAt).map((r) => r.id),
    now: new Date().toISOString(),
    blobs: await readUrls(blobs),
  };
});
// 올리기 (인도자): 바뀐 곡만. 서버가 더 새로우면 건너뛴다
on('PUT', '/library', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const songs = Array.isArray(body.songs) ? body.songs.slice(0, 200) : [];
  const saved = [];
  for (const s of songs) {
    const id = str(s && s.id, 64); if (!id) continue;
    const title = str(s.title, 120);
    const clean = { ...s, id, title, notes: undefined };
    const r = await one(`insert into library(team_id, id, song, norm_title, updated_by, updated_at) values($1,$2,$3,$4,$5,now())
                         on conflict (team_id, id) do update set song=excluded.song, norm_title=excluded.norm_title,
                           updated_by=excluded.updated_by, updated_at=now(), deleted_at=null
                         returning id, updated_at as "updatedAt"`,
      [teamId, id, JSON.stringify(clean), normTitle(title), uid]);
    saved.push(r);
  }
  const del = Array.isArray(body.deleted) ? body.deleted.map((x) => str(x, 64)).filter(Boolean).slice(0, 200) : [];
  if (del.length) await q('update library set deleted_at=now(), updated_at=now() where team_id=$1 and id = any($2::text[])', [teamId, del]);
  return { ok: true, saved, deleted: del.length, now: new Date().toISOString() };
});

/* ---------- §5 합주 녹음 ---------- */
const ROLE_RANK = { member: 0, session_lead: 1, pastor: 0, leader: 2 };
const canUploadRehearsal = (m, st) => m.role !== 'pastor' && ROLE_RANK[m.role] >= ROLE_RANK[st.rehearsalUploadRole || 'member'];
const REHEARSAL_MAX = 150 * 1024 * 1024, REHEARSAL_KEEP_DAYS = 90;

// 콘티 파일(악보·오디오)도 4.5MB 를 넘으면 브라우저가 Blob 으로 바로 올린다
on('POST', '/blobs/:id/upload-url', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  if (!/^[A-Za-z0-9_-]{4,40}$/.test(params.id)) throw bad('파일 id가 이상해요');
  const size = Math.max(0, Math.round(+body.size || 0));
  if (size > 200 * 1024 * 1024) throw new HttpError(413, 'too_large', '파일이 너무 커요 (200MB 이하)');
  const type = str(body.mime, 100) || 'application/octet-stream';
  const ext = type.includes('jpeg') ? '.jpg' : type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : type.startsWith('audio/') ? '.audio' : '';
  const pathname = `teams/${teamId}/${params.id}${ext}`;
  const p = await presignPut(pathname, type, 30);
  return { uploadUrl: p.url, pathname, mime: type };
});
// 직접 올린 파일을 DB 에 등록 (실제로 있는지 확인)
on('POST', '/blobs/:id/register', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const pathname = str(body.pathname, 300);
  if (!pathname.startsWith(`teams/${teamId}/`)) throw bad('경로가 이상해요');
  if (!/^[A-Za-z0-9_-]{4,40}$/.test(params.id)) throw bad('파일 id가 이상해요');
  if (!pathname.startsWith(`teams/${teamId}/${params.id}`)) throw bad('경로가 id 와 맞지 않아요');   // 남의 파일을 자기 id 로 등록하지 못하게
  const h = await headBlob(pathname);
  if (!h) throw bad('파일이 올라오지 않았어요');
  if (h.size > 200 * 1024 * 1024) { await delBlobs([h.url]); throw new HttpError(413, 'too_large', '파일이 너무 커요 (200MB 이하)'); }
  await q(`insert into blobs(team_id, id, url, pathname, type, size) values($1,$2,$3,$4,$5,$6)
           on conflict (team_id, id) do update set url=excluded.url, pathname=excluded.pathname, type=excluded.type, size=excluded.size`,
    [teamId, params.id, h.url, h.pathname, h.contentType || 'application/octet-stream', h.size]);
  return { ok: true, url: h.url };
});

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
  if (!/^[A-Za-z0-9_-]{4,40}$/.test(blobId)) throw bad('파일 id가 이상해요');
  if (!pathname.startsWith(`teams/${teamId}/rehearsals/${blobId}`)) throw bad('경로가 id 와 맞지 않아요');   // 남의 파일 id 로 등록·삭제되지 않게
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
// '나만' 메모는 인도자에게도 보이지 않는다 (§5.3 범위: 전체 / 세션 / 나만)
const rehNoteVisible = (n, m) => n.authorId === m.user_id || n.layer === 'leader'
  || (n.layer === 'session' && mySessions(m).includes(n.session));
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
      [id, teamId, svcId, itemId, str(x.markerId, 40) || null, str(x.mediaId, 40) || null, x.t == null ? null : +x.t, layer, session, text, uid, layer === 'leader' ? '인도자' : m.mname, x.at ? new Date(+x.at) : new Date()]);
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

// 악보 재구성 (인도자): 오선 한 줄을 보내면 그 줄의 마디를 악보 데이터로 돌려준다.
// 한 장을 통째로 읽으면 뒤로 갈수록 흐트러져서(마디 오류 39%), 줄 단위로 나눠 읽는다(4%).
on('POST', '/score', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  if (!geminiConfigured()) throw new HttpError(503, 'no_omr', '채보 엔진이 아직 연결되지 않았어요 (GEMINI_API_KEY)');
  const b64 = String(body.b64 || '');
  const mime = /^image\/(jpeg|png|webp)$/.test(String(body.mime || '')) ? String(body.mime) : 'image/jpeg';
  if (b64.length < 100) throw bad('이미지가 비어 있어요');
  if (b64.length > 9e6) throw new HttpError(413, 'too_large', '이미지가 너무 커요');
  let r;
  try { r = await transcribeScore({ b64, mime }, { thinking: str(body.thinking, 10) || 'LOW', repair: body.repair !== false }); }
  catch (e) {
    if (e.status === 429) throw new HttpError(429, 'omr_quota', '채보 한도에 걸렸어요. 잠시 뒤 다시 해 주세요');
    throw new HttpError(502, 'omr_failed', '채보 실패: ' + (e.message || ''));
  }
  const usd = estimateUSD(r.model, r.usage);
  // 원화는 대략만 보여 준다 (환율은 USD_KRW 로 바꿀 수 있음)
  return { songs: r.songs, model: r.model, usage: r.usage, badMeasures: r.badMeasures, cost: usd, costKRW: Math.round(usd * (+process.env.USD_KRW || 1450) * 10) / 10 };
});

// 악보 데이터 → MusicXML (내려받기·다른 프로그램에서 열기)
on('POST', '/score/musicxml', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, str(body.teamId, 64));
  const { toMusicXML } = await import('../lib/score.js');
  return { xml: toMusicXML(body.score || {}) };
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
const DEF_SETTINGS = { serviceAutoCreateWeeks: 4, nameRule: '{월}/{일} {이름}', reminderDay: 25, reminderMonthsAhead: 3,
  wordRequestDay: 2, wordRequestOn: true, rehearsalUploadRole: 'member', pastorCanMemo: false,
  defaultPractice: '', defaultRehearsal: '',
  songTags: ['경배', '찬양', '적용', '오프닝', '성탄', '부활', '수련회'] };
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
    // 비활성 (§2.2): 미래 날짜 중 콘티도·편성도·가능 여부 답도 없는 것만 삭제. 나머지는 닫기만 한다
    await q(`delete from service_dates sd where sd.team_id=$1 and sd.recurring_id=$2 and sd.date > current_date
             and sd.service_id is null and coalesce(jsonb_array_length(sd.lineup), 0) = 0
             and not exists (select 1 from availability a where a.team_id=sd.team_id and a.date=sd.date)`, [params.id, params.rid]);
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
    await notify(params.id, to, 'date.opened', row.id, { title: `${mdOf(row.date)} ${row.label} 일정이 열렸어요`, body: row.time ? `${row.time} · 참여 가능한지 알려주세요` : '참여 가능한지 알려주세요', link: '#/cal', actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00') });
  } catch (e) { console.error('notify date.opened', e); }
  return { ok: true, date: row };
});

// 날짜 열기·닫기
on('PATCH', '/teams/:id/dates/:did', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const row = await one('select *, date::text as dtext from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  if (typeof body.open === 'boolean') {
    if (!body.open && row.service_id) throw bad('콘티가 있는 날짜는 닫을 수 없어요. 먼저 콘티를 삭제하세요');
    await q('update service_dates set open=$2 where id=$1', [params.did, body.open]);
    if (body.open !== !!row.open) { // §1 date.opened / date.closed
      try {
        const iso = String(row.dtext).slice(0, 10), md = mdOf(iso);
        if (body.open) await notify(params.id, await teamUserIds(params.id, { exceptRole: 'pastor', except: uid }), 'date.opened', row.id, { title: `${md} ${row.label} 일정이 열렸어요`, body: row.time ? `${row.time} · 참여 가능한지 알려주세요` : '참여 가능한지 알려주세요', link: '#/cal', actionable: true, expiresAt: new Date(iso + 'T23:59:59+09:00') });
        else await notify(params.id, await teamUserIds(params.id, { except: uid }), 'date.closed', row.id, { title: `${md} ${row.label}는 이번 주 쉽니다`, body: '', link: '#/cal' });
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
  if (body.reminderMonthsAhead != null) next.reminderMonthsAhead = Math.max(1, Math.min(3, Math.round(+body.reminderMonthsAhead)));
  if (body.wordRequestOn != null) next.wordRequestOn = !!body.wordRequestOn;
  if (body.pastorCanMemo != null) next.pastorCanMemo = !!body.pastorCanMemo;
  if (body.defaultPractice != null) next.defaultPractice = str(body.defaultPractice, 80);
  if (body.defaultRehearsal != null) next.defaultRehearsal = str(body.defaultRehearsal, 80);
  if (body.songTags != null) { const l = strList(body.songTags); if (l) next.songTags = l.slice(0, 20); }
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
const teamMembers = (teamId) => q(`select user_id as "userId", name, session, sessions as msessions, role from members where team_id=$1 and active order by created_at asc`, [teamId]);
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
  const dates = await q(`select id, date::text as date, label, time, source, open, service_id as "serviceId", lineup, notified
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
  const row = await one('select id, date::text as date, label, time, lineup, notified, service_id as "serviceId" from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  const lineup = cleanLineup(row.lineup);
  const md = mdOf(row.date), where = `${md} ${row.label}`;
  const link = row.serviceId ? '#/view/' + row.serviceId : '#/cal';
  const now = new Date().toISOString();
  // 누구에게 이미 알렸는지는 따로 기록해 둔다. 편성에서 빠진 사람은 지금 lineup 에 없으므로 lineup 만으로는 알 수 없다
  const already = new Set((Array.isArray(row.notified) ? row.notified : []).map((x) => str(x, 64)).filter(Boolean));
  const firstTime = already.size === 0;
  const nowIn = new Set(lineup.map((r) => r.memberId).filter(Boolean));   // 빈 자리('')는 제외
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
    await notify(params.id, [mid], 'lineup.changed', row.id, { title: `${md} 편성에서 빠졌어요`, body: row.label, link: '#/cal', actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00') });
    sent++;
  }
  await q('update service_dates set lineup=$2, notified=$3 where id=$1',
    [params.did, JSON.stringify(lineup.map((r) => ({ ...r, notifiedAt: r.memberId ? (r.notifiedAt || now) : null }))), JSON.stringify([...nowIn])]);
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
  // B.7.1 삭제 예약한 지 30일이 지난 팀은 여기서 실제로 지운다 (파일까지)
  let teamsDropped = 0;
  for (const t of await q(`select id from teams where deleted_at is not null and deleted_at < now() - interval '30 days'`)) {
    try {
      const urls = (await q('select url from blobs where team_id=$1', [t.id])).map((b) => b.url);
      if (urls.length) await delBlobs(urls);
      await q('delete from teams where id=$1', [t.id]);   // 나머지는 on delete cascade
      teamsDropped++;
    } catch (e) { console.error('team drop', t.id, e); }
  }
  const recs = await q(`select r.* from recurring r join teams t on t.id=r.team_id where r.active=true and t.deleted_at is null`);
  let n = 0;
  for (const rec of recs) { await fillDates(rec.team_id, rec); n++; }
  // D-N주 콘티 자동 생성 (모든 팀) + 90일 지난 알림 정리 + 녹음 보관
  let created = 0;
  for (const t of await q('select id from teams where deleted_at is null')) {
    try { created += await autoCreateServices(t.id); } catch (e) { console.error('autoCreate', t.id, e); }
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
  return { ok: true, recurring: n, created, purged, warned, dropped, teamsDropped };
});

// 알림 배치 (KST 10:00): 월간 스케줄 요청 · 보류 D-14 · 주간 말씀 요청 (§1.2 시각)
on('GET', '/cron/remind', async ({ req }) => {
  if (!process.env.CRON_SECRET || req.headers['authorization'] !== `Bearer ${process.env.CRON_SECRET}`) throw forbidden('크론 전용');
  let asked = 0, maybes = 0;
  for (const t of await q('select id, settings from teams')) {
    try { const r = await scheduleReminders(t.id, { ...DEF_SETTINGS, ...(t.settings || {}) }); asked += r.asked; maybes += r.maybes; } catch (e) { console.error('reminders', t.id, e); }
  }
  return { ok: true, asked, maybes };
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
    // 파일 그 자체가 본문인 경로(POST /blobs/:id)만 JSON 파싱을 건너뛴다. 이미지 base64 를 싣는 경로는 크게
    const rawBody = method === 'POST' && /^\/blobs\/[^/]+$/.test(path);
    const body = (method === 'GET' || rawBody) ? {} : await readBody(req, /^\/(ocr|omr)$/.test(path) ? 12e6 : 1e6);
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
