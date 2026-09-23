// 콘티 API — 계정 · 팀 · 초대. Vercel 서버리스 함수 하나(api/index.js)에 작은 라우터.
// vercel.json 의 rewrite 가 /api/* 를 /api?p=<경로> 로 보내고, 여기서 p(또는 원래 pathname)로 라우팅합니다.
// 로컬: npm run dev (scripts/dev.mjs가 이 핸들러를 /api/* 에 그대로 붙임)
import { q, one, tx } from '../lib/db.js';
import { sessionClaims, sessionTokens, sessionCookie, clearSessionCookie, randomToken, isApp, appSessionToken } from '../lib/session.js';
import { hashPasswordAsync, verifyPasswordAsync, USERNAME_RE, PASSWORD_MIN } from '../lib/password.js';
import { verifyIdToken, audiencesOf, socialConfigured } from '../lib/social.js';
import { putBlob, delBlobs, readUrls, presignPut, headBlob, blobExists, BlobDownError, sweepBlobs } from '../lib/blob.js';
import { ocrBands, visionConfigured } from '../lib/vision.js';
import { sendPush, pushConfigured, vapidPublicKey, pushEndpointOk } from '../lib/push.js';
import { fcmConfigured } from '../lib/fcm.js';
import { apnsConfigured } from '../lib/apns.js';
import { rcAuthOk, rcConfigured, planFromEvent } from '../lib/iap.js';
import { transcribeSheet, transcribeScore, geminiConfigured, geminiModel, estimateUSD, ocrChordsGemini } from '../lib/gemini.js';
import { norm as normSong, cho as choSong } from '../lib/song.js';
import { safeDoc, safeItem } from '../lib/docsafe.js';
import { randomBytes } from 'node:crypto';
import { gzip } from 'node:zlib';

class HttpError extends Error { constructor(status, code, message) { super(message || code); this.status = status; this.code = code; } }
const bad = (m) => new HttpError(400, 'bad_request', m);
const noAuth = () => new HttpError(401, 'unauthorized', '로그인이 필요해요');
const forbidden = (m) => new HttpError(403, 'forbidden', m || '권한이 없어요');
const notFound = (m) => new HttpError(404, 'not_found', m || '없어요');

