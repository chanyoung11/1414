// 애플 로그인 토큰 되돌리기 (App Store 심사 지침 5.1.1(v)) 서버 검사 — 로컬 DB · 이 프로세스 안의 가짜 애플 서버, 밖으로 나가는 호출 없이.
//
// 사용: node tests/test_apple_revoke.mjs
//   (DATABASE_URL 을 주지 않으면 로컬 도커 postgres://postgres:pg@localhost:54329/postgres. 스키마는 이 검사가 먼저 적용한다 — 멱등)
//
// 애플로 가입한 계정을 지우면 앱이 애플 토큰을 되돌려야(POST /auth/revoke) 한다. 전에는 ID 토큰만 확인하고 refresh token 을
// 받은 적이 없어 되돌릴 것이 없었다. 이제 앱·웹이 authorization code 를 같이 보내면 서버가 /auth/token 에서 refresh token 으로
// 바꿔 암호화해 두고, 계정 삭제·애플 연결 해제 때 /auth/revoke 를 부른다 (애플이 늦거나 죽어도 삭제는 막지 않는다).
// 1) lib/apple.js: 가짜 애플 주소는 localhost 만 · client_secret(ES256 JWT: iss 팀 · sub client_id · aud https://appleid.apple.com ·
//    kid · 서명) · .p8 을 여러 모양으로 넣어도 읽음 · 암호화(되돌리면 원문 · 바꾸면 안 열림 · 다른 계정·다른 AUTH_SECRET 으로 안 열림)
// 2) 교환·되돌리기를 가짜 애플에: 폼 값 · 코드의 sub 가 다르면 버림 · 실패·응답 없음은 시간 안에 실패로
// 3) API 전체: 코드 없는 옛 앱 · 앱(번들 id)·웹(Services ID + redirect_uri) · 다시 로그인하면 새 토큰 · 남의 코드 · 애플 고장 ·
//    키 없는 서버 · 동의 창(428) 뒤 · 계정 삭제(소셜 전용 · 비밀번호 · 애플 없음 · 애플이 응답 없음 · 인도자라 막힘) · 연결 해제
// 만든 사용자·팀은 끝에서 지운다.
import http from 'node:http';
import { generateKeyPairSync, verify as cverify, randomBytes, webcrypto as wc } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgres://postgres:pg@localhost:54329/postgres';
if (!/@(localhost|127\.0\.0\.1)[:/]/.test(process.env.DATABASE_URL)) { console.error('로컬 DB 에서만 돌린다'); process.exit(1); }
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const k of ['BLOB_READ_WRITE_TOKEN', 'R2_ENDPOINT', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'GOOGLE_CLIENT_ID_WEB', 'GOOGLE_CLIENT_ID_IOS', 'GOOGLE_CLIENT_ID_ANDROID']) delete process.env[k];
process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
process.env.BLOB_LOCAL_DIR = process.env.BLOB_LOCAL_DIR || path.join(root, '.localblob');
const WEB = 'test.lets1414.web', BUNDLE = 'test.lets1414.app', TEAM = 'TEAM123456', KID = 'KEY1234567';
process.env.APPLE_SERVICE_ID = WEB;
process.env.APNS_BUNDLE_ID = BUNDLE;
process.env.APPLE_SIGNIN_TEAM_ID = TEAM;
process.env.APPLE_SIGNIN_KEY_ID = KID;
// 애플 .p8 모양(PKCS#8 PEM). 비밀값 칸에 한 줄로 넣느라 줄바꿈을 \n 글자로 적은 것도 읽어야 한다
const sk = generateKeyPairSync('ec', { namedCurve: 'P-256' });
const other = generateKeyPairSync('ec', { namedCurve: 'P-256' });
const PEM = sk.privateKey.export({ type: 'pkcs8', format: 'pem' });
process.env.APPLE_SIGNIN_KEY = PEM.replace(/\n/g, '\\n');

// 스키마 먼저 (dev-local.sh 를 먼저 켜지 않아도 돌게)
{
  const { default: pg } = await import('pg');
  const c = new pg.Client({ connectionString: process.env.DATABASE_URL });
  await c.connect(); await c.query(fs.readFileSync(path.join(root, 'db', 'schema.sql'), 'utf8')); await c.end();
}

let fails = 0;
const ok = (c, m) => { console.log((c ? 'ok  ' : 'FAIL') + ' ' + m); if (!c) fails++; };
const T = Date.now().toString(36);
const b64u = (x) => Buffer.from(x).toString('base64url');
const jpart = (s) => JSON.parse(Buffer.from(s, 'base64url').toString());
// 서버가 남긴 로그 (애플이 실패해도 '적어는 둔다'를 본다)
const LOG = [];
const realErr = console.error;
console.error = (...a) => { LOG.push(a.map(String).join(' ')); };
const logged = (re) => LOG.some((l) => re.test(l));

