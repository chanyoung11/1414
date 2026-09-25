// 애플 로그인 토큰 되돌리기 (App Store 심사 지침 5.1.1(v)).
//
// 애플로 가입한 계정을 지우면 앱이 애플에 그 토큰을 되돌려야 한다(POST /auth/revoke). ID 토큰만으로는 되돌릴 수 없어서,
// 로그인할 때 앱·웹이 같이 보내는 authorization code 를 /auth/token 에서 refresh token 으로 바꿔 암호화해 두었다가
// 계정 삭제·애플 연결 해제 때 되돌린다. 모두 '되는 만큼'이다 — 애플이 늦거나 죽어도 로그인·삭제는 막지 않는다(부르는 쪽이 로그만 남긴다).
//
// client_id 는 code 가 나온 곳: 웹은 Services ID(APPLE_SERVICE_ID), 앱은 번들 id. 부르는 쪽이 ID 토큰의 aud 로 고른다
// (같은 로그인에서 나온 code 와 ID 토큰은 aud 가 같다). 되돌릴 때도 받을 때와 같은 client_id 를 써야 해서 토큰과 함께 적어 둔다.
//
// 환경변수: APPLE_SIGNIN_KEY(.p8 내용 — 줄바꿈을 \n 글자로 적어도 된다) · APPLE_SIGNIN_KEY_ID · APPLE_SIGNIN_TEAM_ID.
// 하나라도 없으면 꺼진다(code 는 버리고 로그인만). APPLE_AUTH_BASE 는 검사 전용 — http://127.0.0.1·localhost 만 받는다.
//
// Workers 와 Node 양쪽에서 돌게 Web Crypto(globalThis.crypto.subtle)만 쓴다.

const APPLE = 'https://appleid.apple.com';
// client_secret 의 aud 는 늘 진짜 애플 주소다 (가짜 서버로 보낼 때도)
const AUD = 'https://appleid.apple.com';
export const _cfg = { timeoutMs: 5000 };

// 시험에서만 로컬 가짜 애플을 쓴다. 그 밖의 주소는 무시한다 — 설정을 잘못 넣어 토큰·비밀값을 남에게 보내는 일이 없게
export function appleBase() {
  const u = process.env.APPLE_AUTH_BASE || '';
  const m = /^(http:\/\/(?:127\.0\.0\.1|localhost)(?::\d{1,5})?)\/?$/.exec(u);
  return m ? m[1] : APPLE;
}

const env = () => ({
  key: process.env.APPLE_SIGNIN_KEY || '',
  kid: process.env.APPLE_SIGNIN_KEY_ID || '',
  team: process.env.APPLE_SIGNIN_TEAM_ID || '',
});
export const appleRevokeConfigured = () => { const e = env(); return !!(e.key && e.kid && e.team); };

const enc = new TextEncoder(), dec = new TextDecoder();
const b64u = (buf) => {
  const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = ''; for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};