/* ---------- 요청/응답 도우미 ---------- */
async function readBody(req, max = 1e6) {
  if (req.body !== undefined && req.body !== null) return typeof req.body === 'string' ? JSON.parse(req.body || '{}') : req.body;
  // 한도를 넘으면 더 모으지 않고 버린다. 전에는 거절한 뒤에도 끝까지 이어 붙여서
  // 로그인 없이 큰 요청 몇십 개로 인스턴스 메모리를 다 쓸 수 있었다 (Cloud Run 은 요청끼리 메모리를 나눠 쓴다)
  const tooBig = () => new HttpError(413, 'too_large', '요청이 너무 커요');
  if (+req.headers['content-length'] > max) { req.resume(); throw tooBig(); }
  return new Promise((res, rej) => {
    let s = '', over = false; req.setEncoding('utf8');
    req.on('data', (c) => { if (over) return; s += c; if (s.length > max) { over = true; s = ''; req.resume(); rej(tooBig()); } });
    req.on('end', () => { if (over) return; try { res(s ? JSON.parse(s) : {}); } catch { rej(bad('JSON이 아니에요')); } });
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
async function send(res, status, data, headers) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  for (const k in headers || {}) res.setHeader(k, headers[k]);
  // 애플 로그인 콜백처럼 HTML 을 그대로 내보내는 자리가 있다
  const ct = String(res.getHeader ? (res.getHeader('Content-Type') || '') : '');
  const body = /json/i.test(ct) ? JSON.stringify(data) : String(data);
  // Cloud Run 은 응답을 압축해 주지 않는다 (Vercel 은 앞단이 해 줬다). 곡 목록 같은 큰 JSON 이 폰으로 열 배 크게 가던 것을
  // 여기서 gzip 한다. 요청을 모르는 자리(Workers 의 흉내 res 에는 req 가 없다)는 전처럼 그대로 보낸다
  const req = res.req;
  if (req && req.headers && body.length > 1024) {
    const v = res.getHeader('Vary');
    res.setHeader('Vary', v ? `${v}, Accept-Encoding` : 'Accept-Encoding');
    if (/\bgzip\b/.test(String(req.headers['accept-encoding'] || ''))) {
      try {
        const gz = await new Promise((ok, no) => gzip(body, (e, b) => (e ? no(e) : ok(b))));
        res.setHeader('Content-Encoding', 'gzip');
        return res.end(gz);
      } catch (e) { console.error('gzip', e.message); }
    }
  }
  res.end(body);
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
  plan: planName(t), planUntil: t.plan_until || null, planSource: t.plan_source || null,
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
// 유료 AI 호출 한도. 하루 팀당 이만큼까지. ENFORCE_PLAN 과 무관하게 늘 켜 둔다 —
// 이건 요금제가 아니라 비용 사고를 막는 안전장치다
const AI_DAILY = { omr: 60, score: 400, ocr: 300 };
// 한 사람이 하루에 쓸 수 있는 총량. 팀을 여러 개 만들어도 이건 못 넘는다
const AI_DAILY_USER = { omr: 80, score: 500, ocr: 400 };
// 서비스 전체의 하루 총량. 가입은 누구나 공짜라 계정을 찍어 내면 사람당 한도도 그만큼 늘어난다 —
// 그래도 이건 못 넘는다. 차면 모두 멈춘다 (선불 크레딧이 바닥나 전원이 못 쓰게 되는 것보다 낫다)
const AI_DAILY_ALL = { omr: 1000, score: 1500, ocr: 3000 };
const MAX_TEAMS_PER_USER = 20;   // 요금제가 아니라 스팸·비용 사고 방지선
const KST_DAY = `(now() at time zone 'Asia/Seoul')::date`;
const aiCap = (prefix, table, kind, dflt) => +process.env[prefix + kind.toUpperCase()] || table[kind] || dflt;
// 부르기 전에 한도 안에서 n 번 쓸 자리를 먼저 잡는다 (전체 → 팀 → 사람, 한 문장씩 원자적으로).
// 전에는 세어 보고(select) 부른 뒤에 더해서, 동시에 보내면 모두 '아직 여유'를 보고 통과했다 (한도 60 에 128번)
async function aiGuard(teamId, kind, uid, n = 1) {
  const label = kind === 'ocr' ? '코드 인식' : '채보';
  const take = (sql, params) => one(sql, params).then((r) => !!r);
  const all = aiCap('AI_DAILY_ALL_', AI_DAILY_ALL, kind, 1000);
  if (!await take(`insert into ai_usage_all(day, kind, calls) select ${KST_DAY}, $1::text, $2::int where $2::int <= $3::int
                   on conflict (day, kind) do update set calls = ai_usage_all.calls + excluded.calls
                   where ai_usage_all.calls + excluded.calls <= $3::int returning calls`, [kind, n, all]))
    throw new HttpError(429, 'ai_quota', `오늘은 ${label} 요청이 너무 많아 멈췄어요. 내일 다시 해 주세요`);
  const cap = aiCap('AI_DAILY_', AI_DAILY, kind, 100);
  if (!await take(`insert into ai_usage(team_id, day, kind, calls, tokens) select $1::uuid, ${KST_DAY}, $2::text, $3::int, 0 where $3::int <= $4::int
                   on conflict (team_id, day, kind) do update set calls = ai_usage.calls + excluded.calls
                   where ai_usage.calls + excluded.calls <= $4::int returning calls`, [teamId, kind, n, cap])) {
    await aiRelease(null, kind, null, n);
    throw new HttpError(429, 'ai_quota', `오늘 ${label} 한도(${cap}회)를 다 썼어요. 내일 다시 해 주세요`);
  }
  if (!uid) return;
  const ucap = aiCap('AI_DAILY_USER_', AI_DAILY_USER, kind, 150);
  if (!await take(`insert into ai_usage_user(user_id, day, kind, calls) select $1::uuid, ${KST_DAY}, $2::text, $3::int where $3::int <= $4::int
                   on conflict (user_id, day, kind) do update set calls = ai_usage_user.calls + excluded.calls
                   where ai_usage_user.calls + excluded.calls <= $4::int returning calls`, [uid, kind, n, ucap])) {
    await aiRelease(teamId, kind, null, n);
    throw new HttpError(429, 'ai_quota', `오늘 ${label}를 너무 많이 했어요. 내일 다시 해 주세요`);
  }
}
// 잡아 둔 자리를 돌려준다: 과금되지 않은 실패(Gemini 가 오류로 답함)나 월 한도(402)에 막혔을 때
async function aiRelease(teamId, kind, uid, n = 1) {
  const dec = (t, where, params) => q(`update ${t} set calls = greatest(0, calls - $${params.length + 1}::int) where day=${KST_DAY} and ${where}`,
    [...params, n]).catch((e) => console.error('aiRelease', e.message));
  await dec('ai_usage_all', 'kind=$1', [kind]);
  if (teamId) await dec('ai_usage', 'team_id=$1 and kind=$2', [teamId, kind]);
  if (uid) await dec('ai_usage_user', 'user_id=$1 and kind=$2', [uid, kind]);
}
// 부른 뒤: 토큰을 적고, 잡아 둔 것보다 더 부른 만큼(악보 다시 묻기 · Vision 으로 다시 읽기) 더 센다.
// 이미 쓴 것이라 한도를 넘어도 센다 (다음 요청이 막힌다)
async function aiCount(teamId, kind, tokens, uid, extra = 0) {
  const more = Math.max(0, Math.round(+extra || 0));
  if (more) {
    await q(`insert into ai_usage_all(day, kind, calls) values(${KST_DAY}, $1, $2)
             on conflict (day, kind) do update set calls = ai_usage_all.calls + excluded.calls`, [kind, more]).catch(() => {});
    if (uid) await q(`insert into ai_usage_user(user_id, day, kind, calls) values($1, ${KST_DAY}, $2, $3)
                      on conflict (user_id, day, kind) do update set calls = ai_usage_user.calls + excluded.calls`, [uid, kind, more]).catch(() => {});
  }
  await q(`insert into ai_usage(team_id, day, kind, calls, tokens) values($1, ${KST_DAY}, $2, $3, $4)
           on conflict (team_id, day, kind) do update set calls = ai_usage.calls + excluded.calls, tokens = ai_usage.tokens + excluded.tokens`,
    [teamId, kind, more, Math.max(0, +tokens || 0)]).catch((e) => console.error('aiCount', e.message));
}
const teamSettings = async (teamId) => {
  const t = await one('select settings from teams where id=$1', [teamId]);
  return { ...DEF_SETTINGS, ...((t && t.settings) || {}) };
};
async function requireMember(uid, teamId, role) {
  const m = await membership(uid, teamId);
  if (!m) throw forbidden('이 팀의 멤버가 아니에요');
  if (m.active === false) throw forbidden('이 팀에서 비활성 상태예요. 인도자에게 문의해 주세요');
  if (role === 'leader' && m.role !== 'leader') throw forbidden('인도자만 할 수 있어요');
  return m;
}
async function meView(uid) {
  const u = await one('select id, username, display_name, agreed_ver from users where id=$1', [uid]);
  if (!u) throw noAuth();
  q(`update members set last_seen_at=now() where user_id=$1 and (last_seen_at is null or last_seen_at < now() - interval '1 hour')`, [uid]).catch(() => {});
  const rows = await q(`select t.*, m.user_id, m.name as mname, m.session, m.sessions as msessions, m.role, m.capo, m.active from members m join teams t on t.id=m.team_id
                        where m.user_id=$1 order by m.active desc, m.created_at asc`, [uid]);
  // 비활성인 팀은 목록에 넣지 않는다. 다만 그 팀뿐이면 왜 안 보이는지 알려 준다 (B.4.3)
  const live = rows.filter((r) => r.active !== false);
  const out = { user: { id: u.id, username: u.username, name: u.display_name, agreedVer: u.agreed_ver || '', legalVer: LEGAL_VERSION }, team: live[0] ? viewOf(live[0]) : null, teams: live.map(viewOf) };
  if (!live.length && rows.length) {
    // 스스로 나간 팀만 남았으면 막힌 게 아니다 — 팀이 없는 사람처럼 새 팀을 만들거나 초대로 들어간다.
    // 나가기도 비활성(active=false)으로 남기므로 기록(team_audit)의 마지막 동작으로 가른다. 기록이 없으면 예전처럼 막힘으로 본다
    const acts = await q(`select distinct on (team_id) team_id, action from team_audit
                          where target=$1 and team_id = any($2::uuid[]) and action in ('member.leave','member.deactivate','member.activate','member.rejoin')
                          order by team_id, at desc`, [uid, rows.map((r) => r.id)]).catch(() => []);
    const left = new Set(acts.filter((a) => a.action === 'member.leave').map((a) => a.team_id));
    const by = rows.find((r) => !left.has(r.id));
    if (by) out.blocked = { teamName: by.name };
  }
  return out;
}
function pickSession(team, s) {
  const list = team.sessions || [];
  return list.includes(s) ? s : (list[0] || '');
}

/* ---------- 라우트 ---------- */
const routes = [];
const on = (method, pattern, fn) => routes.push({ method, re: new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn });

on('GET', '/health', async () => ({ ok: true, app: 'conti', enforcePlan: ENFORCE_PLAN }));

on('POST', '/auth/signup', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), password = String(body.password || ''), name = str(body.name, 40);
  if (!USERNAME_RE.test(username)) throw bad('아이디는 3~20자, 영문 소문자·숫자·. _ - 만 쓸 수 있어요');
  if (password.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  if (!name) throw bad('이름을 적어 주세요');
  if (await one('select 1 from users where username=$1', [username])) throw new HttpError(409, 'taken', '이미 쓰는 아이디예요');
  // 가입은 주소당 15분에 30개까지. 계정마다 AI 하루 한도가 따로라 스크립트로 계정을 찍어 내면 한도도 늘어났다.
  // 교회 와이파이에서 팀원이 한꺼번에 가입해도 걸리지 않게 넉넉히. 앞단 주소가 없는 로컬(개발·테스트)은 세지 않는다
  const ip = clientIp(req);
  const keys = /^(-|127\.|::1$|::ffff:127\.)/.test(ip) ? [] : [[`signup:|${ip}`, 30]];
  await assertNotLocked(keys).catch((e) => { throw e.code === 'locked' ? new HttpError(429, 'locked', '여기서 가입이 너무 많았어요. 15분 뒤에 다시 해 주세요') : e; });
  // 가입 시 약관·개인정보처리방침 동의 시각을 남긴다 (나중에 증명이 필요할 수 있다)
  const agreedAt = /^\d{4}-\d{2}-\d{2}T/.test(String(body.agreedAt || '')) ? new Date(body.agreedAt) : new Date();
  const u = await one('insert into users(username, password_hash, display_name, last_login_at, agreed_at, agreed_ver) values($1,$2,$3,now(),$4,$5) returning id',
    [username, await hashPasswordAsync(password), name, agreedAt, LEGAL_VERSION]);
  await noteFailure(keys);   // 이름은 '실패'지만 여기서는 가입 수를 센다 (같은 15분 창)
  return { data: withAppToken(req, await meView(u.id), u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

// 앱은 appToken 만 세션으로 받는다. 다른 응답에도 token 이 있어서(목사님 말씀 링크) 그 값이 로그인 토큰을
// 덮어 iOS 앱이 로그아웃됐다. token 은 이미 깔린 앱(아무 token 이나 받는 판)을 위해 같이 둔다
const withAppToken = (req, data, uid) => { if (!isApp(req)) return data; const t = appSessionToken(uid); return { ...data, token: t, appToken: t }; };
// 앱이 보낸 동의 시각. 없거나 이상하면 null (전에는 없으면 지금 시각으로 채워 동의한 것으로 남겼다)
function agreedAtOf(body) {
  if (!/^\d{4}-\d{2}-\d{2}T/.test(String((body && body.agreedAt) || ''))) return null;
  const d = new Date(body.agreedAt);
  return isNaN(d) ? null : d;
}
// 비밀번호가 바뀌어 다른 기기의 로그인이 끊기면 그 기기로 가던 알림도 끊는다. keep 은 지금 이 기기(웹푸시 endpoint · 앱 토큰)
async function dropPushExcept(uid, keep) {
  const ep = String((keep && keep.endpoint) || '').slice(0, 2000), tok = str(keep && keep.pushToken, 400);
  await q('delete from push_subs where user_id=$1 and endpoint<>$2', [uid, ep]);
  await q('delete from push_tokens where user_id=$1 and token<>$2', [uid, tok]);
}

// X-Forwarded-For 의 맨 앞은 클라이언트가 마음대로 적을 수 있다. Cloud Run 앞단은 받은 값을 지우지 않고
// 진짜 주소를 맨 뒤에 붙인다 (Vercel 은 통째로 덮어써서 첫 값이 곧 진짜였다) → 맨 뒤 값을 쓴다
const clientIp = (req) => String(req.headers['x-forwarded-for'] || req.socket?.remoteAddress || '').split(',').pop().trim().slice(0, 45) || '-';
// 로그인·복구 시도 제한. '아이디|주소' 로 8번, 주소를 바꿔 가며 두드리는 것까지 막으려고 '아이디|*' 로 30번
const LOCK_MS = 15 * 60 * 1000;
const lockKeys = (kind, username, req) => [[`${kind}${username}|${clientIp(req)}`, 8], [`${kind}${username}|*`, 30]];
async function assertNotLocked(keys) {
  try {
    for (const [k, lim] of keys) {
      const la = await one('select n, last from login_attempts where username=$1', [k]);
      if (la && la.n >= lim && Date.now() - new Date(la.last).getTime() < LOCK_MS) throw new HttpError(429, 'locked', '시도가 너무 많아요. 15분 뒤에 다시 해 주세요');
    }
  } catch (e) { if (e instanceof HttpError) throw e; }
}
async function noteFailure(keys) {
  for (const [k] of keys) {
    try { await q(`insert into login_attempts(username, n, last) values($1, 1, now()) on conflict (username) do update set n = case when login_attempts.last < now() - interval '15 minutes' then 1 else login_attempts.n + 1 end, last = now()`, [k]); } catch (e) {}
  }
}
async function clearFailures(keys) { try { await q('delete from login_attempts where username = any($1::text[])', [keys.map(([k]) => k)]); } catch (e) {} }
on('POST', '/auth/login', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), password = String(body.password || '');
  const keys = lockKeys('', username, req);
  await assertNotLocked(keys);
  const u = await one('select id, password_hash from users where username=$1', [username]);
  if (!u || !(await verifyPasswordAsync(password, u.password_hash))) {
    await noteFailure(keys);
    throw new HttpError(401, 'bad_login', '아이디 또는 비밀번호가 맞지 않아요');
  }
  await clearFailures(keys);
  await q('update users set last_login_at=now() where id=$1', [u.id]);
  return { data: withAppToken(req, await meView(u.id), u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

// ---- 구글·애플 로그인 -------------------------------------------------------
// 앱·웹이 받아 온 ID 토큰을 서버가 제공자 공개키로 검증한다. 토큰만 믿고 세션을 준다.
// 이미 로그인한 채로 부르면 그 계정에 붙이고(계정 연결), 아니면 찾거나 새로 만든다
const SOCIAL = { google: '구글', apple: '애플' };
// 소셜로만 가입한 계정의 아이디. 사람이 입력할 일은 없고 화면에도 안 보인다
async function freeUsername(seed) {
  const base = String(seed || 'user').toLowerCase().replace(/[^a-z0-9._-]/g, '').slice(0, 12) || 'user';
  for (let i = 0; i < 20; i++) {
    const name = (base + '-' + randomToken(6).replace(/[^a-z0-9]/gi, '').toLowerCase()).slice(0, 20);
    if (!USERNAME_RE.test(name)) continue;
    if (!await one('select 1 from users where username=$1', [name])) return name;
  }
  throw bad('아이디를 만들지 못했어요');
}
// 로그인 화면이 어떤 소셜 버튼을 띄울지 알아야 한다 (공개)
// 애플 웹 로그인이 돌아오는 자리. 팝업 방식이면 애플이 이 주소로 form_post 를 보내고,
// 우리는 그 값을 연 창(앱 화면)으로 넘겨 준다. 등록된 Return URL 이라 형식만 맞으면 된다
on('POST', '/auth/apple/callback', async ({ body }) => {
  const tok = str(body && body.id_token, 4000);
  const user = str(body && body.user, 2000);
  const html = `<!doctype html><meta charset="utf-8"><body><script>
   (function(){var d=${JSON.stringify({ id_token: tok, user })};
    try{ if(window.opener){ window.opener.postMessage({source:'apple-signin', data:d}, '*'); window.close(); return } }catch(e){}
    location.replace('/#/'); })();
  </script></body>`;
  return { data: html, headers: { 'Content-Type': 'text/html; charset=utf-8' } };
});
on('GET', '/auth/providers', async () => ({
  google: process.env.GOOGLE_CLIENT_ID_WEB || null,
  apple: process.env.APPLE_SERVICE_ID || null,
  // 앱(네이티브)은 플랫폼마다 다른 클라이언트 ID 를 쓴다
  googleIos: process.env.GOOGLE_CLIENT_ID_IOS || null,
  googleAndroid: process.env.GOOGLE_CLIENT_ID_ANDROID || null,
  appleBundle: process.env.APNS_BUNDLE_ID || 'com.lets1414.app',
}));
on('POST', '/auth/social', async ({ req, uid, body }) => {
  const provider = str(body.provider, 10);
  if (!SOCIAL[provider]) throw bad('지원하지 않는 방식이에요');
  if (!socialConfigured(provider)) throw new HttpError(503, 'no_social', `${SOCIAL[provider]} 로그인이 아직 연결되지 않았어요`);
  let claim;
  try { claim = await verifyIdToken(provider, String(body.idToken || ''), audiencesOf(provider)); }
  catch (e) { throw new HttpError(401, 'bad_token', `${SOCIAL[provider]} 확인에 실패했어요: ${e.message}`); }

  const found = await one('select user_id from identities where provider=$1 and subject=$2', [provider, claim.sub]);

  // 이미 로그인한 상태면 '계정 연결'이다. 다만 로그인 화면에서 부른 것(login)은 연결이 아니다 —
  // 로그아웃이 실패해 남은 옛 세션 쿠키에 다음 사람의 구글·애플 계정이 영영 붙었다
  if (uid && !body.login) {
    if (found && found.user_id !== uid) throw new HttpError(409, 'taken', `이 ${SOCIAL[provider]} 계정은 다른 계정에 이미 연결돼 있어요`);
    if (!found) {
      try {
        await q('insert into identities(provider, subject, user_id, email) values($1,$2,$3,$4)', [provider, claim.sub, uid, claim.email]);
      } catch (e) { throw new HttpError(409, 'taken', `이 계정에는 이미 ${SOCIAL[provider]} 계정이 연결돼 있어요`); }
    }
    return { data: withAppToken(req, await meView(uid), uid), headers: { 'Set-Cookie': sessionCookie(req, uid) } };
  }

  // 로그인 상태가 아니면 찾거나 새로 만든다
  if (found) {
    await q('update users set last_login_at=now() where id=$1', [found.user_id]);
    return { data: withAppToken(req, await meView(found.user_id), found.user_id), headers: { 'Set-Cookie': sessionCookie(req, found.user_id) } };
  }
  // 가입: 약관 동의 시각을 남긴다 (아이디/비밀번호 가입과 같은 기준).
  // 동의를 보여 주지 않고 만든 계정에 '동의함'을 남기면 안 된다 → 동의가 없으면 만들지 않고, 앱이 동의 창을 띄운 뒤 다시 부른다
  const agreedAt = agreedAtOf(body);
  if (!agreedAt) throw new HttpError(428, 'needs_consent', '처음 오셨네요. 이용약관과 개인정보처리방침에 동의한 뒤 가입할 수 있어요');
  const name = str(body.name, 40) || claim.name || (claim.email ? claim.email.split('@')[0] : SOCIAL[provider] + ' 사용자');
  const username = await freeUsername(claim.email ? claim.email.split('@')[0] : provider);
  const u = await one(`insert into users(username, password_hash, display_name, last_login_at, agreed_at, agreed_ver)
                       values($1,'',$2,now(),$3,$4) returning id`, [username, name, agreedAt, LEGAL_VERSION]);
  await q('insert into identities(provider, subject, user_id, email) values($1,$2,$3,$4)', [provider, claim.sub, u.id, claim.email]);
  return { data: withAppToken(req, await meView(u.id), u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});
// 내 계정에 붙은 소셜 계정 목록 / 떼기
on('GET', '/auth/social', async ({ uid }) => {
  if (!uid) throw noAuth();
  const rows = await q('select provider, email, created_at as "at" from identities where user_id=$1 order by provider', [uid]);
  const u = await one('select password_hash from users where id=$1', [uid]);
  return { linked: rows, hasPassword: !!(u && u.password_hash), available: { google: socialConfigured('google'), apple: socialConfigured('apple') } };
});
on('DELETE', '/auth/social/:provider', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const u = await one('select password_hash from users where id=$1', [uid]);
  const rows = await q('select provider from identities where user_id=$1', [uid]);
  // 들어올 길을 모두 없애면 안 된다
  if (!(u && u.password_hash) && rows.length <= 1) throw bad('이 방법 말고는 로그인할 길이 없어요. 먼저 비밀번호를 정해 주세요');
  await q('delete from identities where user_id=$1 and provider=$2', [uid, params.provider]);
  return { ok: true };
});

// 로그아웃: 이 요청에 실린 토큰을 서버에서도 끊는다. 토큰은 서명만 보고 믿어서, 전에는 로그아웃해도
// 복사해 둔 토큰(앱은 localStorage 에 있다)이 90일 동안 그대로 통했다.
// all 이면 모든 기기에서 — 비밀번호를 바꿀 때처럼 auth_epoch 를 지금으로 (그 전에 받은 토큰은 모두 무효)
// 이 기기로 가던 알림도 끊는다. 안 끊으면 교회 공용 아이패드·PC 가 로그아웃한 사람의 콘티·편성 알림을
// (이름까지) 계속 받았다. endpoint·토큰은 그 기기만 아는 값이라 세션이 이미 끝났어도 지운다
on('POST', '/auth/logout', async ({ req, uid, body }) => {
  const toks = sessionTokens(req);
  if (toks.length) await q(`insert into revoked_sessions(id, exp) select * from unnest($1::text[], $2::timestamptz[]) on conflict (id) do nothing`,
    [toks.map((t) => t.tid), toks.map((t) => new Date(t.exp * 1000).toISOString())]);
  const ep = String((body && body.endpoint) || '').slice(0, 2000), tok = str(body && body.pushToken, 400);
  if (ep) await q('delete from push_subs where endpoint=$1', [ep]);
  if (tok) await q('delete from push_tokens where token=$1', [tok]);
  // 모든 기기에서 나가면 다른 기기의 알림도 끊는다 (비밀번호를 바꿀 때와 같게)
  if (uid && body && body.all) { await q('update users set auth_epoch=to_timestamp($2) where id=$1', [uid, nowSec()]); await dropPushExcept(uid, null); }
  return { data: { ok: true }, headers: { 'Set-Cookie': clearSessionCookie(req) } };
});

// 로그인한 채로 하는 되돌릴 수 없는 일(계정 삭제·복구 코드·비밀번호 바꾸기)은 현재 비밀번호를 다시 묻는다.
// 소셜로만 가입한 계정은 비밀번호가 없다 → 로그인만으로 (비밀번호 만들기와 같은 기준).
// 세션만 가진 사람(교회 공용 PC)이 비밀번호를 맞혀 보지 못하게 로그인처럼 횟수를 센다
async function recheckPassword(uid, hash, password, msg) {
  if (!hash) return;
  const keys = [[`reauth:${uid}`, 8]];
  await assertNotLocked(keys);
  if (!(await verifyPasswordAsync(String(password || ''), hash))) { await noteFailure(keys); throw new HttpError(401, 'bad_login', msg || '비밀번호가 맞지 않아요'); }
  await clearFailures(keys);
}

// 계정 삭제 (§7): 아이디·비밀번호로 두 번 확인. 인도자로 남아 있는 팀이 있으면 먼저 넘기게 한다
on('POST', '/auth/delete', async ({ req, uid, body }) => {
  if (!uid) throw noAuth();
  const u = await one('select id, username, password_hash from users where id=$1', [uid]);
  if (!u) throw noAuth();
  if (str(body.username, 40).toLowerCase() !== u.username) throw bad('아이디가 맞지 않아요');
  // 소셜로만 가입한 계정은 아이디 확인만으로 (전에는 비밀번호가 없어 영영 못 지웠다)
  await recheckPassword(uid, u.password_hash, body.password);
  // 넘길 사람이 있는 팀만 막는다. 삭제 예약한 팀(30일 유예)과 나머지가 모두 비활성인 팀은
  // 넘길 수도 없으니(비활성에게는 못 넘긴다) 막지 않고 아래에서 정리한다
  const stuck = await q(`select t.name from members m join teams t on t.id=m.team_id
                         where m.user_id=$1 and m.role='leader' and t.deleted_at is null
                           and (select count(*) from members m2 where m2.team_id=m.team_id and m2.role='leader') = 1
                           and exists (select 1 from members m3 where m3.team_id=m.team_id and m3.user_id<>$1 and m3.active)`, [uid]);
  if (stuck.length) throw bad(`${stuck.map((r) => r.name).join(', ')} 팀의 인도자예요. 다른 사람을 인도자로 지정한 뒤 다시 시도해 주세요`);
  // 한 트랜잭션으로 지운다. 전에는 한 줄씩이라 중간(사람을 가리키는 칸)에서 막히면
  // 메모와 혼자 쓰던 팀만 먼저 지워지고 계정은 남았다. 운영 DB(Neon HTTP)는 문장 묶음을 한 번에 보내므로
  // 문장마다 스스로 대상을 고른다 (앞 문장의 결과를 JS 로 받아 다음을 정하지 않는다)
  const P = [uid];
  // 나만 있는 팀 (내가 만들었는데 아무도 없는 팀 포함) → 팀째로 지운다
  const solo = `select t.id from teams t where (t.created_by=$1 or exists (select 1 from members m where m.team_id=t.id and m.user_id=$1))
                  and not exists (select 1 from members m where m.team_id=t.id and m.user_id<>$1)`;
  const steps = [
    // '누가 했는지'만 가리키는 칸은 비운다. 스키마도 on delete set null 이지만 옛 DB 에서도 되게 직접 비운다
    // (결제 담당·초대 링크·관리 기록·곡·공유 코드를 빠뜨려 전 인도자·팀을 나간 사람의 삭제가 500 이었다)
    ...[['services', 'updated_by'], ['drafts', 'updated_by'], ['service_words', 'updated_by'], ['rehearsals', 'uploaded_by'],
      ['word_links', 'created_by'], ['library', 'updated_by'], ['teams', 'billing_user_id'], ['invites', 'created_by'],
      ['team_audit', 'actor_id'], ['songs', 'created_by'], ['share_codes', 'created_by']]
      .map(([t, c]) => [`update ${t} set ${c}=null where ${c}=$1`, P]),
    // 팀을 만든 사람 칸은 not null → 남은 사람에게 넘긴다 (활성 인도자 → 활성 멤버 → 오래된 순)
    [`update teams t set created_by = (select m.user_id from members m where m.team_id=t.id and m.user_id<>$1
         order by m.active desc, (m.role='leader') desc, m.created_at asc limit 1)
      where t.created_by=$1 and exists (select 1 from members m where m.team_id=t.id and m.user_id<>$1)`, P],
    // 내가 인도자인데 나머지가 모두 비활성이면 들어올 사람도 되살릴 사람도 없다 → 삭제 예약 (30일 뒤 크론이 파일까지)
    [`update teams t set deleted_at=now() where t.deleted_at is null
        and exists (select 1 from members m where m.team_id=t.id and m.user_id=$1 and m.role='leader')
        and exists (select 1 from members m where m.team_id=t.id and m.user_id<>$1)
        and not exists (select 1 from members m where m.team_id=t.id and m.user_id<>$1 and m.active)`, P],
    [`delete from notes where author_id=$1`, P],
    [`delete from blobs where team_id in (${solo}) returning url`, P],
    [`delete from teams where id in (${solo})`, P],
    [`delete from users where id=$1`, P],
  ];
  // 편성에서 뺄 팀은 멤버 줄이 지워지기 전에 적어 둔다
  const myTeams = await q('select team_id from members where user_id=$1', [uid]);
  const out = await tx(steps);
  // 앞으로의 편성에서 뺀다 (비활성·내보내기와 같게). 안 빼면 지운 계정이 편성 표에 남아 자리를 차지한다.
  // 계정이 실제로 지워진 뒤에 (삭제가 되돌려지면 편성은 그대로)
  for (const m of myTeams) {
    try { await clearFromLineups(m.team_id, uid); } catch (e) { console.error('clear lineup', e.message); }
  }
  // 파일은 계정이 실제로 지워진 뒤에 (되돌려진 삭제가 파일만 지우지 않게)
  await delBlobs(out[steps.length - 3].map((r) => r.url));
  return { data: { ok: true }, headers: { 'Set-Cookie': clearSessionCookie(req) } };
});

on('POST', '/auth/password', async ({ req, uid, body }) => {
  if (!uid) throw noAuth();
  const cur = String(body.current || ''), next = String(body.next || '');
  if (next.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  const u = await one('select password_hash from users where id=$1', [uid]);
  // 소셜로만 가입한 계정은 현재 비밀번호가 없다. 그때는 확인을 건너뛰고 새로 정하게 한다
  await recheckPassword(uid, u.password_hash, cur, '현재 비밀번호가 맞지 않아요');
  // 다른 기기의 로그인은 끊고, 이 기기는 새 쿠키로 이어간다
  await q('update users set password_hash=$2, auth_epoch=to_timestamp($3) where id=$1', [uid, await hashPasswordAsync(next), nowSec()]);
  await dropPushExcept(uid, body);
  return { data: withAppToken(req, { ok: true }, uid), headers: { 'Set-Cookie': sessionCookie(req, uid) } };
});

on('GET', '/me', async ({ uid }) => { if (!uid) throw noAuth(); const r = await meView(uid); const u = await one('select recovery_hash is not null as has from users where id=$1', [uid]); r.user.hasRecovery = !!(u && u.has); return r; });

// 약관이 생기기 전에 가입한 사람, 또는 약관이 바뀐 뒤의 재동의
on('POST', '/me/agree', async ({ uid }) => {
  if (!uid) throw noAuth();
  await q('update users set agreed_at=now(), agreed_ver=$2 where id=$1', [uid, LEGAL_VERSION]);
  return { ok: true, agreedVer: LEGAL_VERSION };
});

// ---------- 개인 설정 (무대 조판 · 조용한 시간 · 알림 끄기) ----------
// 기기를 옮겨도 따라온다. 교회 컴퓨터에서 로그인해 PDF 뽑을 때 내 조판이 그대로 온다.
// 무대 조판은 user_stage 에 따로 둔다 — prefs(jsonb) 안에 두면 한 칸만 바꿔도 prefs 전체를 다시 쓰는데
// 크기·개수 제한도 없어서, 한 계정이 큰 요청 몇십 개로 DB 를 수백 MB 부풀릴 수 있었다 (Neon 무료 0.5GB)
const PREFS_MAX = 64 * 1024;            // 조판을 뺀 나머지 설정 전체 (조용한 시간·알림 끄기·메트로놈 …)
const STAGE_VALUE_MAX = 64 * 1024;      // 조판 하나 (블록 자리만 남긴 것이라 보통 수 KB)
const STAGE_MAX = 300, STAGE_TOTAL_MAX = 1024 * 1024;   // 한 사람의 조판 개수·전체. 넘으면 오래 안 고친 것(지난 예배)부터 뺀다
// 화면은 예전처럼 prefs.stage[키] 로 읽는다 (앱 옛 버전도)
async function prefsOf(uid) {
  const u = await one(`select coalesce(prefs,'{}'::jsonb) as prefs from users where id=$1`, [uid]);
  const prefs = { ...((u && u.prefs) || {}) };
  if (prefs.stage !== undefined) {
    // 예전 자리(prefs.stage)에 있던 조판은 처음 읽을 때 옮긴다. 옮기기와 지우기를 한 문장으로 (반만 되지 않게).
    // 언제 고쳤는지 모르니 가장 오래된 것으로 친다
    await q(`with moved as (
               insert into user_stage(user_id, key, value, updated_at)
               select $1, e.key, e.value, to_timestamp(0)
                 from users u, jsonb_each(case when jsonb_typeof(u.prefs->'stage')='object' then u.prefs->'stage' else '{}'::jsonb end) e
                where u.id=$1 and jsonb_typeof(e.value)='object' and length(e.key) <= 120 and octet_length(e.value::text) <= $2
               on conflict (user_id, key) do nothing returning 1)
             update users set prefs = prefs - 'stage' where id=$1`, [uid, STAGE_VALUE_MAX]);
    delete prefs.stage;
  }
  const rows = await q('select key, value from user_stage where user_id=$1', [uid]);
  if (rows.length) prefs.stage = Object.fromEntries(rows.map((r) => [r.key, r.value]));
  return prefs;
}
on('GET', '/me/prefs', async ({ uid }) => {
  if (!uid) throw noAuth();
  return { prefs: await prefsOf(uid), push: { configured: pushConfigured(), key: vapidPublicKey() } };
});
// 부분 병합. 통째로 덮으면 다른 기기가 방금 저장한 것이 날아간다
on('PATCH', '/me/prefs', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const patch = body && typeof body.prefs === 'object' && body.prefs && !Array.isArray(body.prefs) ? { ...body.prefs } : {};
  delete patch.stage;   // 조판은 아래 PUT 으로만 (따로 둔 표)
  const txt = JSON.stringify(patch);
  // 한 단계 더 깊게 합친다: notiOff·quiet 는 객체라 통째로 덮으면 다른 기기에서 끈 종류가 다시 켜졌다
  // (PC 에서 한 종류를 끄면 폰에서 꺼 둔 '콘티 발행'이 되살아남). 앱은 바뀐 키만 보낸다
  const merged = `coalesce(prefs,'{}'::jsonb) || coalesce((
      select jsonb_object_agg(e.key, case when jsonb_typeof(e.value)='object' and jsonb_typeof(users.prefs->e.key)='object'
                                          then (users.prefs->e.key) || e.value else e.value end)
      from jsonb_each($2::jsonb) e), '{}'::jsonb)`;
  // 한 번에 보내는 양만 보던 것을 합친 결과까지 본다. 전에는 키를 바꿔 가며 보내면 한없이 커졌다
  const u = Buffer.byteLength(txt) > PREFS_MAX ? null
    : await one(`update users set prefs = ${merged}
                 where id=$1 and octet_length((${merged} - 'stage')::text) <= $3 returning id`,
      [uid, txt, PREFS_MAX]);
  if (!u) throw new HttpError(413, 'too_big', '설정이 너무 큽니다');
  return { prefs: await prefsOf(uid) };
});
// 무대 조판은 곡·기기구간마다 따로. 한 덩어리로 합치면 기기끼리 서로 덮는다
on('PUT', '/me/prefs/stage/:key', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const key = String(params.key || '').slice(0, 120);
  if (!/^[A-Za-z0-9_.:~-]+$/.test(key)) throw new HttpError(400, 'bad_key', '잘못된 키');
  const val = body && typeof body.value === 'object' && body.value && !Array.isArray(body.value) ? body.value : null;
  if (!val) {
    await q('delete from user_stage where user_id=$1 and key=$2', [uid, key]);
    // 아직 옮기지 않은 예전 자리에 있으면 거기서도 (안 지우면 다음에 읽을 때 되살아난다)
    await q(`update users set prefs = prefs #- array['stage', $2::text] where id=$1 and prefs->'stage' ? $2::text`, [uid, key]);
    return { ok: true };
  }
  const txt = JSON.stringify(val);
  if (Buffer.byteLength(txt) > STAGE_VALUE_MAX) throw new HttpError(413, 'too_big', '조판이 너무 커요');
  await q(`insert into user_stage(user_id, key, value) values($1,$2,$3)
           on conflict (user_id, key) do update set value=excluded.value, updated_at=now()`, [uid, key, txt]);
  await q(`delete from user_stage where user_id=$1 and key in (
             select key from (select key, row_number() over w as n, sum(octet_length(value::text)) over w as total
                                from user_stage where user_id=$1 window w as (order by (key=$2) desc, updated_at desc, key)) s
              where n > $3 or total > $4)`, [uid, key, STAGE_MAX, STAGE_TOTAL_MAX]);
  return { ok: true };
});

// ---------- 네이티브 앱 푸시 토큰 (FCM) ----------
on('POST', '/push/token', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const token = str(body.token, 400);
  const platform = ['android', 'ios'].includes(str(body.platform, 10)) ? str(body.platform, 10) : 'android';
  if (!token) throw bad('토큰이 없어요');
  await q(`insert into push_tokens(token, user_id, platform) values($1,$2,$3)
           on conflict (token) do update set user_id=excluded.user_id, platform=excluded.platform, last_ok_at=now()`,
    [token, uid, platform]);
  return { ok: true };
});
on('POST', '/push/token/remove', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const token = str(body.token, 400);
  if (token) await q('delete from push_tokens where token=$1 and user_id=$2', [token, uid]);
  return { ok: true };
});

// ---------- 푸시 구독 ----------
on('GET', '/push/key', async () => ({ configured: pushConfigured(), key: vapidPublicKey(), app: fcmConfigured() || apnsConfigured(), android: fcmConfigured(), ios: apnsConfigured() }));
on('POST', '/push/subscribe', async ({ uid, body, req }) => {
  if (!uid) throw noAuth();
  const sub = body && body.sub;
  if (!sub || !sub.endpoint || !sub.keys || !sub.keys.p256dh || !sub.keys.auth) throw new HttpError(400, 'bad_sub', '구독 정보가 없습니다');
  const ep = String(sub.endpoint).slice(0, 2000);
  // 서버가 이 주소로 직접 보낸다 (lib/push.js pushEndpointOk)
  if (!pushEndpointOk(ep)) throw new HttpError(400, 'bad_sub', '알림 주소가 올바르지 않아요');
  await q(`insert into push_subs(endpoint, user_id, keys, ua) values($1,$2,$3,$4)
           on conflict (endpoint) do update set user_id=excluded.user_id, keys=excluded.keys, ua=excluded.ua, last_ok_at=now()`,
    [ep, uid, JSON.stringify({ p256dh: String(sub.keys.p256dh), auth: String(sub.keys.auth) }),
     str((req && req.headers && req.headers['user-agent']) || '', 200)]);
  return { ok: true };
});
on('POST', '/push/unsubscribe', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const ep = String((body && body.endpoint) || '').slice(0, 2000);
  if (ep) await q('delete from push_subs where endpoint=$1 and user_id=$2', [ep, uid]);
  return { ok: true };
});
// 이 기기로 시험 발송
on('POST', '/push/test', async ({ uid }) => {
  if (!uid) throw noAuth();
  const n = await sendPush([uid], { title: '알림 시험', body: '이렇게 보여요', link: '#/home', type: 'test' });
  return { sent: n };
});

// 복구 코드 발급 (로그인 상태). 코드는 한 번만 보여주고 해시만 저장.
// 코드가 있으면 비밀번호를 새로 정할 수 있으니 현재 비밀번호를 다시 묻는다 — 전에는 세션만으로 발급돼서
// 공용 PC 에 로그인이 남아 있으면 누구든 코드를 받아 두었다가 비밀번호를 바꿔 주인을 내쫓을 수 있었다
on('POST', '/auth/recovery', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const u = await one('select password_hash from users where id=$1', [uid]);
  if (!u) throw noAuth();
  await recheckPassword(uid, u.password_hash, body && body.password);
  const alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'; const raw = randomToken(18); let code = '';
  for (let i = 0; i < 12; i++) { code += alphabet[raw.charCodeAt(i) % alphabet.length]; if (i === 3 || i === 7) code += '-'; }
  await q('update users set recovery_hash=$2 where id=$1', [uid, await hashPasswordAsync(code)]);
  return { code };
});
// 복구 코드로 비밀번호 재설정 → 로그인. 코드는 폐기
on('POST', '/auth/recover', async ({ req, body }) => {
  const username = str(body.username, 40).toLowerCase(), code = str(body.code, 20).toLowerCase().replace(/\s/g, ''), next = String(body.next || '');
  if (next.length < PASSWORD_MIN) throw bad(`비밀번호는 ${PASSWORD_MIN}자 이상이에요`);
  // 복구 코드도 로그인과 같이 시도 횟수를 센다 (전에는 제한이 없었다)
  const keys = lockKeys('recover:', username, req);
  await assertNotLocked(keys);
  const u = await one('select id, recovery_hash from users where username=$1', [username]);
  if (!u || !u.recovery_hash || !(await verifyPasswordAsync(code, u.recovery_hash))) { await noteFailure(keys); throw new HttpError(401, 'bad_recovery', '아이디 또는 복구 코드가 맞지 않아요'); }
  await clearFailures(keys);
  await q('update users set password_hash=$2, recovery_hash=null, last_login_at=now(), auth_epoch=to_timestamp($3) where id=$1', [u.id, await hashPasswordAsync(next), nowSec()]);
  await dropPushExcept(u.id, null);   // 이 기기는 홈에 들어가며 다시 등록한다
  return { data: withAppToken(req, await meView(u.id), u.id), headers: { 'Set-Cookie': sessionCookie(req, u.id) } };
});

// 내 이름·세션(팀 안에서) 바꾸기
on('PATCH', '/me', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const name = str(body.name, 40) || m.mname;
  // 목회자는 세션이 없다. 이름만 바꿔도 첫 세션이 배정되던 것을 막는다
  const session = m.role === 'pastor' ? '' : pickSession(m, str(body.session, 40) || m.session);
  const capo = body.capo == null ? (+m.capo || 0) : Math.max(0, Math.min(9, Math.round(+body.capo) || 0));
  // 겸임 세션 (§3): 팀 세션 목록에 있는 것만, 대표 세션은 항상 포함
  const asked = strList(body.mySessions);
  const sessions = m.role === 'pastor' ? []
    : asked ? [...new Set([session, ...asked])].filter((s) => s && (m.sessions || []).includes(s))
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
  // 요금제가 꺼져 있어도 이건 막는다 — 팀을 늘려 팀당 AI 한도를 우회하는 것을 방지
  if (owned.n >= MAX_TEAMS_PER_USER) throw new HttpError(429, 'too_many_teams', '팀을 너무 많이 만들었어요');
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
  if (sessions) { const t0 = await one('select plan, plan_until from teams where id=$1', [params.id]);
    checkLimit(t0, 'sessions', sessions.length - 1, (cap) => `세션은 ${cap}개까지예요`); }
  // B.5.2 세션 이름을 바꾸면 멤버·정원·기본 편성·앞으로의 편성·메모가 함께 따라간다. 발행본은 그대로
  const rename = body.rename && typeof body.rename === 'object' ? body.rename : null;
  if (rename) await renameSessions(params.id, rename);
  await q(`update teams set name=coalesce(nullif($2,''), name), sessions=coalesce($3::jsonb, sessions), phrases=coalesce($4::jsonb, phrases) where id=$1`,
    [params.id, name, sessions ? JSON.stringify(sessions) : null, phrases ? JSON.stringify(phrases) : null]);
  if (sessions) {
    // 없어진 세션의 정원·기본 편성 자리도 지운다. 안 그러면 없는 세션이 계속 자동 편성된다
    const t2 = await one('select settings from teams where id=$1', [params.id]);
    const st2 = { ...((t2 && t2.settings) || {}) };
    let cut = false;
    for (const key of ['slots', 'defaultLineup']) {
      if (!st2[key] || typeof st2[key] !== 'object') continue;
      const o = {};
      for (const k of Object.keys(st2[key])) { if (sessions.includes(k)) o[k] = st2[key][k]; else cut = true; }
      st2[key] = o;
    }
    // 정원을 줄였으면 기본 편성의 넘치는 자리도 뒤에서부터 자른다
    if (st2.defaultLineup && typeof st2.defaultLineup === 'object') {
      for (const k of Object.keys(st2.defaultLineup)) {
        const n = st2.slots && st2.slots[k] != null ? +st2.slots[k] : (k === '싱어' ? 3 : 1);
        if (Array.isArray(st2.defaultLineup[k]) && st2.defaultLineup[k].length > n) { st2.defaultLineup[k] = st2.defaultLineup[k].slice(0, n); cut = true; }
      }
    }
    if (cut) await q('update teams set settings=$2 where id=$1', [params.id, JSON.stringify(st2)]);
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
  // 앞으로의 편성. lineup 은 [{session, memberId, …}] 배열이라 원소의 session 만 바꾼다.
  // 그날만 늘리거나 줄인 정원(slots)도 세션 이름이 키라 같이 옮긴다 (안 옮기면 그날 정원이 사라졌다)
  for (const r of await q(`select id, lineup, slots from service_dates where team_id=$1 and date >= (now() at time zone 'Asia/Seoul')::date`, [teamId])) {
    const lineup = Array.isArray(r.lineup) ? r.lineup : [];
    const next = lineup.map((x) => (x && at(x.session) !== x.session ? { ...x, session: at(x.session) } : x));
    const sl = r.slots && typeof r.slots === 'object' ? r.slots : null;
    const moved = sl && Object.keys(sl).some((k) => at(k) !== k);
    if (!next.some((x, i) => x !== lineup[i]) && !moved) continue;
    const slots = moved ? Object.fromEntries(Object.entries(sl).map(([k, v]) => [at(k), v])) : sl;
    await q('update service_dates set lineup=$2, slots=$3 where id=$1', [r.id, JSON.stringify(next), slots ? JSON.stringify(slots) : null]);
  }
  // 메모의 세션 태그 (예배 메모 · 고정 메모). 한 문장으로 바꾼다 — 쌍마다 차례로 바꾸면
  // 드럼↔베이스처럼 맞바꿀 때 두 번째가 첫 번째 결과를 다시 바꿔 전부 한쪽으로 몰렸다
  const from = pairs.map(([a]) => a), to = pairs.map(([, b]) => b);
  for (const t of ['notes', 'arrangement_notes'])
    await q(`update ${t} n set session=m.b from unnest($2::text[], $3::text[]) as m(a, b) where n.team_id=$1 and n.session=m.a`, [teamId, from, to]);
  // 녹음 타임라인 메모의 세션 태그 (세션 메모는 이름이 같아야 그 세션 사람에게 보인다)
  for (const r of await q(`select id, notes from rehearsals where team_id=$1 and notes <> '[]'::jsonb`, [teamId])) {
    const ns = Array.isArray(r.notes) ? r.notes : [];
    if (!ns.some((n) => n && n.session && at(n.session) !== n.session)) continue;
    await q('update rehearsals set notes=$2 where id=$1',
      [r.id, JSON.stringify(ns.map((n) => (n && n.session && at(n.session) !== n.session ? { ...n, session: at(n.session) } : n)))]);
  }
  // 편곡 미디어의 대상 세션
  for (const r of await q(`select id, media from arrangements where team_id=$1 and deleted_at is null`, [teamId])) {
    const md = Array.isArray(r.media) ? r.media : [];
    if (!md.some((m) => Array.isArray(m && m.sessions) && m.sessions.some((x) => at(x) !== x))) continue;
    await q('update arrangements set media=$2 where id=$1',
      [r.id, JSON.stringify(md.map((m) => (Array.isArray(m && m.sessions) ? { ...m, sessions: m.sessions.map(at) } : m)))]);
  }
  // 고정 메모·미디어의 세션 이름이 바뀌었으니 기기의 곡 목록도 다시 받게 한다
  await q('update songs set touched_at=now() where team_id=$1 and deleted_at is null', [teamId]);
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
// 이번 달 한국 시간 기준 'YYYY-MM'
const aiMonth = () => new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 7);
// 곡 단위 월 한도. 이미 이번 달에 센 곡이면 더 차감하지 않는다.
// 한도를 넘으면 402 로 막고, 넘지 않으면 그 곡을 이번 달 사용으로 기록한다
// 인식이 잘 안 됐을 때 이번 달 사용 기록을 지워 준다(= 크레딧 환불).
// 코드가 적은 악보만 골라 올려 공짜로 쓰는 것을 막으려고 달마다 횟수를 둔다
// quota 는 aiSongGuard 가 돌려준 것. 이번 호출이 차감한 것만 돌려준다 — 전에는 이미 센 곡을 다시 부르다
// 실패해도 지난번 기록을 지워 공짜가 됐다. 크레딧으로 낸 곡이면 크레딧을 되돌린다 (F112)
async function aiRefund(teamId, kind, quota) {
  if (!ENFORCE_PLAN || !quota || !quota.charged || !quota.key) return false;
  const key = quota.key;
  const month = aiMonth();
  const n = (await one(`select count(*)::int n from credit_refunds where team_id=$1 and month=$2 and kind=$3`, [teamId, month, kind])).n;
  if (n >= REFUND_PER_MONTH) return false;
  const gone = await q('delete from ai_songs where team_id=$1 and month=$2 and kind=$3 and song_key=$4 returning source', [teamId, month, kind, key]);
  if (!gone.length) return false;
  if (gone[0].source === 'credit') await q('update credit_balance set omr = omr + 1, updated_at=now() where team_id=$1', [teamId]);
  await q('insert into credit_refunds(team_id, month, kind, song_key) values($1,$2,$3,$4) on conflict do nothing', [teamId, month, kind, key]);
  return true;
}

// 엔진이 실패해 아무것도 못 돌려줬을 때, 이 요청이 방금 뺀 것만 되돌린다.
// 위의 환불(인식이 덜 됐다)과 달리 사용자가 골라 쓸 수 있는 게 아니라서 달마다 횟수를 세지 않는다
// quota 는 aiSongGuard 가 돌려준 것 (곡 키 · 이번에 뺐는지). 크레딧으로 낸 곡이면 크레딧을 되돌린다
async function aiUndo(teamId, kind, quota) {
  if (!quota || !quota.charged || !quota.key) return false;
  const gone = await q('delete from ai_songs where team_id=$1 and month=$2 and kind=$3 and song_key=$4 returning source', [teamId, aiMonth(), kind, quota.key]);
  if (!gone.length) return false;
  if (gone[0].source === 'credit') await q('update credit_balance set omr = omr + 1, updated_at=now() where team_id=$1', [teamId]);
  return true;
}

async function aiSongGuard(teamId, kind, songKey) {
  if (!ENFORCE_PLAN) return { charged: false, used: 0, cap: null };
  // 곡을 모르면(곡 키를 안 보내는 예전 앱) 부를 때마다 한 곡으로 센다. 전에는 아예 안 세서
  // 채보 월 한도와 크레딧이 통째로 비어 있었다 (F39)
  const key = str(songKey, 64) || 'call:' + randomToken(9);
  // plan_until 까지 읽어야 기한 지난 유료를 무료로 본다 (F40)
  const t = await one('select plan, plan_until from teams where id=$1', [teamId]);
  const cap = planOf(t)[kind === 'omr' ? 'omrSongs' : 'ocrSongs'];
  const month = aiMonth();
  const seen = await one('select 1 from ai_songs where team_id=$1 and month=$2 and kind=$3 and song_key=$4', [teamId, month, kind, key]);
  // 요금제 몫만 센다. 크레딧으로 낸 곡은 한도 사용량이 아니다
  const used = (await one(`select count(*)::int n from ai_songs where team_id=$1 and month=$2 and kind=$3 and source is distinct from 'credit'`, [teamId, month, kind])).n;
  if (seen) return { charged: false, key, used, cap };            // 같은 달 같은 곡은 다시 안 센다
  const what = kind === 'omr' ? '채보' : '코드 인식';
  if (cap != null && used >= cap) {
    // 채보는 크레딧 팩으로 산 횟수가 남아 있으면 거기서 뺀다 (소멸 없음).
    // 곡을 먼저 적어 둔다 — 같은 곡을 다시 채보하면 또 빠지지 않고(동시에 불러도), 실패하면 돌려준다 (F112)
    if (kind === 'omr') {
      const mine = await q(`insert into ai_songs(team_id, month, kind, song_key, source) values($1,$2,$3,$4,'credit')
                            on conflict do nothing returning 1`, [teamId, month, kind, key]);
      if (!mine.length) return { charged: false, key, used, cap };
      const got = await q(`update credit_balance set omr = omr - 1, updated_at=now()
                           where team_id=$1 and omr > 0 returning omr`, [teamId]);
      if (got.length) return { charged: true, key, used, cap, credits: got[0].omr };
      await q('delete from ai_songs where team_id=$1 and month=$2 and kind=$3 and song_key=$4', [teamId, month, kind, key]);
    }
    throw new HttpError(402, 'ai_limit', `이번 달 ${what} ${cap}곡을 다 썼어요. 다음 달 1일에 다시 채워집니다`);
  }
  const ins = await q('insert into ai_songs(team_id, month, kind, song_key) values($1,$2,$3,$4) on conflict do nothing returning 1', [teamId, month, kind, key]);
  return { charged: ins.length > 0, key, used: used + 1, cap };
}

// B.9 플랜 한도. 결제가 아직 없어서 검사는 꺼 둔다 (ENFORCE_PLAN=1 이면 켜진다)
// 2026-09-17 가격표. 숫자를 고치면 화면 안내(설정 → 플랜)도 같이 따라간다.
// ocrSongs/omrSongs 는 '곡' 단위다 — 악보가 몇 장이든 한 곡은 한 번만 센다.
// ocrSongs: Infinity 는 화면에 '무제한'으로 보이지만, 뒤에서 OCR_GUARD 로 조용히 지킨다
const PLAN = {
  free: { members: 10, pastors: 2, sessions: 10, invites: 2, teamsOwned: 1,
          songs: 25, services: 5, versions: 5,
          ocrSongs: 10, omrSongs: 1, credits: false,
          storage: 200 * 1024 * 1024, fileSize: 30 * 1024 * 1024,
          shareSend: false, readonlyViews: 0 },
  pro: { members: 25, pastors: 2, sessions: 14, invites: 5, teamsOwned: 1,
         songs: Infinity, services: Infinity, versions: 30,
         ocrSongs: 100, omrSongs: 15, credits: false,
         storage: 5 * 1024 * 1024 * 1024, fileSize: 100 * 1024 * 1024,
         shareSend: true, readonlyViews: 1 },
  plus: { members: 50, pastors: 2, sessions: 14, invites: 5, teamsOwned: 1,
          songs: Infinity, services: Infinity, versions: 100,
          ocrSongs: 300, omrSongs: 50, credits: true,
          storage: 30 * 1024 * 1024 * 1024, fileSize: 500 * 1024 * 1024,
          shareSend: true, readonlyViews: Infinity },
};
// 인식이 잘 안 됐을 때 크레딧을 돌려주는 횟수. 코드가 적은 악보만 골라 올려
// 공짜로 쓰는 것을 막는다
const REFUND_PER_MONTH = 3;
// 유료 기간이 지났으면 무료로 본다. 결제·프로모션이 끝났는데 계속 쓰이는 일이 없게 한다.
// plan_until 이 없으면 기한 없는 유료(수동 지정)로 본다.
// 그래서 팀을 읽을 때 plan 만 골라 넘기면 안 된다 — plan_until 도 같이 읽어야 기한이 보인다 (F40)
const planName = (t) => {
  const p = (t && t.plan) || 'free';
  if (p === 'free') return 'free';
  if (t && t.plan_until && new Date(t.plan_until) < new Date()) return 'free';
  return PLAN[p] ? p : 'free';
};
const planOf = (t) => PLAN[planName(t)] || PLAN.free;
const PLAN_RANK = { free: 0, pro: 1, plus: 2 };   // 프로모션·결제가 플랜을 내리지 않게 비교할 때
const ENFORCE_PLAN = process.env.ENFORCE_PLAN === '1';
const LEGAL_VERSION = '2026-09-24';   // 약관·개인정보처리방침 시행일. 내용을 고치면 앱과 함께 올린다 (09-24: Cloud Run·R2 로 옮긴 처리위탁·국외이전 표)
// 한도를 넘었는지 본다. 검사가 꺼져 있으면 언제나 통과 (컬럼과 자리만 미리 만들어 둔 것)
function checkLimit(team, key, count, msg) {
  if (!ENFORCE_PLAN) return;
  const cap = planOf(team)[key];
  if (cap != null && count >= cap) throw new HttpError(402, 'plan_limit', msg(cap));
}
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
  const cap = planOf(m).invites;   // 기한 지난 유료는 무료로 (F40)
  if (ENFORCE_PLAN && live.length >= cap) throw new HttpError(402, 'plan_limit', `살아 있는 초대 링크는 ${cap}개까지예요. 안 쓰는 링크를 회수해 주세요`);
  if (live.length >= 20) throw bad('초대 링크가 너무 많아요. 안 쓰는 링크를 회수해 주세요');
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

// 활성 멤버 자리: 목회자는 활성 두 명까지(나간 목회자는 세지 않는다), 나머지는 요금제 정원까지(ENFORCE_PLAN).
// 새로 들어오기뿐 아니라 다시 들어오기·다시 켜기·목회자에서 내리기도 같은 검사를 한다 (F41·F116).
// 세고 쓰는 것을 팀마다 잠근 한 트랜잭션에서 한다 — 따로 하면 동시에 들어온 사람이 모두 빈자리를 본다 (F115).
// 쓰는 문장은 $1=팀, $2=정원(null 이면 정원 검사 없음) 을 받고, where 에 seatOk(역할식) 을 넣어 자리가 있을 때만 쓴다
const PASTOR_MAX = 2;
const seatOk = (role) => `(case when ${role}='pastor'
    then (select count(*) from members where team_id=$1 and active and role='pastor') < ${PASTOR_MAX}
    else $2::int is null or (select count(*) from members where team_id=$1 and active and role<>'pastor') < $2::int end)`;
async function seated(teamId, t, text, params) {
  const cap = ENFORCE_PLAN ? planOf(t).members : null;
  const [, rows] = await tx([[`select pg_advisory_xact_lock(hashtext($1))`, ['seat:' + teamId]], [text, [teamId, cap, ...params]]]);
  return rows;
}
const seatFull = (role, t) => role === 'pastor' ? bad(`목회자는 팀에 ${PASTOR_MAX}명까지예요`)
  : new HttpError(402, 'plan_limit', `정원(${planOf(t).members}명)이 찼어요. 먼저 다른 멤버를 비활성으로 두세요`);

// B.4.2 멤버 고치기: 이름·세션·역할·활성. 인도자는 여기서 만들 수 없다(넘기기로만)
on('PATCH', '/teams/:id/members/:userId', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const cur = await one('select * from members where team_id=$1 and user_id=$2', [params.id, params.userId]);
  if (!cur) throw notFound('그 멤버가 없어요');
  const t = await one('select sessions, name, plan, plan_until, plan_source, billing_user_id, created_by from teams where id=$1', [params.id]);
  const teamSessions = Array.isArray(t && t.sessions) ? t.sessions : [];

  if (body.role !== undefined) {
    const role = str(body.role, 20);
    if (!['session_lead', 'member', 'pastor'].includes(role)) throw bad('인도자는 「인도자 넘기기」로만 바꿔요');
    if (cur.role === 'leader') throw bad('인도자는 「인도자 넘기기」로만 바꿔요');
    // 목회자가 되거나 목회자에서 내려오면 세는 자리가 바뀐다 (목회자 두 명 · 정원). 비활성이면 켤 때 센다
    const ok = await seated(params.id, t, `update members set role=$4 where team_id=$1 and user_id=$3
        and (not active or role=$4 or (role<>'pastor' and $4<>'pastor') or ${seatOk('$4')}) returning 1`, [params.userId, role]);
    if (!ok.length) throw seatFull(role, t);
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
    if (on) {
      // 다시 켤 때도 새로 들어올 때와 같은 자리 검사 (F41·F116)
      const ok = await seated(params.id, t, `update members set active=true, deactivated_at=null where team_id=$1 and user_id=$3
          and (active or ${seatOk('role')}) returning 1`, [params.userId]);
      if (!ok.length) throw seatFull((await one('select role from members where team_id=$1 and user_id=$2', [params.id, params.userId]) || cur).role, t);
    } else {
      // 그사이 인도자가 된 사람은 끄지 않는다 (넘기기와 겹치면 팀에 인도자가 없어진다, F113)
      const off = await q(`update members set active=false, deactivated_at=now() where team_id=$1 and user_id=$2 and role<>'leader' returning 1`,
        [params.id, params.userId]);
      if (!off.length) throw bad('인도자는 비활성으로 둘 수 없어요. 먼저 인도자를 넘기세요');
      await releaseBilling(t, params.id, params.userId);
      await clearFromLineups(params.id, params.userId);
    }
    await audit(params.id, uid, on ? 'member.activate' : 'member.deactivate', params.userId, {});
  }
  return { ok: true };
});

// 비활성·삭제된 사람을 앞으로의 편성에서 뺀다. 지난 발행본은 그대로 둔다
async function clearFromLineups(teamId, userId) {
  const rows = await q(`select id, lineup from service_dates where team_id=$1 and date >= (now() at time zone 'Asia/Seoul')::date`, [teamId]);
  for (const r of rows) {
    if (!Array.isArray(r.lineup) || !r.lineup.length) continue;
    const next = r.lineup.filter((x) => !x || x.memberId !== userId);
    if (next.length !== r.lineup.length) await q('update service_dates set lineup=$2 where id=$1', [r.id, JSON.stringify(next)]);
  }
  // 기본 편성에서도 뺀다. 안 그러면 새 예배마다 다시 채워진다
  const t = await one('select settings from teams where id=$1', [teamId]);
  const st = (t && t.settings) || {};
  if (st.defaultLineup && typeof st.defaultLineup === 'object') {
    let touched = false;
    const d = {};
    for (const k of Object.keys(st.defaultLineup)) {
      const v = Array.isArray(st.defaultLineup[k]) ? st.defaultLineup[k].filter((x) => x !== userId) : st.defaultLineup[k];
      if (Array.isArray(v) && v.length !== st.defaultLineup[k].length) touched = true;
      d[k] = v;
    }
    if (touched) await q('update teams set settings=$2 where id=$1', [teamId, JSON.stringify({ ...st, defaultLineup: d })]);
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
  // 내리기·세우기를 한 트랜잭션으로 (F113). 따로 보내면 둘째가 실패하거나, 그사이 받을 사람이 나가거나,
  // 두 번 눌러 두 사람에게 넘기면 팀에 활성 인도자가 없어져 인도자 기능이 전부 막혔다.
  // 새 인도자를 먼저 세우면 유일 인덱스에 걸리니 옛 인도자를 먼저 내린다
  const [, up] = await tx([
    [`update members set role='session_lead' where team_id=$1 and user_id=$2 and role='leader'`, [params.id, uid]],
    // 받을 사람이 아직 활성이고, 다른 넘기기가 먼저 끝나 인도자가 이미 선 게 아닐 때만
    [`update members set role='leader' where team_id=$1 and user_id=$2 and active and role in ('member','session_lead')
        and not exists (select 1 from members where team_id=$1 and role='leader' and active) returning user_id`, [params.id, to]],
    // 못 세웠으면 옛 인도자를 되돌린다
    [`update members set role='leader' where team_id=$1 and user_id=$2 and role='session_lead'
        and not exists (select 1 from members where team_id=$1 and role='leader' and active)`, [params.id, uid]],
    // created_by 를 옮기기 전에 결제 담당을 못박아 둔다 (기본값이 created_by 라 같이 넘어가 버린다)
    [`update teams set billing_user_id = coalesce(billing_user_id, created_by), created_by=$2 where id=$1
        and exists (select 1 from members where team_id=$1 and user_id=$2 and role='leader' and active)`, [params.id, to]],
  ]);
  if (!up.length) throw bad('인도자를 넘기지 못했어요. 그 멤버가 방금 나갔거나 인도자가 이미 바뀌었어요');
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
// 스토어 구독(인앱결제)이 살아 있는 팀. 이때만 결제 담당이 실제로 돈을 내고 있다
const storePaid = (t) => !!t && t.plan_source === 'iap' && planName(t) !== 'free';
// 결제 담당이 팀을 떠나거나 비활성이 되면 담당을 인도자에게 돌린다 (G03). billing_user_id 를 비우면
// created_by(= 지금 인도자)가 담당이 된다. 떠나는 사람이 created_by 인 옛 자료면 인도자를 직접 적는다
async function releaseBilling(t, teamId, userId) {
  if (!t || (t.billing_user_id || t.created_by) !== userId || storePaid(t)) return;
  await q(`update teams set billing_user_id = case when created_by=$2
             then (select user_id from members where team_id=$1 and role='leader' and active limit 1) end
           where id=$1 and coalesce(billing_user_id, created_by)=$2`, [teamId, userId]);
  await audit(teamId, null, 'team.billing', null, { from: userId, auto: true });
}

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
  await q('update users set password_hash=$2, auth_epoch=to_timestamp($3) where id=$1', [params.userId, await hashPasswordAsync(pw), nowSec()]);
  await dropPushExcept(params.userId, null);
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
  const t = await one('select billing_user_id, created_by, plan, plan_until, plan_source from teams where id=$1', [params.id]);
  // 결제 담당은 스토어 구독이 살아 있는 동안만 막는다 (그 사람 계정에서 돈이 나가고 있다).
  // 결제 화면을 숨긴 지금(BILLING_UI)은 담당을 넘길 길이 없어, 늘 막으면 인도자를 넘긴 옛 인도자가
  // 나가지도 내보내지지도 못했다 (G03). 나가면 담당은 인도자에게 돌아간다 (releaseBilling)
  if ((t.billing_user_id || t.created_by) === params.userId && storePaid(t)) throw bad('결제 담당자예요. 먼저 결제 담당을 넘겨 주세요');

  // 그사이 인도자로 바뀐 사람은 건드리지 않는다. 넘기기와 겹치면 팀에 활성 인도자가 없어진다 (F113)
  const gone = self
    ? await q(`update members set active=false, deactivated_at=now() where team_id=$1 and user_id=$2 and role<>'leader' returning 1`, [params.id, params.userId])
    : await q(`delete from members where team_id=$1 and user_id=$2 and role<>'leader' returning 1`, [params.id, params.userId]);
  if (!gone.length) throw bad('인도자는 먼저 「인도자 넘기기」를 해야 해요');
  await releaseBilling(t, params.id, params.userId);
  await clearFromLineups(params.id, params.userId);
  if (self) {
    await audit(params.id, uid, 'member.leave', params.userId, {});
  } else {
    await q('delete from notes where team_id=$1 and author_id=$2', [params.id, params.userId]).catch(() => {});
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
  const rows = await q(`select lineup from service_dates where team_id=$1`, [params.id]);
  let slots = 0;
  for (const r of rows) if (Array.isArray(r.lineup)) slots += r.lineup.filter((x) => x && x.memberId === params.userId).length;
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
  // 나갔거나 비활성인(인도자가 뺀) 사람은 '이미 팀에 있어요'가 아니다. 가입 화면을 보여 다시 들어오게 한다 (F42 · G20).
  // 예전에는 '이미 ○○ 팀에 있어요'로 돌려보내 다시 들어올 길이 없었다 — 가입하면 원래 역할로 되살린다 (POST join)
  return { teamName: r.team.name, sessions: r.team.sessions, count: n.n, role: r.invite.role,
           alreadyMember: !!mine && mine.active !== false, rejoin: !!mine && mine.active === false };
});

on('POST', '/invite/:token/join', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const r = await inviteOf(params.token);
  if (r.err) throw notFound(r.err);
  const t = r.team, inv = r.invite;
  const name = str(body.name, 40);
  if (!name) throw bad('이름을 적어 주세요');
  const already = await one('select role, active from members where team_id=$1 and user_id=$2', [t.id, uid]);
  const leaderOf = () => one(`select user_id from members where team_id=$1 and role='leader' and active limit 1`, [t.id]);
  // 자리가 없을 때. 정원이 찼다는 것은 인도자가 알아야 한다
  const full = async (role) => {
    if (role === 'pastor') return bad(`목회자는 팀에 ${PASTOR_MAX}명까지예요`);
    const cap = planOf(t).members, l = await leaderOf();
    if (l) await notify(t.id, [l.user_id], 'invite.full', t.id,
      { title: `${t.name} 정원(${cap}명)이 찼어요`, body: '누군가 초대 링크로 들어오려다 막혔어요', link: '#/team', actionable: true });
    return new HttpError(402, 'plan_limit', `${t.name}은 지금 ${cap}명까지예요. 인도자에게 알려 주세요`);
  };
  // 비활성이던 사람이 다시 들어오면 원래 역할로 되살린다 (초대 링크의 역할이 아니라).
  // 새로 들어올 때와 같은 자리 검사를 하고, 인도자에게도 알린다 (F41·F42)
  if (already) {
    if (already.active === false) {
      const back = await seated(t.id, t, `update members set name=$4, active=true, deactivated_at=null where team_id=$1 and user_id=$3
          and not active and ${seatOk('role')} returning 1`, [uid, name]);
      if (back.length) {
        await audit(t.id, uid, 'member.rejoin', uid, {});
        const l = await leaderOf();
        if (l && l.user_id !== uid) await notify(t.id, [l.user_id], 'member.join', uid,
          { title: `${josa(name, '이', '가')} 팀에 다시 들어왔어요`, link: '#/team' });
      } else if (!(await one('select 1 from members where team_id=$1 and user_id=$2 and active', [t.id, uid]))) throw await full(already.role);
      // (두 번 눌러 먼저 간 요청이 이미 되살렸으면 그대로 성공)
    } else await q('update members set name=$3 where team_id=$1 and user_id=$2', [t.id, uid, name]);
    await q('update users set display_name=$2 where id=$1', [uid, name]);
    return viewOf(await membership(uid, t.id));
  }
  const pastor = inv.role === 'pastor';
  const sessions = pastor ? [] : (strList(body.sessions) || [pickSession(t, str(body.session, 40))]).filter(Boolean);
  const session = pastor ? '' : (sessions[0] || pickSession(t, ''));
  const ins = await seated(t.id, t, `insert into members(user_id, team_id, name, session, sessions, role)
      select $3::uuid, $1::uuid, $4::text, $5::text, $6::text[], $7::text where ${seatOk('$7::text')}
      on conflict (user_id, team_id) do nothing returning 1`, [uid, name, session, sessions, inv.role]);
  if (!ins.length) {
    // 가입을 두 번 눌러 먼저 간 요청이 이미 넣었으면 그대로 성공이다 (전에는 500)
    if (await one('select 1 from members where team_id=$1 and user_id=$2 and active', [t.id, uid])) return viewOf(await membership(uid, t.id));
    throw await full(inv.role);
  }
  await q('update users set display_name=$2 where id=$1', [uid, name]);
  // 먼저 세지 않으면 동시에 들어올 때 1회용 링크가 두 번 쓰인다
  const claimed = await one(`update invites set uses = uses + 1 where id=$1
    and (max_uses is null or uses < max_uses) and revoked_at is null returning id`, [inv.id]);
  if (!claimed) { await q('delete from members where team_id=$1 and user_id=$2', [t.id, uid]); throw notFound('이 코드는 이미 다 쓰였어요'); }
  // 인도자에게 알림
  const leader = await one(`select user_id from members where team_id=$1 and role='leader' and active limit 1`, [t.id]);
  if (leader && leader.user_id !== uid) await notify(t.id, [leader.user_id], 'member.join', uid,
    { title: `${josa(name, '이', '가')} ${pastor ? '목회자로' : (session ? josa(session, '으로', '로') : '멤버로')} 들어왔어요`, link: '#/team' });
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
  const m0 = await requireMember(uid, teamId);
  const wantDraft = url.searchParams.get('draft') === '1';
  if (wantDraft && (await membership(uid, teamId)).role !== 'leader') throw forbidden('초안은 인도자만 볼 수 있어요');
  const row = wantDraft
    ? await one('select doc, 0 as version, updated_at as "updatedAt" from drafts where team_id=$1 and id=$2', [teamId, params.id])
    : await one('select doc, version, updated_at as "updatedAt" from services where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) throw notFound(wantDraft ? '초안이 없어요' : '발행된 콘티가 없어요');
  safeDoc(row.doc);   // 숫자 칸에 글자가 든 문서가 팀원 화면에 그대로 끼워지지 않게 (lib/docsafe.js)
  // 발행본 안에 들어 있는 말씀은 스냅샷이라 메모까지 담겨 있을 수 있다 → 보는 사람 권한으로 다시 거른다
  if (row.doc && row.doc.word) row.doc = { ...row.doc, word: wordView(row.doc.word, await membership(uid, teamId)) };
  // 발행 때 굳힌 곡 고정 메모도 GET /songs 와 같은 규칙으로 거른다. 예전 발행본에는 인도자의 '나만' 메모와
  // 모든 세션 메모가 그대로 들어 있어 멤버 누구나 받아 갔다
  if (row.doc && Array.isArray(row.doc.items)) row.doc = fixedView(row.doc, m0, uid);
  const ids = blobIdsOf(row.doc);
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  const w = await one('select word, updated_at as "updatedAt" from service_words where team_id=$1 and service_id=$2', [teamId, params.id]);
  const rd = await one('select rev from service_reads where team_id=$1 and service_id=$2 and user_id=$3', [teamId, params.id, uid]);
  return { doc: row.doc, version: row.version, updatedAt: row.updatedAt, blobs: await readUrls(blobs), word: wordView(w && w.word, await membership(uid, teamId)), readRev: rd ? rd.rev : 0 };
});
function fixedView(doc, m, uid) {
  const lead = !!(m && m.role === 'leader'), mine = new Set(m ? mySessions(m) : []);
  const ok = (n) => n && (n.layer === 'all' || (n.layer === 'mine' && n.authorId === uid) || (n.layer === 'session' && (lead || mine.has(n.session))));
  return { ...doc, items: doc.items.map((it) => (it && Array.isArray(it.fixedNotes) ? { ...it, fixedNotes: it.fixedNotes.filter(ok) } : it)) };
}
// 말씀 (§4.1): 본문·제목·한 줄은 항상 전체 공개, 목회자 메모는 memoPublic 이 아니면 인도자에게만
function wordView(w, m) {
  if (!w || !(w.passage || w.title || w.line)) return null;
  const canSeeMemo = w.memoPublic || (m && (m.role === 'leader' || m.role === 'pastor'));
  return { passage: w.passage || '', title: w.title || '', line: w.line || '', memo: canSeeMemo ? (w.memo || '') : '', memoPublic: !!w.memoPublic, from: w.from || null, receivedAt: w.receivedAt || null, updatedAt: w.updatedAt || null };
}
const wordKey = (w) => w ? [w.passage, w.title, w.line, w.memo, w.memoPublic ? 1 : 0].map((x) => String(x == null ? '' : x)).join('') : '';
// 말씀 칸마다 길이 한도. 넘치면 잘라 저장하지 않고 돌려보낸다 — 전에는 목사님 메모 뒷부분이 소리 없이
// 사라지고 링크는 '전달됐습니다'와 함께 닫혔다 (G23). 화면의 maxlength 와 같은 숫자다
const WORD_MAX = { passage: [60, '본문'], title: [40, '제목'], line: [80, '한 줄'], memo: [1000, '메모'] };
function wordFields(b) {
  const out = {};
  for (const [k, [max, label]] of Object.entries(WORD_MAX)) {
    const v = typeof b[k] === 'string' ? b[k].trim() : '';
    if (v.length > max) throw bad(`${josa(label, '은', '는')} ${max}자까지예요 (지금 ${v.length}자)`);
    out[k] = v;
  }
  return out;
}

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
  const f = wordFields(b);
  const prev = await one('select word from service_words where team_id=$1 and service_id=$2', [teamId, params.id]);
  const word = {
    ...f, memoPublic: !!b.memoPublic,
    from: { type: m.role === 'pastor' ? 'pastor' : 'leader', memberId: uid, name: m.mname || '' },
    receivedAt: (prev && prev.word && prev.word.receivedAt) || new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
  await q(`insert into service_words(team_id, service_id, word, updated_by, updated_at) values($1,$2,$3,$4,now())
           on conflict (team_id, service_id) do update set word=excluded.word, updated_by=excluded.updated_by, updated_at=now()`,
    [teamId, params.id, JSON.stringify(word), uid]);
  if (m.role === 'pastor') await ackWord(teamId, params.id);
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
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  const out = rows.map((r) => ({
    dateId: r.dateId, date: r.date, label: r.label, serviceId: r.serviceId,
    name: (r.serviceId && (svcNames[r.serviceId] || drafts[r.serviceId])) || `${mdOf(r.date)} ${r.label}`,
    past: r.date < today,
    word: wordView(r.word, m),
  }));
  // 사역 날짜가 아직 없는 콘티도 보여 준다. 안 그러면 그 예배는 말씀을 적을 곳이 없다
  if (m.role === 'leader') {
    const seen = new Set(out.map((x) => x.serviceId).filter(Boolean));
    const loose = await q(`select s.id, s.name, s.d as date, w.word
                             from (select id, coalesce(name,'')::text as name, date::text as d from services
                                    where team_id=$1 and date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                                   union all
                                   select id, coalesce(doc->>'name','')::text as name, (doc->>'date')::text as d
                                     from drafts where team_id=$1 and (doc->>'date') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') s
                             left join service_words w on w.team_id=$1 and w.service_id=s.id
                            where s.d::date >= current_date - interval '30 days' and s.d::date < current_date + interval '28 days'`, [teamId]);
    for (const r of loose) {
      if (seen.has(r.id)) continue;
      seen.add(r.id);
      out.push({ dateId: null, date: r.date, label: '', serviceId: r.id, name: r.name || `${mdOf(r.date)} 예배`, past: r.date < today, word: wordView(r.word, m) });
    }
    out.sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }
  return { services: out, role: m.role };
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
  const f = wordFields(body);
  const passage = f.passage; if (!passage) throw bad('본문을 적어 주세요');
  const word = {
    ...f, memoPublic: false,
    from: { type: 'link', name }, receivedAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
  };
  await q(`insert into service_words(team_id, service_id, word, updated_at) values($1,$2,$3,now())
           on conflict (team_id, service_id) do update set word=excluded.word, updated_at=now()`, [l.team_id, l.service_id, JSON.stringify(word)]);
  await q('update word_links set used_at=now() where token=$1', [token]);
  await ackWord(l.team_id, l.service_id);   // 링크로 보내 준 것도 목회자가 답한 것이다
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
  // 나간 목회자에게는 보내지 않는다 (주간 요청 크론과 같게, F116)
  const pastors = (await q(`select user_id from members where team_id=$1 and role='pastor' and active`, [teamId])).map((r) => r.user_id);
  if (!pastors.length) throw bad('팀에 목회자가 없어요. 링크로 보내 주세요');
  const svc = await one('select name from services where team_id=$1 and id=$2', [teamId, params.id]);
  // 그 예배가 지나면 할 일 카드도 내린다 (전에는 기한이 없어 영영 남았다)
  const sd = await one('select date::text as date from service_dates where team_id=$1 and service_id=$2 order by date desc limit 1', [teamId, params.id]);
  await notify(teamId, pastors, 'word.request', params.id, { title: '말씀을 다시 봐 주세요', body: (svc && svc.name) || '', link: '#/word', actionable: true,
    expiresAt: sd ? new Date(sd.date + 'T23:59:59+09:00') : null });
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
  const doc = safeDoc(body.doc);
  if (!doc || !Array.isArray(doc.items)) throw bad('발행본이 비어 있어요');
  const missing = blobIdsOf(doc);
  const have = missing.length ? (await q('select id from blobs where team_id=$1 and id = any($2::text[])', [teamId, missing])).map((r) => r.id) : [];
  const notUploaded = missing.filter((id) => !have.includes(id));
  if (notUploaded.length) throw bad('아직 올라가지 않은 파일이 있어요: ' + notUploaded.length + '개');
  const docJson = JSON.stringify(doc);
  const cur = await one(`select version, doc, (doc - 'stageLayouts') = ($3::jsonb - 'stageLayouts') as same from services where team_id=$1 and id=$2`,
    [teamId, params.id, docJson]);
  // 같은 판을 다시 보낸 것(서버엔 들어갔는데 응답을 못 받아 앱이 다시 올림)은 이미 된 것으로 받는다. 알림도 다시 안 보낸다.
  // 전에는 409 로 막혀 '서버에 못 올림'이 영영 남았다
  if (cur && cur.version === (+doc.version || 0) && cur.same) return { ok: true, version: cur.version, same: true };
  const conflict = (v) => new HttpError(409, 'version_conflict', `다른 기기에서 v${v}이 이미 발행됐어요. 새로고침으로 받은 뒤 다시 발행하세요`);
  if (cur && cur.version >= (+doc.version || 0)) throw conflict(cur.version);
  // 판 검사를 upsert 안에도 둔다. 위에서 읽고 따로 쓰면 같은 판을 동시에 발행한 두 기기가 모두 200 을 받고
  // 하나가 소리 없이 덮였다 (F43). 충돌 행은 잠긴 채 최신 판으로 다시 비교된다
  const wrote = await q(`insert into services(team_id, id, doc, version, name, date, updated_by, updated_at) values($1,$2,$3,$4,$5,$6,$7,now())
           on conflict (team_id, id) do update set
             doc = excluded.doc || jsonb_build_object('stageLayouts',
                     coalesce(services.doc->'stageLayouts','{}'::jsonb) || coalesce(excluded.doc->'stageLayouts','{}'::jsonb)),
             version=excluded.version, name=excluded.name, date=excluded.date, updated_by=excluded.updated_by, updated_at=now()
           where services.version < excluded.version
           returning version`,
    [teamId, params.id, docJson, +doc.version || 0, str(doc.name, 120), str(doc.date, 20), uid]);
  if (!wrote.length) throw conflict(((await one('select version from services where team_id=$1 and id=$2', [teamId, params.id])) || { version: +doc.version || 0 }).version);
  // §1 알림: publish(팀 전원, 발행자 제외) · note.updated(인도자의 글이 이전 발행과 다를 때)
  try {
    const version = +doc.version || 0, md = mdOf(doc.date), name = str(doc.name, 60) || '예배';
    const label = name.startsWith(md) ? name : `${md} ${name}`; // 이름 규칙에 이미 날짜가 들어 있으면 겹쳐 쓰지 않음
    const titles = doc.items.map((it) => str(it && it.title, 40)).filter(Boolean);
    const songs = titles.length ? (titles.length > 1 ? `${titles[0]} ~ ${titles[titles.length - 1]}` : titles[0]) : '곡 없음';
    // 바뀐 것이 있으면 그것을 알려 준다. 팀원이 알림만 보고도 뭘 다시 봐야 하는지 안다
    const chg = Array.isArray(doc.changes) ? doc.changes.map((c) => str(c && c.text, 60)).filter(Boolean) : [];
    const body = chg.length ? (chg.slice(0, 3).join(' · ') + (chg.length > 3 ? ` 외 ${chg.length - 3}` : '')) : songs;
    const to = await teamUserIds(teamId, { except: uid });
    await notify(teamId, to, 'publish', params.id, { title: `${label} 콘티 v${version}`, body, link: '#/view/' + params.id });
    const prevMsg = cur && cur.doc ? String(cur.doc.message || '') : '';
    const prevWord = cur && cur.doc ? wordKey(cur.doc.word) : '';
    if (cur && (String(doc.message || '') !== prevMsg || wordKey(doc.word) !== prevWord) && (String(doc.message || '').trim() || wordKey(doc.word)))
      await notify(teamId, to, 'note.updated', params.id, { title: `${label} 인도자의 글이 바뀌었어요`, body: String(doc.message).split('\n')[0], link: '#/view/' + params.id });
    await linkDate(teamId, params.id, doc.date, name);
  } catch (e) { console.error('notify publish', e); }
  try { await syncUsages(teamId, params.id, doc, uid); } catch (e) { console.error('usages', e); }
  // 다시 발행하며 빠진 파일(자른 악보의 옛 판, 지운 곡)은 팀 어디에서도 안 쓰면 지운다 (F117)
  if (cur) {
    const now = new Set(blobIdsOf(doc));
    try { await freeBlobs(teamId, blobIdsOf(cur.doc).filter((id) => !now.has(id))); } catch (e) { console.error('free blobs', e); }
  }
  return { ok: true, version: +doc.version || 0 };
});

// 사용 이력은 발행본에서만 만든다 (명세 A.1.3). 다시 발행하면 이 예배 줄을 지우고 새로 쓴다
// 통계가 바뀐 곡은 touched_at 을 올려 곡 목록 since 로 받아지게 한다 (빠진 곡도, 새로 든 곡도)
const dropUsages = (teamId, serviceId) => q(`with d as (delete from song_usages where team_id=$1 and service_id=$2 returning song_id)
  update songs set touched_at=now() where id in (select song_id from d)`, [teamId, serviceId]);
async function syncUsages(teamId, serviceId, doc, uid) {
  await dropUsages(teamId, serviceId);
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
    const ok = await one('select id from songs where id=$1 and team_id=$2 and deleted_at is null', [songId, teamId]);
    if (!ok) {
      // 합쳐졌으면 편곡을 따라 남은 곡으로 옮겨 붙인다
      const a2 = str(it.arrId, 64) ? await one('select song_id from arrangements where id=$1 and team_id=$2 and deleted_at is null', [it.arrId, teamId]) : null;
      if (!a2) continue;
      songId = a2.song_id;
    }
    await q(`insert into song_usages(team_id, song_id, arrangement_id, service_id, service_date, service_name, position, is_application, key_used, via_medley, leader_id)
             values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) on conflict (song_id, service_id) do update set
               arrangement_id=excluded.arrangement_id, service_date=excluded.service_date, service_name=excluded.service_name,
               position=excluded.position, is_application=excluded.is_application, key_used=excluded.key_used`,
      [teamId, songId, str(it.arrId, 64) || null, serviceId, date, str(doc.name, 120), i, i === last, str(it.key, 12), !!it.medley, uid]);
  }
  await q('update songs set touched_at=now() where id in (select song_id from song_usages where team_id=$1 and service_id=$2)', [teamId, serviceId]);
}

on('PUT', '/services/:id/stage-layout', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const dev = str(body.device, 20);
  if (!/^[a-z-]{3,20}$/.test(dev)) throw bad('기기 종류가 이상해요');
  const val = body.layout && typeof body.layout === 'object' ? body.layout : null;
  const sql = val
    ? `update services set doc = doc || jsonb_build_object('stageLayouts',
         coalesce(doc->'stageLayouts','{}'::jsonb) || jsonb_build_object($3::text, $4::jsonb)) where team_id=$1 and id=$2`
    : `update services set doc = doc || jsonb_build_object('stageLayouts',
         coalesce(doc->'stageLayouts','{}'::jsonb) - $3::text) where team_id=$1 and id=$2`;
  // 발행본이 없으면(초안뿐) 바뀐 줄이 없다. 전에는 그래도 ok 를 돌려줘 '저장했어요'가 떴다
  const done = await q(sql + ' returning id', val ? [teamId, params.id, dev, JSON.stringify(val)] : [teamId, params.id, dev]);
  if (!done.length) throw notFound('발행한 콘티에만 추천 조판을 저장할 수 있어요');
  return { ok: true };
});
// 추천 조판만 가볍게 (무대를 열 때). 발행 뒤에 붙는 일이 많아 버전 비교로는 안 내려간다
on('GET', '/services/:id/stage-layout', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const row = await one(`select doc->'stageLayouts' as "stageLayouts" from services where team_id=$1 and id=$2`, [teamId, params.id]);
  if (!row) throw notFound('발행된 콘티가 없어요');
  return { stageLayouts: row.stageLayouts || null };
});

on('GET', '/services/:id/draft', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const row = await one('select doc, updated_at as "updatedAt" from drafts where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) return { doc: null };
  safeDoc(row.doc);
  const ids = blobIdsOf(row.doc);
  const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
  return { doc: row.doc, updatedAt: row.updatedAt, blobs: await readUrls(blobs) };
});
on('PUT', '/services/:id/draft', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  const doc = safeDoc(body.doc);
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
  // 발행본뿐 아니라 초안에만 있던 파일, 이 콘티의 녹음(잠근 것 포함)도 같이 지운다.
  // 콘티가 없어지면 볼 길이 없는데 저장소에 영영 남았다 (F117)
  const pub = await q('delete from services where team_id=$1 and id=$2 returning doc', [teamId, params.id]);
  const dr = await q('delete from drafts where team_id=$1 and id=$2 returning doc', [teamId, params.id]);
  const rh = await q('delete from rehearsals where team_id=$1 and service_id=$2 returning blob_id', [teamId, params.id]);
  await q('delete from notes where team_id=$1 and service_id=$2', [teamId, params.id]);
  await dropUsages(teamId, params.id);   // 이력은 발행본에서만 나온다
  // 이 콘티 때문에 생긴 날짜는 같이 지운다. 안 그러면 콘티를 지워도 홈의 D-day 카드에 남아
  // '콘티 만들기'를 누르면 되살아난 것처럼 보인다
  await q(`delete from service_dates where team_id=$1 and service_id=$2 and source='service'`, [teamId, params.id]);
  // 인도자가 직접 연 날짜나 반복 일정은 그대로 두되, 자동 생성이 같은 날짜에 새 콘티를 만들어
  // 되살리지 않게 막는다. 손으로 새 콘티를 만들어 붙이면 auto_skip 은 풀린다 (linkDate)
  await q('update service_dates set service_id=null, auto_skip=true where team_id=$1 and service_id=$2', [teamId, params.id]);
  const mine = [...pub, ...dr].flatMap((r) => blobIdsOf(r.doc)).concat(rh.map((r) => r.blob_id).filter(Boolean));
  const freed = await freeBlobs(teamId, [...new Set(mine)]);
  return { ok: true, freedFiles: freed };
});
// 이 id 들 가운데 팀 어디에서도 안 쓰는 것만 지운다 (blobs 행과 저장소 파일 둘 다). 지운 개수를 돌려준다
async function freeBlobs(teamId, ids) {
  if (!ids.length) return 0;
  const used = await teamBlobRefs(teamId);
  const orphan = ids.filter((id) => !used.has(id));
  if (!orphan.length) return 0;
  const rows = await q('delete from blobs where team_id=$1 and id = any($2::text[]) returning url', [teamId, orphan]);
  await delBlobs(rows.map((r) => r.url));
  return rows.length;
}
// 팀 안에서 아직 쓰이는 파일 id 전부 — 콘티·초안뿐 아니라 라이브러리·녹음까지 봐야 남의 파일을 지우지 않는다
async function teamBlobRefs(teamId) {
  const used = new Set();
  for (const r of await q('select doc from services where team_id=$1', [teamId])) blobIdsOf(r.doc).forEach((id) => used.add(id));
  for (const r of await q('select doc from drafts where team_id=$1', [teamId])) blobIdsOf(r.doc).forEach((id) => used.add(id));
  for (const r of await q('select song from library where team_id=$1 and deleted_at is null', [teamId])) songBlobIds(r.song).forEach((id) => used.add(id));
  for (const r of await q('select pieces, media from arrangements where team_id=$1 and deleted_at is null', [teamId])) arrBlobIds(r).forEach((id) => used.add(id));
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
// 마커 라벨 길이. 앱의 라벨 입력칸(labelPicker)도 같은 값으로 막는다 — 고정 메모는 라벨이 정확히 같아야 붙는다
const MARKER_LABEL_MAX = 40;
// ♩= 는 정수 칸이다. 72.5 나 아주 큰 수가 오면 저장 전체가 500 으로 날아갔다 (키·송폼까지 같이)
const bpmOf = (v) => { const n = Math.round(+v); return Number.isFinite(n) && n > 0 ? Math.min(400, Math.max(20, n)) : null; };
const arrBlobIds = (a) => {
  const ids = new Set();
  for (const p of (a && a.pieces) || []) if (p && p.blob) ids.add(p.blob);
  for (const m of (a && a.media) || []) if (m && m.blob) ids.add(m.blob);
  return [...ids];
};
const arrView = (a) => safeItem({
  id: a.id, songId: a.song_id, name: a.name, isDefault: a.is_default,
  medleySongIds: a.medley_song_ids || [], key: a.key, mod: a.mod, form: a.form,
  bpm: a.bpm, songNote: a.song_note, pieces: a.pieces || [], media: a.media || [],
  chart: a.chart || null, score: a.score || null, updatedAt: a.updated_at,
});
const songView = (s, extra) => ({
  id: s.id, title: s.title, aliases: s.aliases || [], artist: s.artist, origKey: s.orig_key,
  firstLine: s.first_line, tags: s.tags || [], tempo: s.tempo, archived: s.archived, folder: s.folder || '',
  notDupOf: s.not_dup_of || [], updatedAt: s.updated_at,
  fromTeam: s.from_team || null, fromAt: s.from_at || null,
  titleNorm: s.title_norm, titleCho: s.title_cho, ...(extra || {}),
});
// 파생값 (명세 A.1.3). 목록에 붙여 내려보낸다. ids 를 주면 그 곡들만
// 날짜는 글자('2025-09-24')로 받는다. date 를 그대로 받으면 드라이버가 Date 로 바꿔서 String(d) 가
// 'Tue Sep 23' 이 됐고(연도 없음) '작년 이맘때' 가 늘 비었다. 서버 시간대에 따라 하루 밀리지도 않는다
async function songStats(teamId, ids) {
  if (ids && !ids.length) return {};
  const only = ids ? ' and song_id = any($2::uuid[])' : '', args = ids ? [teamId, ids] : [teamId];
  const rows = await q(`select song_id, count(*)::int as n, max(service_date)::text as last, min(service_date)::text as first,
                        array_remove(array_agg(service_date::text order by service_date desc), null) as dates
                        from song_usages where team_id=$1${only} group by song_id`, args);
  const keys = await q(`select song_id, key_used, count(*)::int as n from song_usages
                        where team_id=$1${only} and key_used<>'' group by song_id, key_used`, args);
  const out = {};
  for (const r of rows) out[r.song_id] = { useCount: r.n, lastUsed: r.last, firstUsed: r.first,
    usedDates: (r.dates || []).slice(0, 40), keyStats: {} };
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

// 곡 목록을 통째로 만드는 일은 무겁다 — 800곡 팀이면 편곡 JSON 수 MB 를 객체로 풀었다가 다시 글자로 만든다(한 번에 수십 MB).
// Cloud Run 은 한 인스턴스(512MB)에 요청을 80개까지 몰아 주므로, 발행 푸시에 팀원 열 명이 한꺼번에 앱을 열면 힙이 넘쳐
// 인스턴스가 죽었다 — 그 인스턴스에 있던 다른 팀 요청까지 함께. 무거운 것은 동시에 둘까지만 만들고 나머지는 줄을 선다
const HEAVY = { busy: 0, max: 2, wait: [] };
async function heavySlot() {
  if (HEAVY.busy < HEAVY.max) HEAVY.busy++;
  else await new Promise((r) => HEAVY.wait.push(r));   // 앞 사람의 자리를 그대로 넘겨받는다 (busy 는 그대로)
  let done = false;
  return () => { if (done) return; done = true; const next = HEAVY.wait.shift(); if (next) next(); else HEAVY.busy--; };
}
// 목록 (전원). 검색은 브라우저가 하고 서버는 팀의 곡을 준다. since 가 있으면 그 뒤에 바뀐 곡만 —
// 편곡·고정 메모·파일 주소·사용 통계도 그 곡들 것만 싣는다 (전에는 since 여도 팀 전체를 읽어 매번 통째와 같은 일을 했다).
// 목록에 보이는 것이 바뀌면 songs.updated_at(고친 것) 이나 songs.touched_at(사용 이력·세션 이름처럼 '최근 고친' 순서는
// 건드리면 안 되는 것) 을 올려야 since 로 받아진다
on('GET', '/songs', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const me0 = await requireMember(uid, teamId);
  let since = str(url.searchParams.get('since'), 40);
  if (since && isNaN(Date.parse(since))) since = '';
  // 읽기 전에 잡아야 그 사이 바뀐 것을 다음에 받는다. 몇 초 앞당겨 둔다 — 지금 막 쓰는 중인(아직 커밋 전) 줄은
  // updated_at 이 이 시각보다 앞선 채로 나중에 보이게 되어, 딱 지금으로 잡으면 다음 since 에서 영영 빠진다
  const now0 = (await one(`select now() - interval '5 seconds' as t`)).t;
  const songs = since
    ? await q('select * from songs where team_id=$1 and (updated_at > $2 or touched_at > $2) order by updated_at asc', [teamId, since])
    : await q('select * from songs where team_id=$1 order by updated_at asc', [teamId]);
  const release = !since || songs.length > 50 ? await heavySlot() : null;
  try {
    const sids = since ? songs.filter((s) => !s.deleted_at).map((s) => s.id) : null;
    const arrs = !sids ? await q('select * from arrangements where team_id=$1 and deleted_at is null order by is_default desc, created_at asc', [teamId])
      : sids.length ? await q('select * from arrangements where team_id=$1 and song_id = any($2::uuid[]) and deleted_at is null order by is_default desc, created_at asc', [teamId, sids])
      : [];
    const stats = await songStats(teamId, sids);
    // 남의 '나만' 메모는 내려보내지 않는다. 세션 메모는 그 세션 사람과 인도자만
    const fixed = arrs.length ? await q(`select id, arrangement_id as "arrangementId", marker_label as "markerLabel", layer, session,
        author_id as "authorId", author_name as "authorName", text from arrangement_notes
        where arrangement_id = any($1::uuid[]) and (layer='all' or (layer='mine' and author_id=$2)
          or (layer='session' and ($3 or session = any($4::text[]))))`,
      [arrs.map((a) => a.id), uid, me0.role === 'leader', mySessions(me0)]) : [];
    const notesBy = {};
    for (const n of fixed) (notesBy[n.arrangementId] = notesBy[n.arrangementId] || []).push(n);
    const byId = {};
    for (const a of arrs) (byId[a.song_id] = byId[a.song_id] || []).push({ ...arrView(a), notes: notesBy[a.id] || [] });
    const ids = [...new Set(arrs.flatMap(arrBlobIds))];
    const blobs = ids.length ? await q('select id, url, pathname from blobs where team_id=$1 and id = any($2::text[])', [teamId, ids]) : [];
    return {
      songs: songs.filter((s) => !s.deleted_at).map((s) => songView(s, { arrangements: byId[s.id] || [], ...(stats[s.id] || { useCount: 0, lastUsed: null, firstUsed: null, keyStats: {} }) })),
      deleted: songs.filter((s) => s.deleted_at).map((s) => s.id),
      now: now0,
      blobs: await readUrls(blobs),
    };
  } finally { if (release) release(); }
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
  const usages = await q(`select service_id as "serviceId", service_date::text as "serviceDate", service_name as "serviceName",
      position, is_application as "isApplication", key_used as "keyUsed", via_medley as "viaMedley", arrangement_id as "arrangementId"
      from song_usages where team_id=$1 and song_id=$2 order by service_date desc nulls last`, [teamId, s.id]);
  const me1 = await membership(uid, teamId);
  const notes = await q(`select id, arrangement_id as "arrangementId", marker_label as "markerLabel", layer, session,
      author_id as "authorId", author_name as "authorName", text, created_at as "createdAt"
      from arrangement_notes where arrangement_id = any($1::uuid[])
        and (layer='all' or (layer='mine' and author_id=$2) or (layer='session' and ($3 or session = any($4::text[]))))
      order by created_at asc`, [arrs.map((a) => a.id), uid, me1.role === 'leader', mySessions(me1)]);
  const stats = (await songStats(teamId, [s.id]))[s.id] || { useCount: 0, lastUsed: null, firstUsed: null, keyStats: {} };
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
  // 기기가 정한 id(uuid)가 오면 그 id 로 만든다. 응답을 못 받아 다시 보내거나 두 번 눌러도 곡은 하나다
  const cid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(body.id || '')) ? String(body.id).toLowerCase() : null;
  const had = cid ? await one('select * from songs where id=$1', [cid]) : null;
  if (had && (String(had.team_id) !== String(teamId).toLowerCase() || had.deleted_at)) throw new HttpError(409, 'song_id_taken', '곡을 다시 만들어 주세요');
  if (ENFORCE_PLAN && !had) {
    const n = await one('select count(*)::int as n from songs where team_id=$1 and not archived and deleted_at is null', [teamId]);
    const cap = planOf(m).songs;
    if (n.n >= cap) throw new HttpError(402, 'plan_limit', `무료는 ${cap}곡까지예요. 안 부르는 곡을 보관하면 자리가 생겨요`);
  }
  const tn = normSong(title);
  const s = had || await one(`insert into songs(id, team_id, title, title_norm, title_cho, artist, orig_key, tempo, tags, aliases, first_line, folder, created_by)
    values(coalesce($13::uuid, gen_random_uuid()),$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) on conflict (id) do nothing returning *`,
    [teamId, title, tn, choSong(tn), str(body.artist, 60), str(body.origKey, 12), str(body.tempo, 8),
     strList(body.tags) || [], strList(body.aliases) || [], str(body.firstLine, 200), str(body.folder, 30).trim(), uid, cid])
    || await one('select * from songs where id=$1 and team_id=$2 and deleted_at is null', [cid, teamId]);   // 같은 id 가 동시에 두 번
  if (!s) throw new HttpError(409, 'song_id_taken', '곡을 다시 만들어 주세요');
  // 기본 편곡도 한 번만. 같은 곡으로 동시에 두 번 오면 먼저 넣은 것을 쓴다 (기본 편곡은 곡마다 하나 — 유일 인덱스)
  const firstArr = () => one('select * from arrangements where song_id=$1 and deleted_at is null order by is_default desc, created_at asc limit 1', [s.id]);
  const a = (had && await firstArr()) || await one(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, song_note, pieces, media, chart, score)
    values($1,$2,'기본',true,$3,$4,$5,$6,$7,$8,$9,$10) on conflict do nothing returning *`,
    [s.id, teamId, str(body.key, 12), str(body.mod, 12), str(body.form, 500), str(body.songNote, 300),
     JSON.stringify(Array.isArray(body.pieces) ? body.pieces : []), JSON.stringify(Array.isArray(body.media) ? body.media : []),
     body.chart ? JSON.stringify(body.chart) : null, body.score ? JSON.stringify(body.score) : null])
    || await firstArr();
  const stats = had ? ((await songStats(teamId))[s.id] || {}) : {};
  return { song: songView(s, { arrangements: [arrView(a)], useCount: 0, lastUsed: null, firstUsed: null, keyStats: {}, ...stats }) };
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
  if (body.folder !== undefined) put('folder', str(body.folder, 30).trim());
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
  await q('update arrangements set deleted_at=now() where song_id=$1 and deleted_at is null', [params.id]);
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
  await q('update songs set updated_at=now() where id=$1', [s.id]);   // 다른 기기가 since 로 새 편곡을 받게
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
  safeItem(body);   // pieces·media·score 의 숫자 칸 (lib/docsafe.js)
  if (body.name !== undefined) put('name', str(body.name, 40) || '기본');
  if (body.key !== undefined) put('key', str(body.key, 12));
  if (body.mod !== undefined) put('mod', str(body.mod, 12));
  if (body.form !== undefined) put('form', str(body.form, 500));
  if (body.songNote !== undefined) put('song_note', str(body.songNote, 300));
  if (body.bpm !== undefined) put('bpm', bpmOf(body.bpm));
  if (body.pieces !== undefined) put('pieces', JSON.stringify(Array.isArray(body.pieces) ? body.pieces : []));
  if (body.media !== undefined) put('media', JSON.stringify(Array.isArray(body.media) ? body.media : []));
  if (body.chart !== undefined) put('chart', body.chart ? JSON.stringify(body.chart) : null);
  if (body.score !== undefined) put('score', body.score ? JSON.stringify(body.score) : null);
  if (set.length) { set.push('updated_at=now()'); await q(`update arrangements set ${set.join(', ')} where id=$1`, vals); }
  // 기본 편곡 바꾸기는 유일 인덱스 때문에 순서가 있다: 내리고 올린다
  // 하나씩 하면 중간에 끊겼을 때 기본 편곡이 없는 곡이 남는다. 한 문장으로.
  // 다만 'is_default = (id = $2)' 한 번으로는 안 된다 — 유일 인덱스는 줄마다 바로 검사해서, 올릴 편곡을
  // 옛 기본보다 먼저 만나면(옛 기본을 한 번 고치면 뒤로 간다) 충돌로 500 이었다.
  // 내리는 쪽을 WITH 로 먼저 끝내고(아래 count 가 그 결과를 기다린다) 올린다
  if (body.isDefault === true && !a.is_default)
    await q(`with off as (update arrangements set is_default=false where song_id=$1 and is_default and id<>$2 returning id)
             update arrangements set is_default=true where id=$2 and deleted_at is null and (select count(*) from off) >= 0`,
      [a.song_id, params.id]);
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
  if (layer === 'session' && m.role !== 'leader' && !(m.role === 'session_lead' && mySessions(m).includes(session)))
    throw forbidden('세션이 함께 보는 고정 메모는 인도자와 세션 리더만 남길 수 있어요');
  if (m.role === 'pastor' && !(await teamSettings(teamId)).pastorCanMemo) throw forbidden('목회자 메모는 팀 설정에서 켜야 해요');
  // 인도자 메모('전체' 층)도 대상 세션을 고를 수 있다 (드럼에게만 '쉬기'). 전에는 층이 all 이면 대상을 버려서
  // 보컬까지 모두에게 '전체'로 보였다. 팀에 없는 세션이면 아무에게도 안 보이니 받지 않는다
  if (layer === 'all' && session && !(Array.isArray(m.sessions) ? m.sessions : []).includes(session))
    throw bad('팀에 없는 세션이에요. 새로고침한 뒤 다시 골라 주세요');
  const text = str(body.text, 60);
  if (!text) throw bad('메모를 적어 주세요');
  // 라벨은 마커와 정확히 같아야 붙는다(A≠A1). 잘라 저장하면 'Pre-Chorus' 가 'Pre-Chor' 가 되어 어디에도 안 보였다.
  // 자르지 않고, 너무 길면 거절한다 (라벨 입력칸도 같은 길이로 막았다)
  const label = typeof body.markerLabel === 'string' ? body.markerLabel.trim() : '';
  if (label.length > MARKER_LABEL_MAX) throw bad('마커 라벨이 너무 길어요');
  const r = await one(`insert into arrangement_notes(arrangement_id, team_id, marker_label, layer, session, author_id, author_name, text)
    values($1,$2,$3,$4,$5,$6,$7,$8) returning *`,
    [params.id, teamId, label || 'A', layer, layer === 'mine' ? null : session, uid, m.mname || '', text]);
  await q('update songs set updated_at=now() where id=$1', [a.song_id]);
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
  await q(`update songs set updated_at=now() where id=(select song_id from arrangements where id=$1)`, [n.arrangement_id]);
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

/* ---------- 곡 공유 코드 (명세 A.7) ---------- */
// 파일은 담지 않는다. 악보 이미지·녹음·채보 결과는 코드에 없다.
// 받는 쪽은 곡·편곡이 생기고 악보는 빈 상태다. 자기 악보를 올리고 마커를 찍으면
// 라벨이 같은 고정 메모가 붙는다 (§A.6.3 규칙 그대로).
const SHARE_ALPHA = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';   // 헷갈리는 I O 0 1 은 뺐다
function shareCode() {
  const b = randomBytes(6);
  let out = ''; for (let i = 0; i < 6; i++) out += SHARE_ALPHA[b[i] % SHARE_ALPHA.length];
  return out;
}
const ytOnly = (m) => m && m.type === 'youtube' && m.url;
// 곡 하나를 코드에 담을 모양으로 (파일 없이)
async function sharePayloadOf(teamId, songId, arrId) {
  const s = await one('select * from songs where id=$1 and team_id=$2 and deleted_at is null', [songId, teamId]);
  if (!s) throw notFound('그 곡이 없어요');
  const arrs = await q('select * from arrangements where song_id=$1 and deleted_at is null order by is_default desc, created_at asc', [s.id]);
  const a = (arrId ? arrs.find((x) => x.id === arrId) : null) || arrs[0];
  if (!a) throw bad('편곡이 없어요');
  const notes = await q(`select marker_label as "label", session, text from arrangement_notes
                         where arrangement_id=$1 and layer='all' order by created_at asc`, [a.id]);
  return {
    title: s.title, aliases: s.aliases || [], artist: s.artist || '', origKey: s.orig_key || '',
    tempo: s.tempo || '', tags: s.tags || [],
    arr: { name: a.name || '기본', key: a.key || '', mod: a.mod || '', form: a.form || '',
      bpm: a.bpm || null, songNote: a.song_note || '',
      notes: notes.map((n) => ({ label: n.label, text: n.text, ...(n.session ? { session: n.session } : {}) })),
      media: (a.media || []).filter(ytOnly).map((m) => ({ type: 'youtube', url: m.url, name: m.name || '',
        start: +m.start || 0, end: +m.end || 0, sessions: Array.isArray(m.sessions) ? m.sessions : [] })) },
  };
}
// 만들기 전에 무엇이 담기고 무엇이 안 담기는지 보여 준다
on('GET', '/songs/:id/share-preview', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const payload = await sharePayloadOf(teamId, params.id, str(url.searchParams.get('arr'), 64));
  const a = await one('select pieces, media, chart, score from arrangements where song_id=$1 and deleted_at is null order by is_default desc limit 1', [params.id]);
  return { song: payload, left: {
    pieces: ((a && a.pieces) || []).length, audio: ((a && a.media) || []).filter((m) => m && m.type !== 'youtube').length,
    chart: !!(a && a.chart), score: !!(a && a.score) } };
});
on('POST', '/share', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId, 'leader');
  const ids = (Array.isArray(body.songIds) ? body.songIds : [str(body.songId, 64)]).filter(Boolean).slice(0, 30);
  if (!ids.length) throw bad('보낼 곡을 골라 주세요');
  if (ENFORCE_PLAN && !planOf(m).shareSend) throw new HttpError(402, 'plan_limit', '곡 코드 만들기는 Pro 예요');
  if (ENFORCE_PLAN && ids.length > 1 && !planOf(m).shareSend) throw new HttpError(402, 'plan_limit', '묶음 코드는 Pro 예요');
  const songs = [];
  for (const id of ids) songs.push(await sharePayloadOf(teamId, id, ids.length === 1 ? str(body.arrId, 64) : ''));
  const days = [7, 30, 90].includes(+body.days) ? +body.days : 30;
  const payload = { v: 1, kind: ids.length > 1 ? 'bundle' : 'song', songs,
    from: { team: m.name, at: new Date().toISOString().slice(0, 10) } };
  let code = shareCode();
  for (let i = 0; i < 5 && await one('select code from share_codes where code=$1', [code]); i++) code = shareCode();
  await q(`insert into share_codes(code, team_id, created_by, payload, kind, max_uses, expires_at)
           values($1,$2,$3,$4,$5,$6, now() + ($7 || ' days')::interval)`,
    [code, teamId, uid, JSON.stringify(payload), payload.kind, +body.maxUses > 0 ? Math.min(50, +body.maxUses) : null, String(days)]);
  await audit(teamId, uid, 'share.create', code, { songs: ids.length });
  return { code, kind: payload.kind, songs: songs.length, expiresInDays: days };
});
on('GET', '/shares', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const rows = await q(`select code, kind, uses, max_uses as "maxUses", expires_at as "expiresAt",
     revoked_at as "revokedAt", created_at as "createdAt", payload from share_codes
     where team_id=$1 order by created_at desc limit 30`, [teamId]);
  return { shares: rows.map((r) => ({ ...r, titles: ((r.payload || {}).songs || []).map((s) => s.title), payload: undefined })) };
});
on('DELETE', '/share/:code', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId, 'leader');
  const r = await q('update share_codes set revoked_at=now() where code=$1 and team_id=$2 and revoked_at is null returning code',
    [String(params.code || '').toUpperCase(), teamId]);
  if (!r.length) throw notFound('그 코드가 없어요');
  return { ok: true };
});
// 코드는 6자라 마구 넣어 보면 남의 팀 곡을 긁을 수 있다. 틀린 시도를 세어 막는다.
// 미리보기와 담기가 같은 셈을 쓴다 — 전에는 담기(take)에 셈이 없어서 미리보기가 잠겨도 담기로 계속 두드릴 수 있었다
async function shareGuard(uid) {
  const key = 'share|' + uid;
  const la = await one('select n, last from login_attempts where username=$1', [key]).catch(() => null);
  if (la && la.n >= 20 && Date.now() - new Date(la.last).getTime() < 60 * 60 * 1000)
    throw new HttpError(429, 'too_many', '코드를 너무 많이 시도했어요. 한 시간 뒤에 다시 해 주세요');
  return async () => { await q(`insert into login_attempts(username, n, last) values($1,1,now())
    on conflict (username) do update set n = case when login_attempts.last < now() - interval '1 hour' then 1 else login_attempts.n + 1 end, last = now()`, [key]).catch(() => {}); };
}
// 미리보기 (받는 쪽). 담기 전에 무엇이 들어오는지 본다
on('GET', '/share/:code', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  const miss = await shareGuard(uid);
  const r = await one('select * from share_codes where code=$1', [String(params.code || '').toUpperCase()]);
  if (!r) { await miss(); throw notFound('그런 코드가 없어요'); }
  if (r.revoked_at) throw notFound('이 코드는 회수됐어요');
  if (new Date(r.expires_at) < new Date()) throw notFound('이 코드는 기한이 지났어요');
  if (r.max_uses != null && r.uses >= r.max_uses) throw notFound('이 코드는 이미 다 쓰였어요');
  return { payload: r.payload, uses: r.uses, maxUses: r.max_uses, expiresAt: r.expires_at };
});
// 담기: 곡·편곡·고정 메모·유튜브 링크를 내 팀에 만든다
on('POST', '/share/:code/take', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId, 'leader');
  const miss = await shareGuard(uid);
  const code = String(params.code || '').toUpperCase();
  // 먼저 한 자리를 선점한다. 검사하고 나중에 세면 '한 팀만' 코드가 여러 팀에 나간다
  const claim = await one(`update share_codes set uses = uses + 1 where code=$1 and revoked_at is null
    and expires_at > now() and (max_uses is null or uses < max_uses) returning payload`, [code]);
  if (!claim) {
    const exists = await one('select code from share_codes where code=$1', [code]);
    if (!exists) { await miss(); throw notFound('그런 코드가 없어요'); }
    throw notFound('이 코드는 더 쓸 수 없어요');
  }
  try { return await takeSharePayload(teamId, uid, m, claim.payload); }
  catch (e) { await q('update share_codes set uses = greatest(uses - 1, 0) where code=$1', [code]).catch(() => {}); throw e; }
});
// 자립형 코드(1414:…)는 브라우저가 풀어서 이 자리로 보낸다. 서버는 저장하지 않는다
on('POST', '/share/take', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId, 'leader');
  const p = body.payload;
  if (!p || !Array.isArray(p.songs) || !p.songs.length) throw bad('코드를 읽지 못했어요');
  if (p.songs.length > 30) throw bad('한 번에 30곡까지예요');
  if (JSON.stringify(p).length > 400e3) throw new HttpError(413, 'too_large', '코드가 너무 커요');
  return await takeSharePayload(teamId, uid, m, p);
});
async function takeSharePayload(teamId, uid, member, payload) {
  const from = str(payload.from && payload.from.team, 40);
  const teamSess = (await one('select sessions from teams where id=$1', [teamId])).sessions || [];
  const out = [];
  if (ENFORCE_PLAN) {
    const n = await one('select count(*)::int as n from songs where team_id=$1 and not archived and deleted_at is null', [teamId]);
    const cap = planOf(member).songs;
    if (n.n + payload.songs.length > cap) throw new HttpError(402, 'plan_limit', `무료는 ${cap}곡까지예요. 안 부르는 곡을 보관하면 자리가 생겨요`);
  }
  for (const sp of payload.songs.slice(0, 30)) {
    const title = str(sp.title, 120) || '(제목 없음)';
    const tn = normSong(title);
    const s = await one(`insert into songs(team_id, title, title_norm, title_cho, aliases, artist, orig_key, tempo, tags, created_by, from_team, from_at)
      values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,now()) returning *`,
      [teamId, title, tn, choSong(tn), (strList(sp.aliases) || []), str(sp.artist, 60), str(sp.origKey, 12),
       str(sp.tempo, 8), (strList(sp.tags) || []), uid, from || null]);
    const ar = sp.arr || {};
    const media = (Array.isArray(ar.media) ? ar.media : []).filter(ytOnly).slice(0, 12).map((x) => ({
      id: randomToken(8), type: 'youtube', url: str(x.url, 300), name: str(x.name, 120),
      start: +x.start || 0, end: +x.end || 0,
      // 받는 팀에 없는 세션 태그는 버린다. 남기면 아무에게도 안 보인다
      sessions: (strList(x.sessions) || []).filter((v) => teamSess.includes(v)), notes: [] }));
    const a = await one(`insert into arrangements(song_id, team_id, name, is_default, key, mod, form, bpm, song_note, pieces, media)
      values($1,$2,$3,true,$4,$5,$6,$7,$8,'[]',$9) returning *`,
      [s.id, teamId, str(ar.name, 40) || '기본', str(ar.key, 12), str(ar.mod, 12), str(ar.form, 500),
       bpmOf(ar.bpm), str(ar.songNote, 300), JSON.stringify(media)]);
    for (const n of (Array.isArray(ar.notes) ? ar.notes : []).slice(0, 40)) {
      const t0 = str(n && n.text, 60); if (!t0) continue;
      // 한 세션에게만 남긴 메모('드럼: 쉬기')는 받는 팀에 그 세션이 있으면 그대로, 없으면 전체에게 가되
      // 누구에게 한 말인지 글 앞에 붙인다 — 그냥 전체로 두면 모두에게 '쉬기'가 된다
      const ses = str(n.session, 40), keep = !!ses && teamSess.includes(ses);
      const text = ses && !keep ? str(ses + ' · ' + t0, 60) : t0;
      await q(`insert into arrangement_notes(arrangement_id, team_id, marker_label, layer, session, author_id, author_name, text)
               values($1,$2,$3,'all',$4,$5,$6,$7)`, [a.id, teamId, str(n.label, MARKER_LABEL_MAX) || 'A', keep ? ses : null, uid, from ? from + ' (받음)' : '', text]);
    }
    out.push({ songId: s.id, arrangementId: a.id, title });
  }
  await audit(teamId, uid, 'share.take', out.map((x) => x.songId).join(','), { from, songs: out.length });
  return { songs: out, from };
}

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
  if (!size) throw bad('파일 크기를 알 수 없어요');   // 서명 URL 이 이 크기만 받는다
  const type = str(body.mime, 100) || 'application/octet-stream';
  const ext = type.includes('jpeg') ? '.jpg' : type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : type.startsWith('audio/') ? '.audio' : '';
  const pathname = `teams/${teamId}/${params.id}${ext}`;
  const p = await presignPut(pathname, type, 10, size);
  return { uploadUrl: p.url, pathname, mime: type };
});
// 직접 올린 파일을 DB 에 등록 (실제로 있는지 확인)
// 클라이언트가 내려받다 404 를 만나면 알려 준다. 진짜 없으면 기록을 지워, 파일을 가진 기기가
// 다음 동기화 때 다시 올린다 (기록만 남고 파일이 사라진 경우의 자가 치유)
on('POST', '/blobs/:id/gone', async ({ uid, url, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str((body && body.teamId) || url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const row = await one('select url, pathname from blobs where team_id=$1 and id=$2', [teamId, params.id]);
  if (!row) return { gone: true };
  const exists = await blobExists(row);
  if (exists) return { gone: false };
  await q('delete from blobs where team_id=$1 and id=$2', [teamId, params.id]);
  return { gone: true };
});

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
  if (!size) throw bad('파일 크기를 알 수 없어요');
  const mime = /^audio\//.test(str(body.mime, 60)) ? str(body.mime, 60) : 'audio/mp4';
  const blobId = 'r' + randomToken(12).replace(/[^A-Za-z0-9]/g, '').slice(0, 16).toLowerCase();
  const ext = mime.includes('mp4') || mime.includes('m4a') ? '.m4a' : mime.includes('webm') ? '.webm' : mime.includes('mpeg') ? '.mp3' : '.audio';
  const pathname = `teams/${teamId}/rehearsals/${blobId}${ext}`;
  const p = await presignPut(pathname, mime, 10, size);
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
    await notify(teamId, to, 'rehearsal.uploaded', r.id, { title: `${label} 녹음이 올라왔어요`, body: (+body.duration ? `${mm}:${String(ss).padStart(2, '0')}` : '') , link: await viewLinkOr(teamId, serviceId, '#/home') });
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
// 메모는 녹음 한 줄의 jsonb 배열이다. 읽어서 JS 로 고쳐 통째로 쓰면, 업로드 알림을 받고 여럿이 한꺼번에
// 메모를 달 때 나중 쓴 사람이 앞사람 것을 덮어 지운다 (20개 중 4개만 남았다).
// 그래서 배열 고치기를 update 한 문장 안에서 한다 — 같은 줄의 update 는 서로 기다렸다가 새 값 위에 다시 계산된다
const REH_NOTES = `(case when jsonb_typeof(notes) = 'array' then notes else '[]'::jsonb end)`;
on('POST', '/rehearsals/:id/notes', async ({ uid, params, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  const m = await requireMember(uid, teamId);
  const b = body.note || {};
  const layer = ['leader', 'session', 'mine'].includes(str(b.layer, 10)) ? str(b.layer, 10) : 'mine';
  if (layer === 'leader' && m.role !== 'leader') throw forbidden('전체 메모는 인도자만 쓸 수 있어요');
  if (m.role === 'pastor' && !(await teamSettings(teamId)).pastorCanMemo) throw forbidden('목회자 메모는 팀 설정에서 켜야 해요');
  // 세션 메모는 내 세션(겸임이면 그중 하나)에만. 콘티 메모(POST /notes)와 같은 규칙
  const want = str(b.session, 40);
  const n = { id: /^[A-Za-z0-9_-]{4,40}$/.test(str(b.id, 40)) ? str(b.id, 40) : randomToken(8), t: Math.max(0, Math.round(+b.t || 0)), text: str(b.text, 60), layer,
    session: layer === 'session' ? (mySessions(m).includes(want) ? want : (m.session || null)) : null, itemId: str(b.itemId, 64) || null,
    authorId: uid, author: m.mname, createdAt: new Date().toISOString() };
  if (!n.text) throw bad('내용을 적어 주세요');
  // id 는 클라이언트가 정한다 (지울 때 그 id 로 찾는다). 같은 id 로 다시 보내면 내 메모만 바꿔 쓴다 —
  // 남의 메모 id 로 보내 인도자 메모를 지우고 내 것으로 바꿔치는 일이 없게
  const rows = await q(`update rehearsals set notes = (
      select coalesce(jsonb_agg(e order by i), '[]'::jsonb) from (
        select e, i, count(*) over () as cnt from jsonb_array_elements(
          coalesce((select jsonb_agg(x order by k) from jsonb_array_elements(${REH_NOTES}) with ordinality o(x, k) where x->>'id' is distinct from $3), '[]'::jsonb)
          || $4::jsonb) with ordinality a(e, i)) s
      where i > cnt - 300)
    where id=$1 and team_id=$2
      and not exists (select 1 from jsonb_array_elements(${REH_NOTES}) x where x->>'id' = $3 and x->>'authorId' is distinct from $5)
    returning id`, [params.id, teamId, n.id, JSON.stringify([n]), uid]);
  if (!rows.length) {
    if (!(await one('select 1 from rehearsals where id=$1 and team_id=$2', [params.id, teamId]))) throw notFound('녹음이 없어요');
    throw new HttpError(409, 'note_taken', '다른 사람의 메모와 id 가 겹쳐요. 다시 저장해 주세요');
  }
  return { ok: true, note: n };
});
on('DELETE', '/rehearsals/:id/notes/:noteId', async ({ uid, params, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  const m = await requireMember(uid, teamId);
  const rows = await q(`update rehearsals set notes = (
      select coalesce(jsonb_agg(x order by k), '[]'::jsonb) from jsonb_array_elements(${REH_NOTES}) with ordinality o(x, k)
      where not (x->>'id' = $3 and ($4::boolean or x->>'authorId' = $5)))
    where id=$1 and team_id=$2 returning id`, [params.id, teamId, params.noteId, m.role === 'leader', uid]);
  if (!rows.length) throw notFound('녹음이 없어요');
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
  // 겸임이면 내 세션 전부의 공유 메모를 받는다 (쓸 때도 그중 하나를 고른다 — POST /notes)
  const rows = await q(`select id, item_id as "itemId", marker_id as "markerId", media_id as "mediaId", t, layer, session, text, author_id as "authorId", author_name as "authorName", created_at as "createdAt"
                        from notes where team_id=$1 and service_id=$2 and (layer='leader' or (layer='session' and session = any($4::text[])) or author_id=$3) order by created_at asc`, [teamId, svcId, uid, mySessions(m)]);
  return { notes: rows, me: uid };
});

on('POST', '/notes', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64), svcId = str(body.serviceId, 64);
  const m = await requireMember(uid, teamId);
  const list = Array.isArray(body.notes) ? body.notes.slice(0, 200) : [];
  const pastorOk = m.role !== 'pastor' || (await teamSettings(teamId)).pastorCanMemo;
  // 받지 않은 메모는 id 와 까닭을 돌려준다. 전에는 조용히 건너뛰고 200 을 줘서, 클라이언트가
  // 올린 것으로 알고 있다가 다음 동기화 때 메모가 사라졌다 (목회자 메모가 꺼진 팀에서 '메모 저장' 뒤 증발)
  let n = 0; const refused = [];
  for (const x of list) {
    const id = str(x && x.id, 40), itemId = str(x && x.itemId, 40), layer = str(x && x.layer, 10), text = str(x && x.text, 200);
    const why = !/^[A-Za-z0-9_-]{4,40}$/.test(id) || !itemId || !text || !['leader', 'session', 'mine'].includes(layer) ? 'bad'
      : m.role === 'pastor' && !pastorOk ? 'pastor'
      : layer === 'leader' && m.role !== 'leader' ? 'leader' : '';
    if (why) { if (id) refused.push({ id, why }); continue; }
    // 겸임이면 고른 세션을 그대로 쓴다 (내 세션 목록 안일 때만)
    const want = str(x.session, 40);
    const session = layer === 'session' ? (mySessions(m).includes(want) ? want : m.session)
      : layer === 'leader' ? (want || null) : null;
    await q(`insert into notes(id, team_id, service_id, item_id, marker_id, media_id, t, layer, session, text, author_id, author_name, created_at)
             values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) on conflict (id) do nothing`,
      [id, teamId, svcId, itemId, str(x.markerId, 40) || null, str(x.mediaId, 40) || null, x.t == null ? null : +x.t, layer, session, text, uid, layer === 'leader' ? '인도자' : m.mname, x.at ? new Date(+x.at) : new Date()]);
    n++;
  }
  // 이미 서버에 있는 메모는 거절로 치지 않는다. 그림자를 잃은 기기는 받아 둔 남의 메모(인도자 메모 등)까지
  // 다시 올리는데, 그건 서버에 그대로 있으니 클라이언트가 지우면 안 된다
  const there = refused.length ? new Set((await q('select id from notes where team_id=$1 and id = any($2::text[])', [teamId, refused.map((r) => r.id)])).map((r) => r.id)) : new Set();
  return { ok: true, saved: n, rejected: refused.filter((r) => !there.has(r.id)) };
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
  await aiGuard(teamId, 'omr', uid);
  let quota;
  try { quota = await aiSongGuard(teamId, 'omr', body.songKey); } catch (e) { await aiRelease(teamId, 'omr', uid); throw e; }
  let r;
  try { r = await transcribeSheet({ b64, mime }); }
  catch (e) {
    await aiRefund(teamId, 'omr', quota);   // 실패했으니 돌려준다
    // Gemini 가 오류로 답한 것(e.status)은 과금되지 않으니 하루 한도도 돌려준다. 응답이 깨진 것은 과금돼서 그대로 센다
    if (e.status) await aiRelease(teamId, 'omr', uid);
    if (e.status === 429) throw new HttpError(429, 'omr_quota', '채보 한도에 걸렸어요. 잠시 뒤 다시 해 주세요');
    throw new HttpError(502, 'omr_failed', '채보 실패: ' + (e.message || ''));
  }
  await aiCount(teamId, 'omr', r.usage && r.usage.total, uid);
  return { songs: r.songs, model: r.model, usage: r.usage, cost: estimateUSD(r.model, r.usage),
           quota: { used: quota.used, cap: quota.cap } };
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
  await aiGuard(teamId, 'score', uid);
  let r;
  try { r = await transcribeScore({ b64, mime }, { thinking: 'LOW', repair: body.repair !== false }); }
  catch (e) {
    if (e.status) await aiRelease(teamId, 'score', uid);   // Gemini 오류 응답은 과금되지 않는다
    if (e.status === 429) throw new HttpError(429, 'omr_quota', '채보 한도에 걸렸어요. 잠시 뒤 다시 해 주세요');
    throw new HttpError(502, 'omr_failed', '채보 실패: ' + (e.message || ''));
  }
  // 박자가 어긋난 마디를 다시 물은 것도 한 번씩 센다 (사진 한 장에 최대 13번까지 부른다)
  await aiCount(teamId, 'score', r.usage && r.usage.total, uid, (r.calls || 1) - 1);
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
on('GET', '/ocr', async ({ uid }) => { if (!uid) throw noAuth();
  return { available: geminiConfigured() || visionConfigured(),
           engine: geminiConfigured() ? 'gemini' : (visionConfigured() ? 'vision' : ''),
           mock: process.env.GOOGLE_VISION_KEY === 'mock' }; });
on('POST', '/ocr', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');
  // 코드 인식은 Gemini 가 먼저다. 일반 OCR 은 위첨자(Bm⁷, A⁹)와 sus4 를 못 읽어
  // 절반 넘게 틀렸다. Gemini 는 코드 어휘를 알아 95~100% 를 읽는다 (docs/sample_sheet 기준)
  const useGemini = geminiConfigured() && body.engine !== 'vision';
  if (!useGemini && !visionConfigured()) throw new HttpError(503, 'no_ocr', '코드 인식 엔진이 아직 연결되지 않았어요');
  // Gemini 는 장마다 한 번씩 부른다. Vision 처럼 16장을 받으면 한도 1회로 16번을 쓰게 되므로
  // 엔진에 따라 받는 장수를 다르게 한다 (클라이언트는 이제 통째로 한 장만 보낸다)
  const maxImages = useGemini ? 2 : 16;
  // 형식은 그림만 받는다 (/omr·/score 와 같이). 받은 값을 그대로 Gemini 에 넘기면 PDF·영상을 '그림'이라고
  // 보내 한 번에 토큰을 수십만 개 쓰게 할 수 있다 — 한도는 호출 수로만 센다
  const images = (Array.isArray(body.images) ? body.images : []).slice(0, maxImages).filter((im) => im && typeof im === 'object')
    .map((im) => ({ b64: String(im.b64 || ''), mime: /^image\/(jpeg|png|webp)$/.test(str(im.mime, 40)) ? str(im.mime, 40) : 'image/jpeg', w: +im.w || 0, h: +im.h || 0, kind: str(im.kind, 10) })).filter((im) => im.b64.length > 100);
  if (!images.length) throw bad('이미지가 없어요');
  if (images.reduce((n, im) => n + im.b64.length, 0) > 12 * 1024 * 1024) throw new HttpError(413, 'too_large', '이미지가 너무 커요');
  // Gemini 는 장마다 한 번씩(제목 띠는 안 부른다), Vision 은 한 번에 보내도 장마다 과금된다 → 그만큼 자리를 잡는다
  const calls = useGemini ? Math.max(1, images.filter((im) => im.kind !== 'title').length) : images.length;
  await aiGuard(teamId, 'ocr', uid, calls);
  // 무료 플랜의 월 곡 한도. 악보가 여러 장이어도 곡 하나로 센다
  let quota;
  try { quota = await aiSongGuard(teamId, 'ocr', body.songKey); } catch (e) { await aiRelease(teamId, 'ocr', uid, calls); throw e; }
  if (useGemini) {
    let g;
    try { g = await ocrChordsGemini(images, { thinking: 'LOW' }); }
    catch (e) {
      if (!visionConfigured()) {
        await aiUndo(teamId, 'ocr', quota);   // 실패했으니 방금 뺀 곡을 돌려준다 (달마다 세는 환불과 따로)
        if (e.status) await aiRelease(teamId, 'ocr', uid, calls);
        throw new HttpError(502, 'ocr_failed', '코드 인식 실패: ' + (e.message || ''));
      }
      g = null;   // Gemini 가 실패하면 예전 방식으로라도 읽는다
    }
    if (g) {
      // 코드를 거의 못 찾았으면 인식이 안 된 것으로 보고 돌려준다 (달마다 횟수 제한)
      const found = (g.bands || []).reduce((n, b) => n + ((b.tokens || []).length), 0);
      const refunded = found < 5 ? await aiRefund(teamId, 'ocr', quota) : false;
      // 장마다 한 번씩 부른 것은 자리를 잡을 때 이미 셌다
      await aiCount(teamId, 'ocr', (g.usage && (g.usage.input + g.usage.output)) || 0, uid);
      const usd = estimateUSD(g.model, g.usage);
      return { results: g.bands, engine: 'gemini', title: g.title || '', key: g.key || '',
               quota: { used: refunded ? Math.max(0, quota.used - 1) : quota.used, cap: quota.cap, refunded },
               usage: g.usage, cost: usd, costKRW: Math.round(usd * (+process.env.USD_KRW || 1400) * 10) / 10 };
    }
  }
  const results = await ocrBands(images);
  // Gemini 로 읽다 실패해 Vision 으로 다시 읽었으면 그 장수만큼 더 센다
  await aiCount(teamId, 'ocr', 0, uid, useGemini ? images.length : 0);
  return { results, engine: 'vision', quota: { used: quota.used, cap: quota.cap } };
});

/* ---------- 결제 · 프로모션 코드 ---------- */
// RevenueCat 웹훅. 결제·갱신·환불이 일어나면 여기로 온다.
// 사용자 id 로 그 사람이 결제 담당인 팀을 찾아 플랜을 바꾼다
on('POST', '/iap/webhook', async ({ req, body }) => {
  if (!rcConfigured()) throw new HttpError(503, 'no_iap', '결제가 아직 연결되지 않았어요');
  if (!rcAuthOk(req)) throw new HttpError(401, 'bad_sig', '인증 실패');
  const act = planFromEvent((body && body.event) || body || {});
  if (act.kind === 'ignore') return { ok: true, skipped: act.why };

  // appUserID 는 앱이 우리 사용자 id 로 정한다
  const u = await one('select id from users where id=$1', [act.appUserId]).catch(() => null);
  if (!u) return { ok: true, skipped: '모르는 사용자' };
  // 산 사람 = 결제 담당. 인도자를 넘기면 created_by 는 새 인도자로 가지만 결제 담당은 남는다 (B.6.1).
  // created_by 로 찾으면 넘긴 뒤의 갱신이 팀을 못 찾아 유료 팀이 무료로 떨어진다.
  // 결제 담당인 팀이 여럿이면 이미 결제로 유료인 팀을 먼저 (갱신·만료는 그 팀 것이다)
  const t = await one(`select id from teams where coalesce(billing_user_id, created_by)=$1 and deleted_at is null
                       order by (plan_source = 'iap') desc nulls last, created_at limit 1`, [u.id]);
  if (!t) return { ok: true, skipped: '이 사용자가 결제 담당인 팀이 없음' };

  if (act.kind === 'grant') {
    await q('update teams set plan=$2, plan_until=$3, plan_source=$4 where id=$1', [t.id, act.plan, act.until, 'iap']);
    await audit(t.id, u.id, 'iap.grant', act.product, { plan: act.plan, until: act.until });
  } else if (act.kind === 'revoke') {
    // 결제로 받은 플랜만 끊는다. 프로모션으로 받은 기간이나 손으로 준 플랜은 결제 만료로 지우지 않는다
    const cur = await one('select plan_source, plan_until from teams where id=$1', [t.id]);
    if (cur && cur.plan_source === 'promo' && cur.plan_until && new Date(cur.plan_until) > new Date())
      return { ok: true, skipped: '프로모션 기간이 남아 있음' };
    if (!cur || cur.plan_source !== 'iap') return { ok: true, skipped: '결제로 받은 플랜이 아님' };
    await q(`update teams set plan='free', plan_until=null, plan_source=null where id=$1 and plan_source='iap'`, [t.id]);
    await audit(t.id, u.id, 'iap.revoke', act.product, {});
  } else if (act.kind === 'credits') {
    // RevenueCat 은 응답이 늦거나 실패하면 같은 사건을 다시 보낸다. 더하기는 두 번 하면 안 되니
    // 사건 id 를 남기는 것과 더하는 것을 한 문장으로 한다 (이미 있으면 더하지 않는다)
    const got = act.eventId
      ? await q(`with e as (insert into iap_events(id, team_id, kind) values($3, $1::uuid, 'credits') on conflict (id) do nothing returning id)
                 insert into credit_balance(team_id, omr) select $1::uuid, $2::int from e
                 on conflict (team_id) do update set omr = credit_balance.omr + excluded.omr, updated_at=now() returning omr`, [t.id, act.omr, act.eventId])
      : await q(`insert into credit_balance(team_id, omr) values($1,$2)
                 on conflict (team_id) do update set omr = credit_balance.omr + excluded.omr, updated_at=now() returning omr`, [t.id, act.omr]);
    if (!got.length) return { ok: true, skipped: '이미 처리한 사건' };
    await audit(t.id, u.id, 'iap.credits', act.product, { omr: act.omr, event: act.eventId || null });
  }
  return { ok: true, kind: act.kind };
});


// 코드를 넣으면 그 팀이 일정 기간 유료가 된다. 이미 유료면 남은 기간에 이어 붙인다
on('POST', '/promo/redeem', async ({ uid, body }) => {
  if (!uid) throw noAuth();
  const teamId = str(body.teamId, 64);
  await requireMember(uid, teamId, 'leader');   // 인도자만
  const code = str(body.code, 40).trim().toUpperCase();
  if (!code) throw bad('코드를 입력해 주세요');
  const c = await one('select * from promo_codes where upper(code)=$1', [code]);
  if (!c) throw new HttpError(404, 'bad_code', '없는 코드예요');
  if (c.expires_at && new Date(c.expires_at) < new Date()) throw bad('기간이 지난 코드예요');
  if (c.used >= c.max_uses) throw bad('이미 다 쓰인 코드예요');
  if (await one('select 1 from promo_redemptions where code=$1 and team_id=$2', [c.code, teamId]))
    throw bad('이 팀은 이미 쓴 코드예요');

  const t = await one('select plan, plan_until, plan_source from teams where id=$1', [teamId]);
  const cur = planName(t);
  // 결제로 유료인 팀에는 코드를 덮어쓰지 않는다 (결제 상태가 꼬인다)
  if (t && t.plan_source === 'iap' && cur !== 'free')
    throw bad('이미 구독 중이에요. 구독이 끝난 뒤에 쓸 수 있어요');
  // 기한 없는 유료(수동 지정)에 코드를 넣으면 기한이 생겨 며칠 뒤 무료로 떨어진다. 코드를 아껴 둔다
  if (cur !== 'free' && !t.plan_until) throw bad('기한 없는 유료 플랜이라 코드를 쓸 필요가 없어요');
  // 더 높은 플랜이 남아 있으면 낮은 코드로 덮어 내려가게 하지 않는다. 기간이 끝난 뒤에 쓰면 된다
  if (PLAN_RANK[cur] > (PLAN_RANK[c.plan] || 0)) throw bad(`지금 플랜(${cur === 'plus' ? 'Plus' : 'Pro'})이 이 코드보다 높아요. 기간이 끝난 뒤에 써 주세요`);
  // 코드 한 번 쓰기 → 이 팀 사용 기록 → 팀 기간 늘리기를 한 문장으로 한다 (한 트랜잭션).
  // 따로따로 하면 동시에 누른 요청들이 모두 '남았다'를 보고 들어와 한도를 넘기고, 같은 팀이 여러 번 기간을 쌓았다.
  // 한도는 update 가 줄을 잠근 채 다시 보고, 같은 팀의 두 번째 기록은 기본키에 걸려 문장 전체가 되돌려진다.
  // 기간은 그 순간의 plan_until 에서 이어 붙이고, 더 높은 플랜·기한 없는 플랜은 (경합 중에도) 내리지 않는다
  const active = `(teams.plan in ('pro','plus') and (teams.plan_until is null or teams.plan_until > now()))`;
  const rank = (p) => `(case ${p} when 'plus' then 2 when 'pro' then 1 else 0 end)`;
  let row;
  try {
    row = await one(`with u as (
        update promo_codes set used = used + 1
        where code=$1 and used < max_uses and (expires_at is null or expires_at > now())
        returning code, plan, days
      ), r as (
        insert into promo_redemptions(code, team_id, user_id, days) select code, $2::uuid, $3::uuid, days from u returning code
      ), t as (
        update teams set
          plan = case when ${active} and ${rank('teams.plan')} > ${rank('u.plan')} then teams.plan else u.plan end,
          plan_until = case when ${active} and teams.plan_until is null then null
                            else greatest(coalesce(teams.plan_until, now()), now()) + u.days * interval '1 day' end,
          plan_source = case when ${active} and teams.plan_until is null then teams.plan_source else 'promo' end
        from u, r where teams.id=$2
        returning teams.plan, teams.plan_until
      ) select plan, plan_until as until from t`, [c.code, teamId, uid]);
  } catch (e) {
    if (e && e.code === '23505') throw bad('이 팀은 이미 쓴 코드예요');
    throw e;
  }
  if (!row) throw bad('이미 다 쓰인 코드예요');
  await audit(teamId, uid, 'promo.redeem', c.code, { plan: row.plan, days: c.days });
  return { plan: row.plan, days: c.days, until: row.until };
});

/* ---------- §2 정기 예배 · 사역 날짜 ---------- */
const DEF_SETTINGS = { serviceAutoCreateWeeks: 4, nameRule: '{월}/{일} {이름}', reminderDay: 25, reminderMonthsAhead: 3,
  wordRequestDay: 2, wordRequestOn: true, rehearsalUploadRole: 'member', pastorCanMemo: false,
  defaultPractice: '', defaultRehearsal: '',
  songTags: ['경배', '찬양', '적용', '오프닝', '성탄', '부활', '수련회'] };
const WD = ['일', '월', '화', '수', '목', '금', '토'];

// 알림 (§1): 알림함에 남기고, 같은 (type, targetId, user) 키가 24시간 안에 다시 오면 갱신만(읽음 상태 유지). actionable 이면 홈 카드에 뜸
// 이 팀 사람에게만 남긴다. 계정을 지운 사람이 편성·통보 기록에 남아 있으면 외래키로 insert 가 실패해 통보 전체가 500 이었고
// (다시 누를 때마다 다른 사람에게 또 푸시), 편성에 팀 밖 사람 id 를 넣으면 그 사람에게 푸시가 갔다.
// 한 문장으로 모두 넣고, 실제로 남긴 사람에게만 푸시를 보낸다. 돌려주는 값 = 받은 사람 수
// 편성 빠짐·불가능으로 바꿈·말씀 요청은 다시 오면 새 할 일이다 — 할 일이 끝나 서버가 내린 카드(ackWhere)도 다시 띄운다
async function notify(teamId, userIds, type, targetId, { title, body = '', link = '', actionable = false, expiresAt = null }) {
  const ids = [...new Set(userIds || [])].map((u) => str(u, 64)).filter(Boolean);
  if (!ids.length) return 0;
  const rows = await q(`insert into notifications(team_id, user_id, type, target_id, title, body, link, actionable, expires_at)
           select $1::uuid, m.user_id, $3::text, $4::text, $5::text, $6::text, $7::text, $8::bool, $9::timestamptz
             from members m where m.team_id=$1::uuid and m.user_id::text = any($2::text[])
           on conflict (team_id, user_id, type, target_id) do update set
             title=excluded.title, body=excluded.body, link=excluded.link, actionable=excluded.actionable, expires_at=excluded.expires_at,
             read_at = case when notifications.updated_at > now() - interval '24 hours' then notifications.read_at else null end,
             acknowledged_at = case when excluded.type in ('lineup.changed', 'avail.conflict', 'word.request') or notifications.updated_at <= now() - interval '24 hours' then null else notifications.acknowledged_at end,
             updated_at = now()
           returning user_id`,
    [teamId, ids, type, String(targetId || ''), str(title, 120), str(body, 300), str(link, 200), !!actionable, expiresAt]);
  const to = rows.map((r) => r.user_id);
  if (!to.length) return 0;
  // 앱 안 알림은 전부 푸시로도 나간다. 종류별 끄기·조용한 시간은 sendPush 안에서 거른다
  // teamId 를 같이 싣는다: 링크(#/view/…, #/cal/…)는 팀 안 주소라, 여러 팀에 있는 사람이 다른 팀 알림을 누르면
  // 지금 보고 있는 팀에서 열려 엉뚱한 팀에 답하거나 '발행된 콘티가 없어요'가 떴다. 앱은 이걸 보고 팀을 바꾼 뒤 연다
  try {
    await sendPush(to, { title: str(title, 120), body: str(body, 300), link: str(link, 200), type, tag: `${type}:${targetId || ''}`, teamId: String(teamId || '') }, { type });
  } catch (e) { console.warn('push', e && e.message); }
  return to.length;
}
// 멤버가 눌러서 여는 콘티 주소. 멤버는 발행본만 열 수 있어서, 발행 전(자동 초안·인도자 초안)을 가리키면
// '발행된 콘티가 없어요'와 함께 홈으로 떨어졌다 → 발행본이 있을 때만 콘티로, 아니면 fallback
async function viewLinkOr(teamId, serviceId, fallback) {
  if (serviceId && await one('select 1 from services where team_id=$1 and id=$2', [teamId, serviceId])) return '#/view/' + serviceId;
  return fallback;
}
// 콘티(발행본·초안)를 같은 날짜의 사역 날짜에 연결한다. 없으면 manual 날짜를 만든다 (§2.2)
async function linkDate(teamId, serviceId, date, label) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date || ''))) return;
  const lbl = str(label, 40) || '예배';
  const cur = await q('select id, date::text as date, source, lineup from service_dates where team_id=$1 and service_id=$2', [teamId, serviceId]);
  // 날짜를 옮겼으면 옛 날짜에서 뗀다. 전에는 어디든 붙어 있기만 하면 그냥 돌아가서, 옛 날짜가 계속 이 콘티를
  // 가리키고 새 날짜는 빈 채로 남아 자동 생성이 거기에 빈 초안을 하나 더 만들었다 (편성·말씀·D-day 가 엉뚱한 콘티로).
  // 인도자가 연 날짜·정기 예배는 남기되, 콘티를 지웠을 때처럼 자동 초안으로 다시 채우지는 않는다 (그날 편성도 그대로)
  for (const r of cur) if (r.date !== date && r.source !== 'service')
    await q('update service_dates set service_id=null, auto_skip=true where id=$1 and service_id=$2', [r.id, serviceId]);
  // 콘티 때문에 생긴 옛 날짜(source='service')는 콘티를 따라간다 — 거기 짜 둔 편성도 같이
  const own = cur.filter((r) => r.date !== date && r.source === 'service');
  const drop = async (keep) => { for (const r of own) if (r.id !== keep) await q('delete from service_dates where id=$1 and service_id=$2', [r.id, serviceId]); };
  if (cur.some((r) => r.date === date)) return drop(null);
  const carry = own.find((r) => Array.isArray(r.lineup) && r.lineup.length);
  // 날짜가 바뀌었으니 전에 한 통보는 옛 날짜 이야기다 → 통보 기록을 비워 새 날짜로 다시 알리게 한다
  const fresh = (l) => JSON.stringify((Array.isArray(l) ? l : []).map((x) => (x && typeof x === 'object' ? { ...x, notifiedAt: null, acknowledgedAt: null } : x)));
  const free = await one(`select id from service_dates where team_id=$1 and date=$2 and service_id is null order by (source='recurring') desc, created_at asc limit 1`, [teamId, date]);
  // 비어 있을 때만 잡는다. 자동 생성과 동시에 같은 날짜를 잡으면 한쪽 연결이 덮여 사라졌다
  if (free && await one('update service_dates set service_id=$2, auto_skip=false where id=$1 and service_id is null returning id', [free.id, serviceId])) {
    if (carry) await q(`update service_dates set lineup=$2, notified='[]' where id=$1 and coalesce(jsonb_array_length(lineup), 0) = 0`, [free.id, fresh(carry.lineup)]);
    return drop(null);
  }
  if (own.length) {
    const mv = carry || own[0];
    const ok = await one(`update service_dates set date=$3, label=$4, lineup=$5, notified='[]' where id=$1 and service_id=$2
                          and not exists (select 1 from service_dates o where o.team_id=$6 and o.date=$3 and o.label=$4) returning id`,
      [mv.id, serviceId, date, lbl, fresh(mv.lineup), teamId]);
    if (ok) return drop(mv.id);
  }
  // source='service' 는 이 콘티 때문에 생긴 날짜라는 뜻이다. 인도자가 직접 연 날짜('manual')와
  // 구분해야, 콘티를 지웠을 때 남길지 같이 지울지 정할 수 있다
  await q(`insert into service_dates(team_id, date, label, source, open, service_id) values($1,$2,$3,'service',true,$4)
           on conflict (team_id, date, label) do update set service_id=coalesce(service_dates.service_id, excluded.service_id)`, [teamId, date, lbl, serviceId]);
  return drop(null);
}
// 한국 날짜의 오늘. DB 의 current_date 는 세션 시간대(운영 UTC)라 한국 00~09시에는 어제다
const KST_TODAY_SQL = "(now() at time zone 'Asia/Seoul')::date";
// D-N주 안의 열린 날짜에 콘티가 없으면 초안을 자동 생성한다 (§2.2). 이름 = 팀 이름 규칙
async function autoCreateServices(teamId) {
  const t = await one('select settings from teams where id=$1', [teamId]);
  const st = { ...DEF_SETTINGS, ...(t && t.settings || {}) };
  const rows = await q(`select id, date::text as date, label from service_dates where team_id=$1 and open and service_id is null
                        and not auto_skip
                        and date >= ${KST_TODAY_SQL} and date < ${KST_TODAY_SQL} + ($2::int * interval '1 day') order by date`, [teamId, st.serviceAutoCreateWeeks * 7]);
  let n = 0;
  for (const r of rows) {
    const id = 'a' + randomToken(9).replace(/[^A-Za-z0-9]/g, '').slice(0, 10).toLowerCase();
    const doc = { id, name: fmtName(st.nameRule, r.date, r.label), date: r.date, notice: '', message: '', messageRev: 0, version: 0, editedAt: Date.now(), items: [], auto: true, dateId: r.id };
    // 날짜를 먼저 잡고, 잡았을 때만 초안을 넣는다 (한 문장이라 같이 되거나 같이 안 된다).
    // 인도자 앱은 켤 때 목록을 두 번 받고 크론도 같은 일을 해서, 동시에 돌면 날짜마다 초안이 둘씩 생기고
    // 남은 초안이 새 날짜 줄('10/3 성탄예배')로 따로 붙었다
    const got = await one(`with c as (update service_dates set service_id=$2 where id=$3 and service_id is null and open and not auto_skip returning id)
                           insert into drafts(team_id, id, doc, updated_at) select $1::uuid, $2::text, $4::jsonb, now() from c
                           on conflict (team_id, id) do nothing returning id`, [teamId, id, r.id, JSON.stringify(doc)]);
    if (!got) continue;
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
  // 비활성·내보낸·목회자가 된 사람은 자동 편성에서 뺀다
  const ok = new Set((await q(`select user_id from members where team_id=$1 and active and role<>'pastor'`, [teamId])).map((r) => r.user_id));
  const out = [];
  for (const [session, ids] of Object.entries(def)) for (const mid of (Array.isArray(ids) ? ids : [])) out.push({ session, memberId: (no.has(mid) || !ok.has(mid)) ? '' : mid, notifiedAt: null, acknowledgedAt: null });
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
  // 한국 날짜로 센다. 서버 시계(운영 UTC)의 오늘로 세면 한국 00~09시에 추가한 정기 예배가 어제 날짜부터 들어가
  // 이미 지난 예배에 초안·편성이 생겼다. 요일 계산도 UTC 로만 해서 서버 시간대와 상관없게 한다
  // (로컬 시각으로 요일을 세고 toISOString 으로 날짜를 뽑으면 한국 시간대 기계에서는 하루씩 앞당겨졌다)
  const d = new Date(new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10) + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + ((rec.weekday - d.getUTCDay() + 7) % 7));
  const dates = [];
  for (let i = 0; i < weeks; i++, d.setUTCDate(d.getUTCDate() + 7)) dates.push(isoDate(d));
  // 한 문장으로 넣는다 (크론이 팀·정기 예배마다 13번씩 따로 부르던 것)
  await q(`insert into service_dates(team_id, date, label, time, source, recurring_id, open)
           select $1::uuid, x::date, $3::text, $4::text, 'recurring', $5::uuid, true from unnest($2::text[]) x
           on conflict (team_id, date, label) do nothing`,
    [teamId, dates, rec.label, rec.time || null, rec.id]);
}

// 이번 달 AI 사용량 (상단 바의 크레딧 알약·설정의 플랜 화면에서 쓴다)
on('GET', '/teams/:id/usage', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id);
  const t = await one('select plan, plan_until from teams where id=$1', [params.id]);
  const pl = planOf(t);
  const month = aiMonth();
  // 크레딧으로 낸 곡은 월 한도 사용량이 아니다 (크레딧은 creditOmr 로 따로 보인다)
  const rows = await q(`select kind, count(*)::int n from ai_songs where team_id=$1 and month=$2 and source is distinct from 'credit' group by kind`, [params.id, month]);
  const used = (k) => (rows.find((r) => r.kind === k) || {}).n || 0;
  // 다음 달 1일 (한국 시간)
  const [y, m] = month.split('-').map(Number);
  const next = m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`;
  const cb = await one('select omr from credit_balance where team_id=$1', [params.id]);
  return { plan: planName(t), month, resetAt: next, enforced: ENFORCE_PLAN,
           creditOmr: (cb && cb.omr) || 0,
           ocr: { used: used('ocr'), cap: pl.ocrSongs },
           omr: { used: used('omr'), cap: pl.omrSongs },
           credits: pl.credits };
});

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
    await q(`update service_dates set open=false where team_id=$1 and recurring_id=$2 and date > current_date and service_id is null`, [params.id, params.rid]);
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
  // 콘티도·편성도·가능 여부 답도 없는 미래 날짜만 지운다. 나머지는 닫기만 하고 지난 날짜는 그대로 둔다
  await q(`delete from service_dates sd where sd.team_id=$1 and sd.recurring_id=$2 and sd.date > current_date
           and sd.service_id is null and coalesce(jsonb_array_length(sd.lineup), 0) = 0
           and not exists (select 1 from availability a where a.team_id=sd.team_id and a.date=sd.date)`, [params.id, params.rid]);
  await q(`update service_dates set open=false where team_id=$1 and recurring_id=$2 and date > current_date and service_id is null`, [params.id, params.rid]);
  await q(`update service_dates set recurring_id=null where team_id=$1 and recurring_id=$2`, [params.id, params.rid]);
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
        else {
          // 목회자도 알아야 하지만 목회자의 달력은 누를 수 있는 게 없다 (누르면 전부 403) → 목회자는 홈으로
          const all = await q('select user_id, role from members where team_id=$1 and active and user_id<>$2', [params.id, uid]);
          const closed = { title: `${md} ${row.label}는 이번 주 쉽니다`, body: '' };
          await notify(params.id, all.filter((x) => x.role !== 'pastor').map((x) => x.user_id), 'date.closed', row.id, { ...closed, link: '#/cal' });
          await notify(params.id, all.filter((x) => x.role === 'pastor').map((x) => x.user_id), 'date.closed', row.id, { ...closed, link: '#/home' });
        }
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
// 편성 표는 service_dates 를 본다. 콘티를 지웠는데 날짜가 남거나, 콘티는 있는데 날짜가 없으면
// 표가 실제와 어긋난다 → 읽을 때마다 맞춘다 (지운 콘티가 보이고 있는 콘티가 안 보이던 것)
async function reconcileDates(teamId) {
  // 콘티의 날짜: 발행본과 초안 중 나중에 저장된 쪽이 인도자가 지금 정해 둔 날짜다
  const live = await q(`select distinct on (id) id, name, date from (
                          select id, name, date::text as date, updated_at from services where team_id=$1 and date is not null
                          union all select id, doc->>'name', doc->>'date', updated_at from drafts where team_id=$1 and doc->>'date' <> '') s
                        order by id, updated_at desc`, [teamId]);
  // 콘티가 사라진 날짜: 콘티 때문에 생긴 날짜는 지우고, 직접 연 날짜는 연결만 푼다.
  // 있는지는 SQL 안에서 본다 — 목록을 먼저 읽고 나서 그 사이 자동 생성이 붙인 새 초안의 연결을 풀지 않게
  const gone = `service_id is not null
    and not exists (select 1 from services s where s.team_id=$1 and s.id=service_dates.service_id and s.date is not null)
    and not exists (select 1 from drafts d where d.team_id=$1 and d.id=service_dates.service_id and d.doc->>'date' <> '')`;
  await q(`delete from service_dates where team_id=$1 and source='service' and ${gone}`, [teamId]);
  await q(`update service_dates set service_id=null where team_id=$1 and ${gone}`, [teamId]);
  // 날짜가 없는 콘티는 연결하고, 날짜를 옮긴 콘티는 새 날짜로 옮긴다 (예전 코드가 옛 날짜에 남겨 둔 것도 여기서 바로잡힌다)
  const at = new Map();
  for (const r of await q('select service_id, date::text as date from service_dates where team_id=$1 and service_id is not null', [teamId]))
    at.set(r.service_id, (at.get(r.service_id) || []).concat(r.date));
  for (const r of live) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(r.date || '')) continue;
    const ds = at.get(r.id) || [];
    if (ds.length !== 1 || ds[0] !== r.date) await linkDate(teamId, r.id, r.date, r.name);
  }
}