/* ---------- 가짜 애플 (appleid.apple.com 흉내) ----------
   /auth/keys  ID 토큰 공개키(JWKS) · /auth/token  code → refresh token · /auth/revoke  토큰 되돌리기
   client_secret 은 진짜 애플처럼 따진다: ES256 · kid · iss=팀 · sub=client_id · aud=https://appleid.apple.com · 만료 · 서명 */
const rsa = await wc.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = await wc.subtle.exportKey('jwk', rsa.publicKey); jwk.kid = 'fake-apple'; jwk.alg = 'RS256';
async function idToken(sub, aud, { age = 0 } = {}) {
  const now = Math.floor(Date.now() / 1000) - age;
  const h = b64u(JSON.stringify({ alg: 'RS256', kid: 'fake-apple' }));
  const b = b64u(JSON.stringify({ iss: 'https://appleid.apple.com', aud, sub, email: sub + '@privaterelay.appleid.com', email_verified: 'true', iat: now, exp: now + 600 }));
  return h + '.' + b + '.' + b64u(await wc.subtle.sign('RSASSA-PKCS1-v1_5', rsa.privateKey, new TextEncoder().encode(h + '.' + b)));
}
const A = { mode: { token: 'ok', revoke: 'ok' }, codes: new Map(), tokenCalls: [], revokes: [], issued: [], badSecret: [] };
function secretOk(form) {
  try {
    const [h, p, s] = String(form.get('client_secret') || '').split('.');
    const head = jpart(h), body = jpart(p), now = Math.floor(Date.now() / 1000);
    const why = head.alg !== 'ES256' ? 'alg' : head.kid !== KID ? 'kid' : body.iss !== TEAM ? 'iss' : body.sub !== form.get('client_id') ? 'sub'
      : body.aud !== 'https://appleid.apple.com' ? 'aud' : !(body.exp > now) ? 'exp' : !(body.iat <= now + 5) ? 'iat'
      : !cverify('sha256', Buffer.from(h + '.' + p), { key: sk.publicKey, dsaEncoding: 'ieee-p1363' }, Buffer.from(s, 'base64url')) ? 'sig' : '';
    if (why) A.badSecret.push(why);
    return !why;
  } catch (e) { A.badSecret.push('parse'); return false; }
}
// 이 사람(sub)이 이 클라이언트에서 방금 로그인해 받은 code 를 하나 만든다 (한 번만 · 5분 · redirect 가 있으면 맞아야)
function mkCode(sub, clientId, redirect = null) {
  const code = 'c' + randomBytes(12).toString('hex') + '.0.' + T;
  A.codes.set(code, { sub, clientId, redirect, used: false });
  return code;
}
const appleSrv = http.createServer((req, res) => {
  let raw = ''; req.setEncoding('utf8'); req.on('data', (c) => { raw += c; });
  req.on('end', async () => {
    const url = new URL(req.url, 'http://x');
    const json = (st, o) => { res.statusCode = st; res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(o)); };
    if (url.pathname === '/auth/keys') return json(200, { keys: [jwk] });
    const form = new URLSearchParams(raw);
    if (url.pathname === '/auth/token' && req.method === 'POST') {
      A.tokenCalls.push(Object.fromEntries(form)); const m = A.mode.token;
      if (m === 'hang') return;
      if (m === '500') return json(500, { error: 'server_error' });
      if (!/application\/x-www-form-urlencoded/.test(req.headers['content-type'] || '')) return json(400, { error: 'invalid_request' });
      if (!secretOk(form)) return json(400, { error: 'invalid_client' });
      if (form.get('grant_type') !== 'authorization_code') return json(400, { error: 'unsupported_grant_type' });
      const c = A.codes.get(form.get('code'));
      if (!c || c.used) return json(400, { error: 'invalid_grant' });
      if (c.clientId !== form.get('client_id')) return json(400, { error: 'invalid_client' });
      if ((c.redirect || null) !== (form.get('redirect_uri') || null)) return json(400, { error: 'invalid_grant', error_description: 'redirect_uri' });
      c.used = true;
      const refresh = 'r' + randomBytes(16).toString('hex') + '.0.' + T;
      A.issued.push({ refresh, sub: c.sub, clientId: c.clientId });
      return json(200, { access_token: 'a' + randomBytes(8).toString('hex'), token_type: 'Bearer', expires_in: 3600, refresh_token: refresh,
        id_token: await idToken(c.sub, c.clientId) });
    }
    if (url.pathname === '/auth/revoke' && req.method === 'POST') {
      const m = A.mode.revoke;
      if (m === 'hang') { A.revokes.push({ ...Object.fromEntries(form), hung: true }); return; }
      if (!secretOk(form)) return json(400, { error: 'invalid_client' });
      A.revokes.push(Object.fromEntries(form));
      if (m === '500') return json(500, { error: 'server_error' });
      res.statusCode = 200; return res.end();
    }
    json(404, { error: 'not_found' });
  });
}).listen(0, '127.0.0.1');
await new Promise((r) => appleSrv.once('listening', r));
const APPLE = `http://127.0.0.1:${appleSrv.address().port}`;
process.env.APPLE_AUTH_BASE = APPLE;
const reset = () => { A.tokenCalls.length = 0; A.revokes.length = 0; A.badSecret.length = 0; A.mode.token = 'ok'; A.mode.revoke = 'ok'; };

