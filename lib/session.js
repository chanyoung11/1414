// 로그인 세션: HMAC 서명한 쿠키. 외부 라이브러리 없음.
import crypto from 'node:crypto';

const COOKIE = 'conti_s';
const DAYS = 90;

function secret() {
  const s = process.env.AUTH_SECRET;
  if (!s || s.length < 16) throw new Error('AUTH_SECRET(16자 이상)이 필요합니다');
  return s;
}
const b64u = (buf) => Buffer.from(buf).toString('base64url');
const sign = (data) => b64u(crypto.createHmac('sha256', secret()).update(data).digest());

export function makeToken(payload) {
  const body = b64u(JSON.stringify(payload));
  return body + '.' + sign(body);
}

export function readToken(tok) {
  if (!tok || typeof tok !== 'string') return null;
  const i = tok.lastIndexOf('.');
  if (i < 0) return null;
  const body = tok.slice(0, i), sig = tok.slice(i + 1);
  const want = sign(body);
  if (sig.length !== want.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(want))) return null;
  try {
    const p = JSON.parse(Buffer.from(body, 'base64url').toString());
    if (!p.exp || p.exp < Date.now() / 1000) return null;
    return p;
  } catch { return null; }
}

export function parseCookies(req) {
  const out = {};
  (req.headers.cookie || '').split(';').forEach((kv) => {
    const i = kv.indexOf('='); if (i < 0) return;
    const v = kv.slice(i + 1).trim();
    try { out[kv.slice(0, i).trim()] = decodeURIComponent(v); } catch { out[kv.slice(0, i).trim()] = v; } // 깨진 쿠키 한 개가 모든 API를 500으로 만들지 않게
  });
  return out;
}

export function isSecure(req) {
  const proto = (req.headers['x-forwarded-proto'] || '').split(',')[0].trim();
  return proto === 'https';
}

// 네이티브 앱은 화면이 https://localhost 라 서버와 출처가 다르다. 그때만 SameSite=None 로
// 쿠키를 보낼 수 있게 한다. 웹사이트는 Lax 그대로 둬서 CSRF 방어를 지킨다
export function isApp(req) { return (req.headers['x-conti-app'] || '') === '1'; }

// iOS 는 다른 도메인의 쿠키를 앱을 껐다 켜면 버린다(ITP). 그래서 앱에는 같은 토큰을
// 본문으로도 내려 주고, 앱은 그것을 Authorization 헤더로 보낸다.
// 헤더는 브라우저가 자동으로 붙이지 않으므로 CSRF 위험이 없다
export function bearerToken(req) {
  const h = String(req.headers.authorization || '');
  return h.slice(0, 7).toLowerCase() === 'bearer ' ? h.slice(7).trim() : '';
}
export function appSessionToken(userId) {
  const iat = Math.floor(Date.now() / 1000);
  return makeToken({ uid: userId, iat, exp: iat + DAYS * 86400 });
}

export function cookieHeader(name, value, { maxAge, secure, httpOnly = true, cross = false } = {}) {
  let c = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=${cross ? 'None' : 'Lax'}`;
  if (httpOnly) c += '; HttpOnly';
  if (secure || cross) c += '; Secure';   // SameSite=None 은 Secure 가 없으면 브라우저가 버린다
  if (maxAge != null) c += `; Max-Age=${maxAge}`;
  return c;
}

export function sessionCookie(req, userId) {
  const iat = Math.floor(Date.now() / 1000), exp = iat + DAYS * 86400;
  return cookieHeader(COOKIE, makeToken({ uid: userId, iat, exp }),
    { maxAge: DAYS * 86400, secure: isSecure(req), cross: isApp(req) });
}
export function clearSessionCookie(req) {
  return cookieHeader(COOKIE, '', { maxAge: 0, secure: isSecure(req), cross: isApp(req) });
}
// 서명·만료를 통과한 토큰의 내용 {uid, iat, exp}. iat 는 users.auth_epoch(비밀번호 변경 시각)와 비교해 오래된 세션을 끊는 데 쓴다
export function sessionClaims(req) {
  const b = bearerToken(req);
  if (b) { const p = readToken(b); if (p) return p; }
  let c; try { c = parseCookies(req)[COOKIE]; } catch { return null; }
  return readToken(c);
}
export function sessionUserId(req) {
  const p = sessionClaims(req);
  return p ? p.uid : null;
}

export function randomToken(bytes = 12) { return crypto.randomBytes(bytes).toString('base64url'); }
