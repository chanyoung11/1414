// 구글·애플 로그인. 앱이나 웹이 받아 온 ID 토큰을 제공자 공개키로 검증한다.
//
// 둘 다 OpenID Connect 라 방식이 같다: JWKS 에서 공개키를 받아 서명을 확인하고
// iss·aud·exp 를 본다. 검증이 끝나면 {sub, email, name} 만 돌려준다.
//
// Workers 와 Node 양쪽에서 돌아야 해서 Web Crypto(globalThis.crypto.subtle)만 쓴다.

const JWKS_URL = {
  google: 'https://www.googleapis.com/oauth2/v3/certs',
  apple: 'https://appleid.apple.com/auth/keys',
};
const ISSUER = {
  google: ['https://accounts.google.com', 'accounts.google.com'],
  apple: ['https://appleid.apple.com'],
};

const b64url = (s) => {
  const pad = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(pad + '='.repeat((4 - (pad.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};
const jsonPart = (s) => JSON.parse(new TextDecoder().decode(b64url(s)));

// 공개키는 자주 바뀌지 않는다. 한 시간 동안은 받아 둔 것을 쓴다
const cache = new Map();
async function jwks(provider) {
  const hit = cache.get(provider);
  if (hit && Date.now() - hit.at < 3600e3) return hit.keys;
  const r = await fetch(JWKS_URL[provider]);
  if (!r.ok) throw new Error('키를 받지 못했어요');
  const { keys } = await r.json();
  cache.set(provider, { keys, at: Date.now() });
  return keys;
}

export async function verifyIdToken(provider, token, audiences) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) throw new Error('토큰 모양이 이상해요');
  const head = jsonPart(parts[0]);
  const body = jsonPart(parts[1]);

  let keys = await jwks(provider);
  let jwk = keys.find((k) => k.kid === head.kid);
  if (!jwk) {   // 키가 막 바뀌었을 수 있다. 캐시를 버리고 한 번 더
    cache.delete(provider);
    keys = await jwks(provider);
    jwk = keys.find((k) => k.kid === head.kid);
  }
  if (!jwk) throw new Error('서명 키를 찾지 못했어요');

  const key = await crypto.subtle.importKey('jwk',
    { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: jwk.alg || 'RS256', ext: true },
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key,
    b64url(parts[2]), new TextEncoder().encode(parts[0] + '.' + parts[1]));
  if (!ok) throw new Error('서명이 맞지 않아요');

  const now = Math.floor(Date.now() / 1000);
  if (body.exp && body.exp < now - 60) throw new Error('토큰이 만료됐어요');
  if (!ISSUER[provider].includes(body.iss)) throw new Error('발급처가 맞지 않아요');
  const auds = (audiences || []).filter(Boolean);
  if (auds.length && !auds.includes(body.aud)) throw new Error('이 앱에 발급된 토큰이 아니에요');

  return {
    sub: String(body.sub),
    email: body.email ? String(body.email).toLowerCase() : null,
    emailVerified: body.email_verified === true || body.email_verified === 'true',
    name: body.name ? String(body.name).slice(0, 40) : '',
    iat: +body.iat || 0,   // 언제 로그인해 받은 것인지 (다시 확인할 때 방금 받은 것만 받는다)
  };
}

// 환경변수에 넣어 둔 클라이언트 ID 목록 (웹·iOS·안드로이드가 서로 다르다)
export const audiencesOf = (provider) => {
  const raw = provider === 'google'
    ? [process.env.GOOGLE_CLIENT_ID_WEB, process.env.GOOGLE_CLIENT_ID_IOS, process.env.GOOGLE_CLIENT_ID_ANDROID]
    : [process.env.APPLE_SERVICE_ID, process.env.APNS_BUNDLE_ID || 'com.lets1414.app'];
  return raw.filter(Boolean);
};
export const socialConfigured = (provider) => audiencesOf(provider).length > 0;