const madeUsers = [], madeTeams = [];
let q;
try {
  const apple = await import(path.join(root, 'lib', 'apple.js'));
  const { appleBase, appleRevokeConfigured, appleClientSecret, sealAppleRefresh, openAppleRefresh, exchangeAppleCode, revokeAppleToken, _cfg } = apple;

  /* ================= 1) lib/apple.js ================= */
  const withEnv = (k, v, fn) => { const o = process.env[k]; if (v === undefined) delete process.env[k]; else process.env[k] = v; try { return fn(); } finally { if (o === undefined) delete process.env[k]; else process.env[k] = o; } };
  ok(withEnv('APPLE_AUTH_BASE', undefined, appleBase) === 'https://appleid.apple.com', '기본은 진짜 애플');
  ok(appleBase() === APPLE, '시험용 주소(127.0.0.1)를 쓴다');
  ok(withEnv('APPLE_AUTH_BASE', 'http://localhost:5555/', appleBase) === 'http://localhost:5555', 'localhost 도 된다 (끝 / 는 뗀다)');
  for (const bad of ['https://evil.example', 'http://127.0.0.1.evil.example:80', 'http://localhost.evil.example', 'https://127.0.0.1:5555',
    'http://127.0.0.1:5555/x', 'http://user@evil.example', 'http://10.0.0.1:80', ' http://127.0.0.1:5555'])
    ok(withEnv('APPLE_AUTH_BASE', bad, appleBase) === 'https://appleid.apple.com', `localhost 가 아닌 주소는 무시한다: ${bad}`);

  ok(appleRevokeConfigured(), '키·키 id·팀 id 가 다 있으면 켜진다');
  for (const k of ['APPLE_SIGNIN_KEY', 'APPLE_SIGNIN_KEY_ID', 'APPLE_SIGNIN_TEAM_ID'])
    ok(withEnv(k, undefined, () => !appleRevokeConfigured()), `${k} 가 없으면 꺼진다`);

  const nowS = Math.floor(Date.now() / 1000);
  const cs = await appleClientSecret(BUNDLE);
  const [ch, cp, csig] = cs.split('.');
  const H = jpart(ch), P = jpart(cp);
  ok(H.alg === 'ES256' && H.kid === KID, `client_secret 머리: ES256 · kid (${JSON.stringify(H)})`);
  ok(P.iss === TEAM && P.sub === BUNDLE && P.aud === 'https://appleid.apple.com', `client_secret 몸: iss 팀 · sub client_id · aud 는 가짜 주소여도 https://appleid.apple.com (${JSON.stringify(P)})`);
  ok(Math.abs(P.iat - nowS) <= 5 && P.exp > P.iat && P.exp - P.iat <= 15777000, 'iat 지금 · exp 는 뒤이고 6개월 안');
  ok(Buffer.from(csig, 'base64url').length === 64, '서명은 JWS 모양(r||s 64바이트, DER 아님)');
  ok(cverify('sha256', Buffer.from(ch + '.' + cp), { key: sk.publicKey, dsaEncoding: 'ieee-p1363' }, Buffer.from(csig, 'base64url')), '서명이 우리 키로 맞는다');
  ok(!cverify('sha256', Buffer.from(ch + '.' + cp), { key: other.publicKey, dsaEncoding: 'ieee-p1363' }, Buffer.from(csig, 'base64url')), '다른 키로는 안 맞는다');
  ok(jpart((await appleClientSecret(WEB)).split('.')[1]).sub === WEB, '웹은 Services ID 로 서명한다');
  // .p8 을 그대로(줄바꿈) · 본문만(머리·꼬리 없이) 넣어도
  for (const [label, v] of [['줄바꿈 그대로', PEM], ['본문만', PEM.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '')]]) {
    const s = await withEnv('APPLE_SIGNIN_KEY', v, () => appleClientSecret(BUNDLE));
    const [a, b, c] = s.split('.');
    ok(cverify('sha256', Buffer.from(a + '.' + b), { key: sk.publicKey, dsaEncoding: 'ieee-p1363' }, Buffer.from(c, 'base64url')), `.p8 ${label}도 읽는다`);
  }

  const RT = 'r-plain-refresh-' + T;
  const sealed = await sealAppleRefresh(RT, BUNDLE, 'sub-a');
  ok(typeof sealed === 'string' && !sealed.includes(RT) && !sealed.includes(Buffer.from(RT).toString('base64')) && !sealed.includes(b64u(RT)), '암호문에 원문이 안 보인다');
  const opened = await openAppleRefresh(sealed, 'sub-a');
  ok(opened && opened.token === RT && opened.clientId === BUNDLE, '되돌리면 토큰과 client_id');
  ok(await sealAppleRefresh(RT, BUNDLE, 'sub-a') !== sealed, '같은 토큰도 매번 다른 암호문 (iv)');
  ok(await openAppleRefresh(sealed, 'sub-b') === null, '다른 계정(sub) 줄에 옮겨 붙인 것은 안 열린다');
  const flip = sealed.slice(0, -3) + (sealed.slice(-3, -2) === 'A' ? 'B' : 'A') + sealed.slice(-2);
  ok(await openAppleRefresh(flip, 'sub-a') === null, '한 글자 바꾸면 안 열린다');
  ok(await openAppleRefresh('garbage', 'sub-a') === null && await openAppleRefresh(null, 'sub-a') === null, '모양이 틀리면 null');
  ok(await withEnv('AUTH_SECRET', 'another-secret-0123456789', () => openAppleRefresh(sealed, 'sub-a')) === null, 'AUTH_SECRET 이 다르면 안 열린다');

  /* ================= 2) 교환 · 되돌리기 (가짜 애플) ================= */
  reset();
  let code = mkCode('sub-x', BUNDLE);
  let r = await exchangeAppleCode({ code, clientId: BUNDLE, sub: 'sub-x' });
  const iss = A.issued[A.issued.length - 1];
  ok(r.ok && r.refreshToken === iss.refresh, `code → refresh token (${JSON.stringify(r)})`);
  const tc = A.tokenCalls[0] || {};
  ok(tc.client_id === BUNDLE && tc.grant_type === 'authorization_code' && tc.code === code && !('redirect_uri' in tc) && !A.badSecret.length,
    `교환 폼: client_id · grant_type · code · 앱은 redirect_uri 없음 · client_secret 통과 (${JSON.stringify(tc)} ${A.badSecret})`);
  r = await exchangeAppleCode({ code, clientId: BUNDLE, sub: 'sub-x' });
  ok(!r.ok, '한 번 쓴 code 는 다시 안 된다 (애플이 거절 → 실패로)');
  const RED = 'https://lets1414.example/api/auth/apple/callback';
  code = mkCode('sub-w', WEB, RED);
  r = await exchangeAppleCode({ code, clientId: WEB, sub: 'sub-w', redirectUri: RED });
  ok(r.ok && A.tokenCalls[A.tokenCalls.length - 1].redirect_uri === RED && A.tokenCalls[A.tokenCalls.length - 1].client_id === WEB, '웹: Services ID + redirect_uri');
  code = mkCode('someone-else', BUNDLE);
  r = await exchangeAppleCode({ code, clientId: BUNDLE, sub: 'sub-x' });
  ok(!r.ok, '애플이 준 id_token 의 사람이 다르면 버린다 (남의 code 를 붙여 보낸 것)');
  A.mode.token = '500';
  r = await exchangeAppleCode({ code: mkCode('sub-x', BUNDLE), clientId: BUNDLE, sub: 'sub-x' });
  ok(!r.ok, '애플 500 → 실패');
  A.mode.token = 'hang'; _cfg.timeoutMs = 400;
  let t0 = Date.now();
  r = await exchangeAppleCode({ code: mkCode('sub-x', BUNDLE), clientId: BUNDLE, sub: 'sub-x' });
  ok(!r.ok && Date.now() - t0 < 2000, `애플이 답이 없으면 시간 안에 실패 (${Date.now() - t0}ms)`);
  A.mode.token = 'ok';
  r = await withEnv('APPLE_SIGNIN_KEY', undefined, () => exchangeAppleCode({ code: mkCode('sub-x', BUNDLE), clientId: BUNDLE, sub: 'sub-x' }));
  ok(!r.ok, '키가 없으면 교환하지 않는다');

  reset();
  r = await revokeAppleToken({ token: 'r-tok-1', clientId: BUNDLE });
  const rv = A.revokes[0] || {};
  ok(r.ok && rv.token === 'r-tok-1' && rv.token_type_hint === 'refresh_token' && rv.client_id === BUNDLE && !A.badSecret.length,
    `되돌리기 폼: token · token_type_hint=refresh_token · client_id · client_secret (${JSON.stringify(rv)})`);
  A.mode.revoke = '500';
  r = await revokeAppleToken({ token: 'r-tok-2', clientId: WEB });
  ok(!r.ok && r.status === 500, '애플 500 → 실패 (상태를 알려 준다)');
  A.mode.revoke = 'hang'; t0 = Date.now();
  r = await revokeAppleToken({ token: 'r-tok-3', clientId: WEB });
  ok(!r.ok && Date.now() - t0 < 2000, `애플이 답이 없으면 시간 안에 실패 (${Date.now() - t0}ms)`);
  reset();

  /* ================= 3) API 전체 ================= */
  const { default: api } = await import(path.join(root, 'api', 'index.js'));
  ({ q } = await import(path.join(root, 'lib', 'db.js')));
  const call = (method, p, body, headers = {}) => new Promise((resolve) => {
    const h = {};
    const res = { statusCode: 200, setHeader(k, val) { h[k.toLowerCase()] = val; }, getHeader(k) { return h[k.toLowerCase()]; },
      end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ st: this.statusCode, j: j || {}, headers: h }); } };
    api({ method, url: '/api' + p, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
  });
  const cookieOf = (r) => ({ cookie: String(r.headers['set-cookie']).split(';')[0] });
  const AGREE = '2026-09-26T00:00:00Z';
  const stored = async (sub) => { const row = (await q(`select refresh_enc from identities where provider='apple' and subject=$1`, [sub]))[0]; return row ? row.refresh_enc : undefined; };
  const lastIssued = (sub) => [...A.issued].reverse().find((x) => x.sub === sub);
  // 애플로 로그인·가입 (app: 앱이면 번들 id, 웹이면 Services ID + redirect)
  const appleSignIn = async (sub, { app = true, withCode = true, extra = {}, headers = {} } = {}) => {
    const aud = app ? BUNDLE : WEB;
    const body = { provider: 'apple', idToken: await idToken(sub, aud), login: true, agreedAt: AGREE, ...extra };
    if (withCode) { body.code = mkCode(sub, aud, app ? null : RED); if (!app) body.redirectUri = RED; }
    const r = await call('POST', '/auth/social', body, headers);
    if (r.st === 200 && r.j.user && !madeUsers.includes(r.j.user.id)) madeUsers.push(r.j.user.id);
    return r;
  };
  const reauth = async (sub, { withCode = true } = {}) => ({ reauth: { provider: 'apple', idToken: await idToken(sub, BUNDLE), ...(withCode ? { code: mkCode(sub, BUNDLE) } : {}) } });

  // 옛 앱: code 를 안 보낸다 → 그대로 된다 · 애플에 아무것도 안 묻는다 · 적어 둔 것 없음
  const sOld = 'old-' + T;
  r = await appleSignIn(sOld, { withCode: false });
  ok(r.st === 200 && r.j.user, `옛 앱(code 없음) 애플 가입이 그대로 된다 (${r.st} ${r.j.message || ''})`);
  ok(A.tokenCalls.length === 0 && (await stored(sOld)) === null, '옛 앱: 애플 교환 없음 · refresh_enc 비어 있음');

  // 앱: 번들 id 로 교환 · 암호화해 둔다
  const sApp = 'app-' + T;
  r = await appleSignIn(sApp);
  ok(r.st === 200, '앱 애플 가입 (code 포함)');
  let enc = await stored(sApp);
  let want = lastIssued(sApp);
  ok(!!enc && !!want && !enc.includes(want.refresh), '앱: refresh token 을 받아 암호화해 둔다 (DB 에 원문 없음)');
  let op = enc && await openAppleRefresh(enc, sApp);
  ok(op && op.token === want.refresh && op.clientId === BUNDLE, '적어 둔 것을 풀면 애플이 준 토큰 · 번들 id');
  ok(A.tokenCalls.length === 1 && A.tokenCalls[0].client_id === BUNDLE && !('redirect_uri' in A.tokenCalls[0]), '앱 code 는 번들 id 로 · redirect_uri 없이 바꾼다');

  // 다시 로그인하면 새 토큰으로 바꾼다 (사용자가 설정에서 끊었다 다시 허락했으면 옛 토큰은 소용없다)
  const firstRefresh = want.refresh;
  r = await appleSignIn(sApp);
  want = lastIssued(sApp); op = await openAppleRefresh(await stored(sApp), sApp);
  ok(r.st === 200 && op && op.token === want.refresh && want.refresh !== firstRefresh, '다시 로그인하면 새 refresh token 으로 바꿔 둔다');

  // 웹: Services ID + 처음 쓴 redirect_uri
  reset();
  const sWeb = 'web-' + T;
  r = await appleSignIn(sWeb, { app: false });
  op = await openAppleRefresh(await stored(sWeb), sWeb);
  ok(r.st === 200 && op && op.clientId === WEB && A.tokenCalls[0] && A.tokenCalls[0].client_id === WEB && A.tokenCalls[0].redirect_uri === RED,
    `웹 code 는 Services ID · redirect_uri 로 바꾼다 (${JSON.stringify(A.tokenCalls[0])})`);
  // redirectUri 에 엉뚱한 주소를 넣으면 보내지 않는다 (애플이 거절 → 적어 둔 것 그대로 · 로그인은 된다)
  reset();
  const before = await stored(sWeb);
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: await idToken(sWeb, WEB), login: true, code: mkCode(sWeb, WEB, RED), redirectUri: 'javascript:alert(1)' });
  ok(r.st === 200 && (!A.tokenCalls[0] || !('redirect_uri' in A.tokenCalls[0])) && (await stored(sWeb)) === before, 'redirectUri 모양이 틀리면 넣지 않는다 (로그인은 된다)');

  // 남의 code 를 붙여 보낸 것 — 애플이 준 사람이 달라 버린다 (적어 둔 것 그대로)
  reset();
  const keep = await stored(sApp);
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: await idToken(sApp, BUNDLE), login: true, code: mkCode('stranger-' + T, BUNDLE) });
  ok(r.st === 200 && (await stored(sApp)) === keep, '다른 애플 계정의 code 는 버린다 (로그인은 된다 · 적어 둔 것 그대로)');

  // 애플이 고장이어도 로그인은 된다 · 적어는 둔다
  reset(); LOG.length = 0;
  A.mode.token = '500';
  r = await appleSignIn(sApp);
  ok(r.st === 200 && (await stored(sApp)) === keep && logged(/apple/i), '애플 교환이 500 이어도 로그인 · 로그 남김');
  A.mode.token = 'hang'; t0 = Date.now();
  r = await appleSignIn(sApp);
  ok(r.st === 200 && Date.now() - t0 < 2500, `애플이 답이 없어도 로그인은 시간 안에 (${Date.now() - t0}ms)`);
  A.mode.token = 'ok';

  // 키가 없는 서버: code 를 받아도 애플에 묻지 않는다
  reset();
  const sNoKey = 'nokey-' + T;
  const savedKey = process.env.APPLE_SIGNIN_KEY; delete process.env.APPLE_SIGNIN_KEY;
  r = await appleSignIn(sNoKey);
  process.env.APPLE_SIGNIN_KEY = savedKey;
  ok(r.st === 200 && A.tokenCalls.length === 0 && (await stored(sNoKey)) === null, '키가 없으면 code 는 버리고 로그인만 (애플 호출 없음)');

  // 새 계정 동의 창(428) — 그때는 바꾸지 않고, 동의하고 다시 보낸 같은 code 로 바꾼다
  reset();
  const sConsent = 'consent-' + T;
  const cc = mkCode(sConsent, BUNDLE);
  const it = await idToken(sConsent, BUNDLE);
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: it, login: true, code: cc });
  ok(r.st === 428 && A.tokenCalls.length === 0, '동의 전(428)에는 code 를 쓰지 않는다');
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: it, login: true, code: cc, agreedAt: AGREE });
  if (r.j.user) madeUsers.push(r.j.user.id);
  ok(r.st === 200 && !!(await stored(sConsent)), '동의하고 다시 보낸 같은 code 로 받아 둔다');

  // ---- 계정 삭제: 소셜 전용 애플 계정 (다시 확인한 애플 로그인의 code 까지 받아 그것을 되돌린다) ----
  reset(); LOG.length = 0;
  const sDel = 'del-' + T;
  r = await appleSignIn(sDel);
  const uDel = r.j.user;
  const ck = cookieOf(r);
  reset();
  r = await call('POST', '/auth/delete', { username: uDel.username, ...(await reauth(sDel)) }, ck);
  ok(r.st === 200, `소셜 전용 애플 계정 삭제 (${r.st} ${r.j.message || ''})`);
  ok(!(await q('select 1 from users where id=$1', [uDel.id])).length && !(await q(`select 1 from identities where subject=$1`, [sDel])).length, '계정·애플 연결이 지워짐');
  want = lastIssued(sDel);
  ok(A.revokes.length === 1 && A.revokes[0].token === want.refresh && A.revokes[0].client_id === BUNDLE && A.revokes[0].token_type_hint === 'refresh_token' && !A.badSecret.length,
    `삭제하면 애플에 되돌린다 — 다시 확인할 때 받은 가장 새 토큰 (${JSON.stringify(A.revokes)})`);

  // 애플이 답이 없어도 삭제는 된다 (시간 안에) · 로그를 남긴다
  const sHang = 'hang-' + T;
  r = await appleSignIn(sHang);
  const uHang = r.j.user, ckH = cookieOf(r);
  reset(); LOG.length = 0; A.mode.revoke = 'hang'; t0 = Date.now();
  r = await call('POST', '/auth/delete', { username: uHang.username, ...(await reauth(sHang)) }, ckH);
  const took = Date.now() - t0;
  ok(r.st === 200 && !(await q('select 1 from users where id=$1', [uHang.id])).length && took < 2500, `애플이 답이 없어도 삭제 · 시간 안에 (${took}ms)`);
  ok(A.revokes.length === 1 && A.revokes[0].hung && logged(/apple/i), '되돌리기를 시도했고 실패를 로그에 남김');
  // 애플이 500 이어도
  const s500 = 's500-' + T;
  r = await appleSignIn(s500); const u500 = r.j.user, ck5 = cookieOf(r);
  reset(); LOG.length = 0; A.mode.revoke = '500';
  r = await call('POST', '/auth/delete', { username: u500.username, ...(await reauth(s500)) }, ck5);
  ok(r.st === 200 && !(await q('select 1 from users where id=$1', [u500.id])).length && logged(/apple/i), '애플 되돌리기가 500 이어도 삭제 · 로그');
  reset();

  // 옛 앱으로 만든 계정을 옛 앱으로 지운다 (다시 확인에도 code 없음) → 되돌릴 것이 없어 부르지 않는다 · 삭제는 된다
  const uOld = (await q(`select u.id, u.username from users u join identities i on i.user_id=u.id where i.provider='apple' and i.subject=$1`, [sOld]))[0];
  r = await appleSignIn(sOld, { withCode: false });
  r = await call('POST', '/auth/delete', { username: uOld.username, ...(await reauth(sOld, { withCode: false })) }, cookieOf(r));
  ok(r.st === 200 && A.revokes.length === 0 && A.tokenCalls.length === 0, '토큰이 없는 옛 계정 삭제: 애플 호출 없이 삭제');

  // 옛 앱으로 만든 계정이라도 새 앱으로 지우면 — 다시 확인하는 애플 로그인의 code 로 받아 되돌린다
  const sOld2 = 'old2-' + T;
  r = await appleSignIn(sOld2, { withCode: false });
  const uOld2 = r.j.user, ckO2 = cookieOf(r);
  reset();
  r = await call('POST', '/auth/delete', { username: uOld2.username, ...(await reauth(sOld2)) }, ckO2);
  want = lastIssued(sOld2);
  ok(r.st === 200 && A.revokes.length === 1 && want && A.revokes[0].token === want.refresh, '옛 계정도 새 앱의 다시 확인(code)으로 받아 되돌린다');

  // 인도자라 삭제가 막히면 되돌리지 않는다 (계정은 남아 애플 로그인을 계속 쓴다)
  const sLead = 'lead-' + T;
  r = await appleSignIn(sLead); const uLead = r.j.user, ckL = cookieOf(r);
  const tm = await call('POST', '/teams', { name: '애플팀' + T, myName: '인도자' }, ckL);
  if (tm.j.teamId) madeTeams.push(tm.j.teamId);
  const mem = await call('POST', '/auth/signup', { username: 'apm' + T, password: 'secret12', name: '멤버' });
  if (mem.j.user) madeUsers.push(mem.j.user.id);
  const jn = await call('POST', `/invite/${tm.j.invite}/join`, { name: '멤버', sessions: ['드럼'] }, cookieOf(mem));
  ok(tm.st === 200 && jn.st === 200, '전제: 애플 계정이 인도자인 팀에 다른 멤버');
  reset();
  r = await call('POST', '/auth/delete', { username: uLead.username, ...(await reauth(sLead)) }, ckL);
  ok(r.st === 400 && (await q('select 1 from users where id=$1', [uLead.id])).length === 1, '인도자라 삭제가 막힘');
  ok(A.revokes.length === 0 && !!(await stored(sLead)), '막힌 삭제는 애플에 되돌리지 않는다 (토큰은 남는다)');

  // ---- 비밀번호 계정 + 애플 연결 ----
  const pw = await call('POST', '/auth/signup', { username: 'apw' + T, password: 'secret12', name: '비번' });
  madeUsers.push(pw.j.user.id);
  const ckP = cookieOf(pw);
  const sLink = 'link-' + T;
  reset();
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: await idToken(sLink, BUNDLE), code: mkCode(sLink, BUNDLE), password: 'secret12' }, ckP);
  ok(r.st === 200 && !!(await stored(sLink)), `로그인한 채 애플 연결(code 포함) → 받아 둔다 (${r.st} ${r.j.message || ''})`);
  // 연결 해제 → 되돌린다
  reset();
  want = lastIssued(sLink);
  r = await call('DELETE', '/auth/social/apple', { password: 'secret12' }, ckP);
  ok(r.st === 200 && !(await q(`select 1 from identities where subject=$1`, [sLink])).length, '애플 연결 해제');
  ok(A.revokes.length === 1 && A.revokes[0].token === want.refresh && A.revokes[0].client_id === BUNDLE, '연결을 떼면 애플에 되돌린다');
  // 코드 없이(옛 앱) 붙인 것을 떼면 부르지 않는다
  const sLink2 = 'link2-' + T;
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: await idToken(sLink2, BUNDLE), password: 'secret12' }, ckP);
  reset();
  r = await call('DELETE', '/auth/social/apple', { password: 'secret12' }, ckP);
  ok(r.st === 200 && A.revokes.length === 0, '토큰 없이 붙인 애플을 떼면 애플 호출 없음');
  // 비밀번호가 틀리면 떼지도 되돌리지도 않는다
  const sLink3 = 'link3-' + T;
  r = await call('POST', '/auth/social', { provider: 'apple', idToken: await idToken(sLink3, BUNDLE), code: mkCode(sLink3, BUNDLE), password: 'secret12' }, ckP);
  reset();
  r = await call('DELETE', '/auth/social/apple', { password: 'wrong-pass' }, ckP);
  ok(r.st === 401 && A.revokes.length === 0 && !!(await stored(sLink3)), '본인 확인이 틀리면 떼지도 되돌리지도 않는다');
  // 비밀번호 계정 삭제 → 붙어 있던 애플을 되돌린다
  reset();
  want = lastIssued(sLink3);
  r = await call('POST', '/auth/delete', { username: 'apw' + T, password: 'secret12' }, ckP);
  ok(r.st === 200 && A.revokes.length === 1 && A.revokes[0].token === want.refresh, '비밀번호 계정 삭제도 붙은 애플을 되돌린다');

  // 애플이 없는 계정 삭제 → 부르지 않는다
  const plain = await call('POST', '/auth/signup', { username: 'apn' + T, password: 'secret12', name: '평범' });
  madeUsers.push(plain.j.user.id);
  reset();
  r = await call('POST', '/auth/delete', { username: 'apn' + T, password: 'secret12' }, cookieOf(plain));
  ok(r.st === 200 && A.revokes.length === 0 && A.tokenCalls.length === 0, '애플이 없는 계정 삭제: 애플 호출 없음');

  // 응답·목록에 토큰이 새지 않는다
  const sLeak = 'leak-' + T;
  r = await appleSignIn(sLeak);
  const leakRefresh = lastIssued(sLeak).refresh;
  const lst = await call('GET', '/auth/social', null, cookieOf(r));
  const me = await call('GET', '/me', null, cookieOf(r));
  ok(!JSON.stringify(r.j).includes(leakRefresh) && !JSON.stringify(lst.j).includes(leakRefresh) && !JSON.stringify(lst.j).includes('refresh') && !JSON.stringify(me.j).includes(leakRefresh),
    '로그인 응답·연결 목록·/me 에 토큰이 안 나간다');
  ok(!LOG.some((l) => A.issued.some((x) => l.includes(x.refresh))), '로그에도 토큰 원문을 안 적는다');
} catch (e) { realErr(e); fails++; }
finally {
  try {
    if (q) {
      for (const t of madeTeams) await q('delete from teams where id=$1', [t]);
      if (madeUsers.length) await q('delete from users where id = any($1::uuid[])', [madeUsers]);
    }
  } catch (e) { realErr('뒷정리', e.message); fails++; }
  appleSrv.close();
}
console.error = realErr;
console.log(fails ? `\n${fails}개 실패` : '\n모두 통과');
process.exit(fails ? 1 : 0);