const unb64 = (s) => {
  const p = String(s).replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(p + '='.repeat((4 - (p.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

// .p8 (PKCS#8 PEM) → 서명 키. 그대로(줄바꿈) · \n 글자 · 머리·꼬리 없이 본문만 넣어도 읽는다. 같은 값이면 한 번만 읽는다
let keyHit = { raw: '', key: null };
async function signingKey() {
  const raw = env().key;
  if (keyHit.raw === raw && keyHit.key) return keyHit.key;
  const body = raw.replace(/\\n/g, '\n').replace(/-----[A-Z ]+-----/g, '').replace(/\s+/g, '');
  const key = await crypto.subtle.importKey('pkcs8', unb64(body), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  keyHit = { raw, key };
  return key;
}

// 애플이 client_secret 으로 받는 ES256 JWT. 최대 6개월까지 되지만 부를 때마다 새로 만들고 짧게(10분) 둔다.
// Web Crypto 의 ECDSA 서명은 r||s 64바이트라 JWS 모양 그대로다 (DER 이 아니다)
export async function appleClientSecret(clientId, nowMs = Date.now()) {
  const { kid, team } = env();
  const iat = Math.floor(nowMs / 1000);
  const head = b64u(enc.encode(JSON.stringify({ alg: 'ES256', kid })));
  const body = b64u(enc.encode(JSON.stringify({ iss: team, iat, exp: iat + 600, aud: AUD, sub: String(clientId) })));
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, await signingKey(), enc.encode(head + '.' + body));
  return head + '.' + body + '.' + b64u(sig);
}

/* ---------- 암호화해 두기 ----------
   AES-GCM. 키는 AUTH_SECRET 에서 용도를 달리해 뽑는다(HMAC) — 세션 서명과 같은 비밀이지만 같은 키는 아니다.
   계정(sub)을 AAD 로 묶어, 암호문을 다른 사람 줄에 옮겨 붙여도 열리지 않는다.
   모양: a1.<iv 12바이트>.<암호문+태그>  (안에는 {t: 토큰, c: client_id})
   AUTH_SECRET 을 바꾸면 전에 적어 둔 것은 열리지 않는다 → 그 계정은 되돌리지 못하고 로그만 남는다 (다음 애플 로그인 때 새로 적힌다) */
let aesHit = { secret: '', key: null };
async function aesKey() {
  const s = process.env.AUTH_SECRET;
  if (!s || s.length < 16) throw new Error('AUTH_SECRET(16자 이상)이 필요합니다');
  if (aesHit.secret === s && aesHit.key) return aesHit.key;
  const mac = await crypto.subtle.importKey('raw', enc.encode(s), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const raw = await crypto.subtle.sign('HMAC', mac, enc.encode('1414 apple refresh token v1'));
  const key = await crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
  aesHit = { secret: s, key };
  return key;
}
const aadOf = (sub) => enc.encode('identities:apple:' + String(sub));
export async function sealAppleRefresh(token, clientId, sub) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aadOf(sub) }, await aesKey(),
    enc.encode(JSON.stringify({ t: String(token), c: String(clientId) })));
  return 'a1.' + b64u(iv) + '.' + b64u(ct);
}
// 풀리면 {token, clientId}, 아니면 null (모양이 틀림 · 바뀜 · 다른 계정 · AUTH_SECRET 이 바뀜)
export async function openAppleRefresh(sealed, sub) {
  const p = String(sealed || '').split('.');
  if (p.length !== 3 || p[0] !== 'a1') return null;
  try {
    const iv = unb64(p[1]);
    if (iv.length !== 12) return null;
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: aadOf(sub) }, await aesKey(), unb64(p[2]));
    const o = JSON.parse(dec.decode(pt));
    return o && typeof o.t === 'string' && typeof o.c === 'string' ? { token: o.t, clientId: o.c } : null;
  } catch { return null; }
}

// 애플에 폼으로 보낸다. 시간 제한이 지나면 끊고 실패로 (로그인·삭제가 애플을 기다리며 멈추지 않게)
async function post(pathname, form) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), _cfg.timeoutMs);
  try {
    const r = await fetch(appleBase() + pathname, {
      method: 'POST', signal: ctl.signal,
      headers: { 'content-type': 'application/x-www-form-urlencoded', accept: 'application/json' },
      body: new URLSearchParams(form).toString(),
    });
    const text = await r.text();
    let json = null; try { json = text ? JSON.parse(text) : null; } catch {}
    return { status: r.status, json, text };
  } catch (e) {
    return { status: 0, json: null, text: ctl.signal.aborted ? `시간 초과(${_cfg.timeoutMs}ms)` : String((e && e.message) || e) };
  } finally { clearTimeout(timer); }
}
// 애플이 준 오류는 짧게만 (토큰·비밀값이 섞일 일은 없지만 로그가 길어지지 않게)
const why = (r) => `${r.status} ${String((r.json && (r.json.error || r.json.error_description)) || r.text || '').slice(0, 120)}`;
const payloadOf = (jwt) => { try { return JSON.parse(dec.decode(unb64(String(jwt).split('.')[1]))); } catch { return null; } };

// 로그인에서 받은 code → refresh token. sub 는 우리가 검증한 ID 토큰의 사람 — 애플이 함께 준 id_token 의 사람이 다르면 버린다
// (남의 code 를 붙여 보내 그 사람의 토큰을 내 계정에 두고, 내 계정을 지울 때 그 사람의 애플 연결을 끊는 일이 없게).
// 애플에서 바로(TLS) 받은 것이라 id_token 의 서명은 다시 보지 않는다
export async function exchangeAppleCode({ code, clientId, redirectUri, sub }) {
  if (!appleRevokeConfigured()) return { ok: false, error: '애플 키가 없어요' };
  if (!code || !clientId) return { ok: false, error: 'code·client_id 가 없어요' };
  let secret;
  try { secret = await appleClientSecret(clientId); } catch (e) { return { ok: false, error: '애플 키를 읽지 못했어요: ' + ((e && e.message) || e) }; }
  const form = { client_id: clientId, client_secret: secret, code, grant_type: 'authorization_code' };
  if (redirectUri) form.redirect_uri = redirectUri;
  const r = await post('/auth/token', form);
  if (r.status !== 200 || !r.json) return { ok: false, status: r.status, error: why(r) };
  if (typeof r.json.refresh_token !== 'string' || !r.json.refresh_token) return { ok: false, status: r.status, error: 'refresh_token 이 없어요' };
  const who = r.json.id_token ? payloadOf(r.json.id_token) : null;
  if (r.json.id_token && (!who || String(who.sub) !== String(sub))) return { ok: false, status: r.status, error: '다른 애플 계정의 code 예요' };
  return { ok: true, refreshToken: r.json.refresh_token };
}

// 애플에 토큰을 되돌린다. 성공은 200 (애플은 이미 무효인 토큰에도 200 을 준다)
export async function revokeAppleToken({ token, clientId, hint = 'refresh_token' }) {
  if (!appleRevokeConfigured()) return { ok: false, status: 0, error: '애플 키가 없어요' };
  let secret;
  try { secret = await appleClientSecret(clientId); } catch (e) { return { ok: false, status: 0, error: '애플 키를 읽지 못했어요: ' + ((e && e.message) || e) }; }
  const r = await post('/auth/revoke', { client_id: clientId, client_secret: secret, token, token_type_hint: hint });
  return r.status === 200 ? { ok: true, status: 200 } : { ok: false, status: r.status, error: why(r) };
}