on('GET', '/teams/:id/schedule', async ({ uid, url, params }) => {
  if (!uid) throw noAuth();
  const m = await requireMember(uid, params.id);
  try { await reconcileDates(params.id); } catch (e) { console.error('reconcile', e.message); }
  const from = /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get('from') || '') ? url.searchParams.get('from') : null;
  const to = /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get('to') || '') ? url.searchParams.get('to') : null;
  const range = from && to ? 'and date between $2 and $3' : "and date >= current_date - interval '1 month'";
  const args = from && to ? [params.id, from, to] : [params.id];
  const dates = await q(`select id, date::text as date, label, time, source, open, service_id as "serviceId", lineup, notified, slots
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
  // 불가능을 거두면 인도자의 '편성된 사람이 불가능으로 바꿈' 카드도 내린다
  const unConflict = () => ackWhere(`team_id=$1 and type='avail.conflict' and split_part(target_id, ':', 2)=$2
    and split_part(target_id, ':', 1) in (select id::text from service_dates where team_id=$1 and date=$3)`, [params.id, uid, date]);
  if (state === 'unset' || !state) { await q('delete from availability where team_id=$1 and user_id=$2 and date=$3', [params.id, uid, date]); await unConflict(); return { ok: true, state: 'unset' }; }
  if (!AV.includes(state)) throw bad('상태가 이상해요');
  await q(`insert into availability(team_id, user_id, date, state, memo) values($1,$2,$3,$4,$5)
           on conflict (team_id, user_id, date) do update set state=excluded.state, memo=excluded.memo, updated_at=now()`, [params.id, uid, date, state, memo]);
  await ackAvail(params.id, uid);
  if (state !== 'no') await unConflict();
  // §1 avail.conflict: 편성된 날을 불가능으로 바꾸면 인도자에게.
  // 가능 여부는 날짜 하나에 하나지만 그날 예배는 여럿(1부·2부)일 수 있다 → 그날 내가 들어간 예배마다 알린다
  // (첫 예배만 보던 때는 2부에만 선 사람이 빠져도 인도자가 몰랐다)
  if (state === 'no') {
    try {
      const ds = await q('select id, date::text as date, label, lineup from service_dates where team_id=$1 and date=$2 and open order by created_at asc', [params.id, date]);
      let leaders = null;
      for (const d of ds) {
        const mine = cleanLineup(d.lineup).filter((r) => r.memberId === uid);
        if (!mine.length) continue;
        leaders = leaders || (await q(`select user_id from members where team_id=$1 and role='leader'`, [params.id])).map((r) => r.user_id);
        const where = ds.length > 1 ? `${d.label} ` : '';
        await notify(params.id, leaders, 'avail.conflict', d.id + ':' + uid, {
          title: `${josa(m.mname, '이', '가')} ${josa(mdOf(date), '을', '를')} 불가능으로 바꿨어요`, body: [memo ? `"${memo}"` : '', `${where}${josa(mine.map((r) => r.session).join('·'), '으로', '로')} 편성돼 있음`].filter(Boolean).join(' · '),
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
  // 이 팀의 활성 멤버(목회자 제외)만 편성에 들어간다. 다른 id 는 빈 자리로 — 팀 밖 사람 id 를 넣으면 통보가 그 사람에게 갔다
  const okIds = new Set((await q(`select user_id from members where team_id=$1 and active and role<>'pastor'`, [params.id])).map((r) => r.user_id));
  const raw = cleanLineup(body.lineup, m.sessions || null).map((r) => (r.memberId && !okIds.has(r.memberId) ? { ...r, memberId: '' } : r));
  // 통보 기록은 그 사람이 맡은 세션들이 그대로일 때만 잇는다. 세션을 옮기거나 겸임을 늘리고 줄이면
  // 그 사람 자리를 전부 '통보 전'으로 돌린다 — 전에 받은 알림('드럼으로 섭니다')이 이제 틀리기 때문이다
  const sessKey = (l, mid) => l.filter((r) => r.memberId === mid).map((r) => r.session).sort().join('|');
  const next = raw.map((r) => {
    const old = r.memberId && sessKey(prev, r.memberId) === sessKey(raw, r.memberId) ? prev.find((p) => p.session === r.session && p.memberId === r.memberId) : null;
    return { ...r, notifiedAt: old ? old.notifiedAt : null, acknowledgedAt: old ? old.acknowledgedAt : null };
  });
  // 그날만 세션 인원을 늘리거나 줄일 수 있다. 팀 기본 정원은 건드리지 않는다
  let slots;
  if (body.slots && typeof body.slots === 'object') {
    const list = (await one('select sessions from teams where id=$1', [params.id])).sessions || [];
    slots = {};
    for (const k of list) if (body.slots[k] != null) slots[k] = Math.max(0, Math.min(9, Math.round(+body.slots[k]) || 0));
    await q('update service_dates set lineup=$2, slots=$3 where id=$1', [params.did, JSON.stringify(next), JSON.stringify(slots)]);
  } else {
    await q('update service_dates set lineup=$2 where id=$1', [params.did, JSON.stringify(next)]);
  }
  // 불가능으로 바꾼 사람을 편성에서 빼면 그 '불가능으로 바꿈' 카드는 할 일이 끝난 것이다
  await ackWhere(`team_id=$1 and type='avail.conflict' and split_part(target_id, ':', 1)=$2 and not (split_part(target_id, ':', 2) = any($3::text[]))`,
    [params.id, String(row.id), next.map((r) => String(r.memberId))]);
  return { ok: true, lineup: next, slots, changed: lineupKey(prev) !== lineupKey(next) };
});

// 통보하기 / 변경 통보 (§3.4)
on('POST', '/teams/:id/dates/:did/notify', async ({ uid, params }) => {
  if (!uid) throw noAuth();
  await requireMember(uid, params.id, 'leader');
  const row = await one('select id, date::text as date, label, time, lineup, notified, service_id as "serviceId" from service_dates where id=$1 and team_id=$2', [params.did, params.id]);
  if (!row) throw notFound('날짜가 없어요');
  const lineup = cleanLineup(row.lineup);
  const md = mdOf(row.date), where = `${md} ${row.label}`;
  // 발행 전이면(보통 1~3주 전에 통보한다) 그 달 편성 화면으로 — 거기에 '9/26 일렉으로 서요'가 보인다
  const link = await viewLinkOr(params.id, row.serviceId, '#/sched/' + row.date.slice(0, 7));
  const now = new Date().toISOString();
  // 누구에게 이미 알렸는지는 따로 기록해 둔다. 편성에서 빠진 사람은 지금 lineup 에 없으므로 lineup 만으로는 알 수 없다
  const already = new Set((Array.isArray(row.notified) ? row.notified : []).map((x) => str(x, 64)).filter(Boolean));
  const firstTime = already.size === 0;
  const nowIn = new Set(lineup.map((r) => r.memberId).filter(Boolean));   // 빈 자리('')는 제외
  const added = [...nowIn].filter((x) => !already.has(x));
  // 사람은 그대로인데 세션이 바뀐 사람 (편성 저장 때 그 사람 자리의 notifiedAt 을 비워 둔다).
  // 사람만 보던 때는 드럼→베이스로 옮겨도 '바뀐 사람이 없어요'로 끝나 본인은 계속 드럼인 줄 알았다
  const moved = [...nowIn].filter((x) => already.has(x) && lineup.some((r) => r.memberId === x && !r.notifiedAt));
  const dropped = [...already].filter((x) => !nowIn.has(x));
  const sessionsOf = (mid) => lineup.filter((r) => r.memberId === mid).map((r) => r.session).join('·');
  const timeLine = row.time ? `${row.time} 시작` : '';
  let sent = 0;
  for (const mid of (firstTime ? [...nowIn] : [...added, ...moved])) {
    sent += await notify(params.id, [mid], firstTime ? 'lineup.notify' : 'lineup.changed', row.id, {
      title: `${where} · ${josa(sessionsOf(mid), '으로', '로')} 섭니다`, body: timeLine, link, actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00'),
    });
  }
  // 빠진 사람에게도 알린다. 계정을 지웠거나 팀을 떠난 사람은 notify 가 건너뛴다 (셈에도 안 들어간다)
  for (const mid of dropped) {
    sent += await notify(params.id, [mid], 'lineup.changed', row.id, { title: `${md} 편성에서 빠졌어요`, body: row.label, link: '#/cal', actionable: true, expiresAt: new Date(row.date + 'T23:59:59+09:00') });
  }
  // 세션이 바뀌었거나 빠진 사람의 처음 통보 카드('드럼으로 섭니다')는 이제 틀렸다 → 처리한 것으로 내린다 (알림함에는 남는다)
  if (!firstTime && moved.length + dropped.length)
    await q(`update notifications set acknowledged_at=coalesce(acknowledged_at, now()) where team_id=$1 and type='lineup.notify' and target_id=$2 and user_id::text = any($3::text[])`,
      [params.id, row.id, [...moved, ...dropped]]);
  await q('update service_dates set lineup=$2, notified=$3 where id=$1',
    [params.did, JSON.stringify(lineup.map((r) => ({ ...r, notifiedAt: r.memberId ? (r.notifiedAt || now) : null }))), JSON.stringify([...nowIn])]);
  return { ok: true, sent, added: added.length, moved: moved.length, dropped: dropped.length, firstTime };
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

// 할 일이 끝난 알림 카드를 내린다 (§1.5 "할 일이 끝나면 카드는 사라진다"). 실패해도 본 동작은 그대로
async function ackWhere(sql, args) { try { await q(`update notifications set acknowledged_at=now() where acknowledged_at is null and ${sql}`, args); } catch (e) { console.error('ack', e.message); } }
// 목회자가 말씀을 적으면: 그 예배의 '다시 봐 주세요'와, 기간 안 말씀이 다 찬 주간 요청
async function ackWord(teamId, serviceId) {
  await ackWhere(`team_id=$1 and type='word.request' and target_id=$2`, [teamId, serviceId]);
  await ackWhere(`team_id=$1 and type='word.request' and target_id ~ '^\\d{4}-\\d{2}-\\d{2}$'
    and not exists (select 1 from service_dates sd left join service_words w on w.team_id=sd.team_id and w.service_id=sd.service_id
      where sd.team_id=notifications.team_id and sd.open and sd.date between (notifications.updated_at at time zone 'Asia/Seoul')::date
        and (case when notifications.target_id ~ '^\\d{4}-\\d{2}-\\d{2}$' then notifications.target_id::date end)
        and (w.word is null or coalesce(w.word->>'passage','')=''))`, [teamId]);
}
// 가능 여부를 적으면: 요청 기간(target_id 의 달 ~ expires_at)의 열린 날을 다 답한 월간 요청.
// 한 번에 석 달을 묻는데 첫 달만 보고 카드를 내리던 것도 여기서 기간 전체로 본다
async function ackAvail(teamId, userId) {
  await ackWhere(`team_id=$1 and user_id=$2 and type='avail.request' and target_id ~ '^\\d{4}-\\d{2}$' and expires_at is not null
    and not exists (select 1 from service_dates sd where sd.team_id=notifications.team_id and sd.open
      and sd.date between (case when notifications.target_id ~ '^\\d{4}-\\d{2}$' then (notifications.target_id || '-01')::date end)
        and (notifications.expires_at at time zone 'Asia/Seoul')::date
      and not exists (select 1 from availability a where a.team_id=sd.team_id and a.user_id=notifications.user_id and a.date=sd.date))`, [teamId, userId]);
}
// §1 알림함: 내 알림 목록(90일), 읽음, 처리(actionable 카드 닫기)
on('GET', '/notifications', async ({ uid, url }) => {
  if (!uid) throw noAuth();
  const teamId = str(url.searchParams.get('team'), 64);
  await requireMember(uid, teamId);
  const rows = await q(`select id, type, target_id as "targetId", title, body, link, actionable, read_at as "readAt", acknowledged_at as "ackAt", expires_at as "expiresAt", updated_at as "at"
                        from notifications where team_id=$1 and user_id=$2 and updated_at > now() - interval '90 days' order by updated_at desc limit 100`, [teamId, uid]);
  return { notifications: rows, unread: rows.filter((r) => !r.readAt).length };
});
// 사역일(열린 날짜)에 한 답만 센다. 사역일이 아닌 날의 답까지 세면 아직 안 고른 날이 가려졌다
const answeredOpen = `exists (select 1 from service_dates sd where sd.team_id=a.team_id and sd.date=a.date and sd.open)`;
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
  // 가능 여부는 날짜마다 하나다 → 1부·2부 줄이 아니라 날짜로 세고, 답도 사역일에 한 것만 센다
  const dates = await q('select distinct date::text as date from service_dates where team_id=$1 and open and date between $2 and $3', [teamId, from, to]);
  const answered = await one(`select count(*)::int as n from availability a where a.team_id=$1 and a.user_id=$2 and a.date between $3 and $4 and ${answeredOpen}`, [teamId, target, from, to]);
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
  if ((await one('select deleted_at from teams where id=$1', [teamId]) || {}).deleted_at) return { asked: 0, maybes: 0 };
  const day = now.getUTCDate(), dow = now.getUTCDay();
  let asked = 0, maybes = 0;
  // 다음 달 사역일 가능 여부 요청
  if (day === (+st.reminderDay || 25)) {
    const y = now.getUTCFullYear(), mo = now.getUTCMonth();
    const ahead = Math.max(1, Math.min(3, +st.reminderMonthsAhead || 3));
    const from = new Date(Date.UTC(y, mo + 1, 1)).toISOString().slice(0, 10);
    const to = new Date(Date.UTC(y, mo + 1 + ahead, 0)).toISOString().slice(0, 10);
    // 날짜로 센다 (1부·2부가 있는 날도 하루). 다 답한 사람에게 '미선택 1일'이 가던 것
    const dates = await q('select distinct date::text as date from service_dates where team_id=$1 and open and date between $2 and $3', [teamId, from, to]);
    if (dates.length) {
      const members = (await q(`select user_id from members where team_id=$1 and role<>'pastor' and active`, [teamId])).map((r) => r.user_id);
      const answered = await q(`select a.user_id, count(*)::int as n from availability a where a.team_id=$1 and a.date between $2 and $3 and ${answeredOpen} group by a.user_id`, [teamId, from, to]);
      const cnt = Object.fromEntries(answered.map((r) => [r.user_id, r.n]));
      const m1 = new Date(from + 'T00:00:00Z').getUTCMonth() + 1;
      const m2 = new Date(to + 'T00:00:00Z').getUTCMonth() + 1;
      const label = m1 === m2 ? `${m1}월` : `${m1}~${m2}월`;
      // 문구가 같은 사람끼리 묶어 한 번에 보낸다 (사람마다 따로 보내면 푸시 연결도 사람 수만큼 열려 크론이 느렸다)
      const byLeft = new Map();
      for (const mid of members) {
        const left = dates.length - (cnt[mid] || 0);
        if (left > 0) byLeft.set(left, (byLeft.get(left) || []).concat(mid));
      }
      for (const [left, ids] of byLeft)
        asked += await notify(teamId, ids, 'avail.request', from.slice(0, 7), { title: `${label} 스케줄 알려주세요`, body: `사역일 ${dates.length}일 · 아직 미선택 ${left}일`, link: '#/cal/' + from.slice(0, 7), actionable: true, expiresAt: new Date(to + 'T23:59:59+09:00') });
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
  if (st.wordRequestOn !== false && dow === (st.wordRequestDay == null ? 2 : +st.wordRequestDay)) {
    const pastors = (await q(`select user_id from members where team_id=$1 and role='pastor' and active`, [teamId])).map((r) => r.user_id);
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

// 팀·항목마다 하는 일을 몇 개씩 동시에 돌린다. 한 줄로 차례대로 돌면 팀이 늘수록 크론 제한 시간(300초·재시도 없음)을
// 넘겨, 뒤쪽 팀과 맨 끝의 정리 작업이 조용히 빠졌다. 한 팀이 실패해도 나머지는 계속한다
async function eachLimit(list, fn, n = 8) {
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, list.length) }, async () => {
    while (i < list.length) { const x = list[i++]; try { await fn(x); } catch (e) { console.error('cron', x && (x.id || x.team_id), e); } }
  }));
}

on('GET', '/cron/dates', async ({ req }) => {
  // Vercel 크론은 CRON_SECRET 이 설정돼 있으면 Authorization: Bearer <secret> 를 붙여 부른다. 미설정이면 아예 막는다 (위조 가능한 헤더로는 통과 불가)
  if (!process.env.CRON_SECRET || req.headers['authorization'] !== `Bearer ${process.env.CRON_SECRET}`) throw forbidden('크론 전용');
  // 정리 작업을 먼저 한다 (가볍고, 팀별 작업이 오래 걸려 시간이 끊겨도 빠지지 않게)
  // 90일 지난 알림 정리
  const purged = (await q(`delete from notifications where updated_at < now() - interval '90 days' returning id`)).length;
  await q('delete from revoked_sessions where exp < now()').catch((e) => console.error('revoked purge', e.message));   // 만료된 토큰은 어차피 안 통한다
  // §5.4 녹음 보관: 만료 7일 전 인도자에게 알림함 항목, 지난 것은 파일까지 삭제
  let warned = 0, dropped = 0;
  await eachLimit(await q(`select id, team_id, service_id, label, date::text as date, expires_at from rehearsals
                           where keep=false and warned_at is null and expires_at is not null and expires_at < now() + interval '7 days'`), async (r) => {
    const leaders = (await q(`select user_id from members where team_id=$1 and role='leader'`, [r.team_id])).map((x) => x.user_id);
    await notify(r.team_id, leaders, 'rehearsal.expiring', r.id, { title: `${r.label} 녹음이 7일 뒤 삭제돼요`, body: '보관하려면 잠금', link: '#/view/' + r.service_id });
    await q('update rehearsals set warned_at=now() where id=$1', [r.id]);
    warned++;
  });
  await eachLimit(await q(`select id, team_id, blob_id from rehearsals where keep=false and expires_at is not null and expires_at < now()`), async (r) => {
    await q('delete from rehearsals where id=$1', [r.id]);
    await dropBlobs(r.team_id, [r.blob_id]);
    dropped++;
  });
  // B.7.1 삭제 예약한 지 30일이 지난 팀은 여기서 실제로 지운다 (파일까지)
  let teamsDropped = 0;
  await eachLimit(await q(`select id from teams where deleted_at is not null and deleted_at < now() - interval '30 days'`), async (t) => {
    const urls = (await q('select url from blobs where team_id=$1', [t.id])).map((b) => b.url);
    if (urls.length) await delBlobs(urls);
    await q('delete from teams where id=$1', [t.id]);   // 나머지는 on delete cascade
    teamsDropped++;
  }, 2);
  // 지우다 실패한 파일, 직접 업로드 URL 만 받고 등록하지 않은 파일을 저장소에서 치운다 (lib/blob.js). 이것도 정리라 팀별 작업보다 먼저
  let blobsSwept = null;
  try { blobsSwept = await sweepBlobs(); } catch (e) { console.error('blob sweep', e); }
  // 팀마다: 정기 예배 13주 앞 유지 → D-N주 콘티 자동 생성
  const recs = await q(`select r.* from recurring r join teams t on t.id=r.team_id where r.active=true and t.deleted_at is null`);
  const byTeam = new Map();
  for (const r of recs) byTeam.set(r.team_id, (byTeam.get(r.team_id) || []).concat(r));
  let n = 0, created = 0;
  await eachLimit(await q('select id from teams where deleted_at is null'), async (t) => {
    for (const rec of byTeam.get(t.id) || []) { await fillDates(t.id, rec); n++; }
    created += await autoCreateServices(t.id);
  });
  return { ok: true, recurring: n, created, purged, warned, dropped, teamsDropped, blobsSwept };
});

// 알림 배치 (KST 10:00): 월간 스케줄 요청 · 보류 D-14 · 주간 말씀 요청 (§1.2 시각)
on('GET', '/cron/remind', async ({ req }) => {
  if (!process.env.CRON_SECRET || req.headers['authorization'] !== `Bearer ${process.env.CRON_SECRET}`) throw forbidden('크론 전용');
  let asked = 0, maybes = 0;
  await eachLimit(await q('select id, settings from teams where deleted_at is null'), async (t) => {
    const r = await scheduleReminders(t.id, { ...DEF_SETTINGS, ...(t.settings || {}) }); asked += r.asked; maybes += r.maybes;
  });
  return { ok: true, asked, maybes };
});

/* ---------- 진입점 ---------- */
// 네이티브 앱(화면이 https://localhost)만 다른 출처에서 부를 수 있게 한다.
// 아무 사이트나 열어 두면 남의 웹페이지가 로그인한 사용자 몰래 API 를 부를 수 있다
const APP_ORIGINS = new Set(['https://localhost', 'capacitor://localhost', 'ionic://localhost', 'http://localhost']);
function applyCors(req, res) {
  const origin = req.headers.origin;
  if (!origin || !APP_ORIGINS.has(origin)) return false;
  res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Headers', 'content-type, x-conti, x-conti-app, authorization');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader('Access-Control-Max-Age', '86400');
  res.setHeader('Vary', 'Origin');
  return true;
}

const S2S_PATHS = new Set(['/iap/webhook']);

export default async function handler(req, res) {
  const cors = applyCors(req, res);
  if (req.method === 'OPTIONS') { res.statusCode = cors ? 204 : 403; return res.end(); }
  try {
    const url = new URL(req.url, 'http://local');
    // Vercel 은 rewrite(?p=)가 경로를 풀어서 넘겼다. Cloud Run 에서는 pathname 이 퍼센트 인코딩 그대로라
    // 직접 푼다 (안 풀면 'lay%3Aabc' 같은 키가 형식 검사에 걸려 무대 배치 저장이 전부 400 이었다)
    let raw = url.searchParams.has('p') ? '/' + url.searchParams.get('p') : url.pathname.replace(/^\/api/, '');
    if (!url.searchParams.has('p')) { try { raw = decodeURIComponent(raw); } catch { throw bad('주소가 이상해요'); } }
    const path = raw.replace(/\/+$/, '').replace(/^\/*/, '/') || '/';
    const method = req.method.toUpperCase();
    const route = routes.find((r) => r.method === method && r.re.test(path));
    if (!route) {
      if (routes.some((r) => r.re.test(path))) throw new HttpError(405, 'method_not_allowed', '허용되지 않는 방식이에요');
      throw notFound('그런 API는 없어요');
    }
    // x-conti 는 남의 웹페이지가 로그인 쿠키로 몰래 부르는 것을 막는 표시다. 서버끼리 부르는 웹훅(RevenueCat)은
    // 이 헤더를 붙일 수 없고 쿠키도 쓰지 않는다 — 대신 Authorization 비밀값으로 따로 확인한다 (rcAuthOk)
    if (method !== 'GET' && req.headers['x-conti'] !== '1' && !S2S_PATHS.has(path)) throw forbidden('앱에서만 호출할 수 있어요');
    const params = path.match(route.re).groups || {};
    // 파일 그 자체가 본문인 경로(POST /blobs/:id)만 JSON 파싱을 건너뛴다. 이미지 base64 를 싣는 경로는 크게
    const rawBody = method === 'POST' && /^\/blobs\/[^/]+$/.test(path);
    // 세션: 서명·만료 검사 후, 비밀번호 변경(auth_epoch) 이전에 발급된 토큰과 로그아웃한 토큰은 무효 처리
    let uid = null; const claims = sessionClaims(req);
    // 콘티 한 벌(발행본·초안)은 AI 악보·코드가 많은 곡이 스무 곡쯤이면 1MB 를 넘는다 (앱의 DOC_MAX 와 같은 값).
    // 서명된 세션이 있을 때만 크게 받는다 — 로그인 없는 큰 요청으로 메모리를 채우지 못하게
    const big = /^\/(ocr|omr|score)$/.test(path) ? 12e6 : (claims && method === 'PUT' && /^\/services\/[^/]+(\/draft)?$/.test(path) ? 4e6 : 1e6);
    const body = (method === 'GET' || rawBody) ? {} : await readBody(req, big);
    if (claims) {
      const ep = await one('select extract(epoch from auth_epoch)::bigint as e, exists (select 1 from revoked_sessions where id=$2) as out from users where id=$1', [claims.uid, claims.tid]);
      if (ep && !ep.out && (ep.e == null || (claims.iat && claims.iat >= Number(ep.e)))) uid = claims.uid;
    }
    const out = await route.fn({ req, uid, params, body, url });
    // await 해야 응답을 만들다 던진 것(JSON 으로 못 바꾸는 값 등)도 아래 catch 가 받아 500 으로 끝낸다
    if (out && out.headers && 'data' in out) return await send(res, 200, out.data, out.headers);
    return await send(res, 200, out);
  } catch (e) {
    if (e instanceof HttpError) return send(res, e.status, { error: e.code, message: e.message });
    // 악보 저장소가 멎었을 때는 '서버 오류'가 아니라 무엇이 멈췄는지 알려 준다
    if (e instanceof BlobDownError) { console.error('blob down', e.message); return send(res, 503, { error: 'blob_down', message: e.message }); }
    console.error(e);
    return send(res, 500, { error: 'server', message: '서버 오류가 났어요' });
  }
}
