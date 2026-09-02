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
    out[kv.slice(0, i).trim()] = decodeURIComponent(kv.slice(i + 1).trim());
  });
  return out;
}

export function isSecure(req) {
  const proto = (req.headers['x-forwarded-proto'] || '').split(',')[0].trim();
  return proto === 'https';
}

export function cookieHeader(name, value, { maxAge, secure, httpOnly = true } = {}) {
  let c = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=Lax`;
  if (httpOnly) c += '; HttpOnly';
  if (secure) c += '; Secure';
  if (maxAge != null) c += `; Max-Age=${maxAge}`;
  return c;
}

export function sessionCookie(req, userId) {
  const exp = Math.floor(Date.now() / 1000) + DAYS * 86400;
  return cookieHeader(COOKIE, makeToken({ uid: userId, exp }), { maxAge: DAYS * 86400, secure: isSecure(req) });
}
export function clearSessionCookie(req) {
  return cookieHeader(COOKIE, '', { maxAge: 0, secure: isSecure(req) });
}
export function sessionUserId(req) {
  const p = readToken(parseCookies(req)[COOKIE]);
  return p ? p.uid : null;
}

export function randomToken(bytes = 12) { return crypto.randomBytes(bytes).toString('base64url'); }
