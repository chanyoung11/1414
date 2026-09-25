// 애드몹 보상형 광고 — 서버 측 확인(SSV)과 보상 표(토큰).
//
// 광고를 끝까지 본 사람에게 보상을 줄지는 앱이 아니라 구글이 정한다. 앱이 "봤어요"라고 보내는 말을 믿으면
// 누구나 요청 하나로 코드 인식을 공짜로 얻는다. 그래서 구글이 우리 서버(/api/ads/ssv)를 직접 부르고,
// 그 요청에 붙은 서명(ECDSA P-256 · SHA-256 · DER)을 구글이 공개한 키로 확인한 것만 보상으로 적는다.
//   https://developers.google.com/admob/android/ssv
//   구글 공식 검증기: tink-crypto/tink-java-apps · apps-rewardedads · RewardedAdsVerifier.java
//
// 서명한 내용은 '퍼센트 디코딩한' 쿼리 문자열의 signature 앞까지다. 공식 검증기는 java.net.URI.getQuery()
// (디코딩한 값)에서 "signature=" 앞을 잘라 확인하고, 그 시험(testShouldVerifyWithEncodedUrl)도
// ?foo=hello%20world&bar=user%40gmail.com 를 "foo=hello world&bar=user@gmail.com" 에 서명한다.
// 날것(%3A 그대로)으로 확인하면 custom_data 에 ':' 같은 글자가 하나만 있어도 진짜 보상이 전부 거절된다.
// '+' 는 공백으로 바꾸지 않는다 (URI.getQuery 는 %XX 만 푼다).
import { createPublicKey, verify, createHmac, timingSafeEqual, randomBytes } from 'node:crypto';

const GOOGLE_KEYS_URL = 'https://www.gstatic.com/admob/reward/verifier-keys.json';
// 시험에서만 로컬 키 파일을 쓴다. 그 밖의 주소는 무시한다 — 설정을 잘못 넣어 남이 만든 키를 믿는 일이 없게
function keysUrl() {
  const u = process.env.ADMOB_KEYS_URL || '';
  return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//.test(u) ? u : GOOGLE_KEYS_URL;
}

// 키 캐시. 구글: 키는 주기적으로 바뀌니 24시간보다 오래 두지 말 것
//  · 받는 요청은 한 번에 하나만 (동시에 들어온 콜백은 같은 받기를 기다린다)
//  · 모르는 key_id 로 다시 받는 것은 1분에 한 번 — 로그인 없는 경로라 아무 id 나 보내 밖으로 요청을 쏟게 하지 못하게
//  · 받기가 실패하면 10초 동안은 다시 나가지 않고, 전에 받은 키가 있으면 그것으로 확인한다
export const _cfg = { fetchMs: 5000, unknownGap: 60e3, failGap: 10e3, ttlMax: 24 * 3600e3 };
const K = { keys: new Map(), at: 0, ttl: 0, inflight: null, tried: 0, failedAt: 0, fetches: 0 };
// 시험용: 캐시를 비우고 받은 횟수를 본다
export function _resetKeys() { K.keys = new Map(); K.at = 0; K.ttl = 0; K.inflight = null; K.tried = 0; K.failedAt = 0; K.fetches = 0; }
export const _keyStats = () => ({ fetches: K.fetches, keys: K.keys.size });

async function download() {
  K.fetches++;
  const r = await fetch(keysUrl(), { signal: AbortSignal.timeout(_cfg.fetchMs) });
  if (!r.ok) throw new Error('admob keys ' + r.status);
  const j = await r.json();
  const keys = new Map();
  for (const k of (j && Array.isArray(j.keys) ? j.keys : [])) {
    const id = k && k.keyId != null ? String(k.keyId) : '';
    if (!/^\d{1,20}$/.test(id)) continue;
    try {
      // 공식 검증기처럼 base64(SPKI DER)를 먼저 쓰고, 없으면 pem
      const key = k.base64 ? createPublicKey({ key: Buffer.from(String(k.base64), 'base64'), format: 'der', type: 'spki' })
                           : createPublicKey(String(k.pem || ''));
      if (key.asymmetricKeyType === 'ec') keys.set(id, key);
    } catch { /* 모양이 이상한 키는 건너뛴다 */ }
  }
  if (!keys.size) throw new Error('admob keys empty');   // 빈 목록으로 멀쩡한 캐시를 지우지 않는다
  const m = /max-age=(\d+)/.exec(r.headers.get('cache-control') || '');
  const ttl = m ? Math.min(_cfg.ttlMax, Math.max(60e3, +m[1] * 1000)) : _cfg.ttlMax;
  return { keys, ttl };
}
function refresh() {
  if (K.inflight) return K.inflight;
  K.tried = Date.now();
  K.inflight = download()
    .then(({ keys, ttl }) => { K.keys = keys; K.at = Date.now(); K.ttl = ttl; K.failedAt = 0; },
          (e) => { K.failedAt = Date.now(); throw e; })
    .finally(() => { K.inflight = null; });
  return K.inflight;
}
// 키를 못 받았고 쓸 키도 없으면 던진다 → 라우트가 503 → 구글이 1초 간격으로 다시 보낸다
async function keyFor(keyId) {
  const fresh = K.at && Date.now() - K.at < K.ttl;
  if (!fresh) {
    if (K.inflight || Date.now() - K.failedAt >= _cfg.failGap) {
      try { await refresh(); } catch (e) { console.error('admob keys', e.message); if (!K.keys.size) throw e; }
    } else if (!K.keys.size) throw new Error('admob keys unavailable');
  }
  if (K.keys.has(keyId)) return K.keys.get(keyId);
  // 모르는 key_id — 구글이 키를 막 돌렸을 수 있다. 다만 자주는 안 받는다
  if (K.inflight || Date.now() - K.tried >= _cfg.unknownGap) {
    try { await refresh(); } catch (e) { console.error('admob keys', e.message); }
  }
  return K.keys.get(keyId) || null;
}

// URI 규칙대로 %XX 만 푼다 ('+' 는 그대로). 잘못된 % 는 null
function pctDecode(s) { try { return decodeURIComponent(s); } catch { return null; } }

// rawQuery: 요청 주소의 '?' 뒤 (디코딩하지 않은 것).
// 구글은 signature 와 key_id 를 맨 뒤 두 인자로 보낸다 (공식 검증기도 그렇지 않으면 거절한다).
// 우리 쪽 rewrite(vercel.json: /api?p=<경로>)가 붙인 p=… 는 구글이 보낸 것이 아니라 앞뒤 끝에서만 떼고 본다.
export async function verifySsv(rawQuery) {
  const parts = String(rawQuery || '').replace(/^\?/, '').split('&');
  while (parts.length && /^p=/.test(parts[0])) parts.shift();
  while (parts.length && /^p=/.test(parts[parts.length - 1])) parts.pop();
  const n = parts.length;
  if (n < 3 || !parts[n - 2].startsWith('signature=') || !parts[n - 1].startsWith('key_id=')) return { ok: false, why: 'shape' };
  const sig = parts[n - 2].slice('signature='.length), keyId = parts[n - 1].slice('key_id='.length);
  if (!/^\d{1,20}$/.test(keyId) || !/^[A-Za-z0-9_\-+/]+={0,2}$/.test(sig) || sig.length > 200) return { ok: false, why: 'shape' };
  const rawMsg = parts.slice(0, n - 2).join('&');
  const message = pctDecode(rawMsg);
  if (message == null) return { ok: false, why: 'encoding' };
  const key = await keyFor(keyId);
  if (!key) return { ok: false, why: 'unknown_key' };
  let good = false;
  try { good = verify('sha256', Buffer.from(message, 'utf8'), { key, dsaEncoding: 'der' }, Buffer.from(sig.replace(/\+/g, '-').replace(/\//g, '_'), 'base64url')); }
  catch { good = false; }
  if (!good) return { ok: false, why: 'bad_signature' };
  // 값은 서명을 확인한 바로 그 글자(디코딩한 message)에서 읽는다. 날것을 '&' 로 나눠 읽으면 안 된다:
  // 서명은 디코딩한 글자에만 걸려 있어서, 보내는 사람이 어느 '&' 를 %26 으로 감출지(=어디서 나뉠지)를 서명을 깨지 않고
  // 바꿀 수 있다. 구글의 키는 모든 애드몹 퍼블리셔가 같으니, 자기 광고 단위의 진짜 서명 콜백(custom_data·user_id 는
  // 자기가 정함)을 받아 진짜 ad_unit 은 다른 인자 값 속에 숨기고, custom_data 에 적어 둔 'ad_unit=우리 단위&custom_data=우리 표'
  // (user_id 로는 transaction_id 까지)를 진짜 인자처럼 읽히게 할 수 있었다 → 광고 단위 목록도, transaction_id 도 무력해진다.
  // 구글이 넣는 ad_unit·transaction_id·timestamp 는 서명한 글자 안에서 늘 제 '&' 뒤에 따로 선다. 그래서 custom_data·user_id 로
  // 끼워 넣은 같은 이름은 두 번째가 되고, 같은 이름이 두 번이면 믿지 않는다 (진짜 것을 가리거나 덮을 수 없다).
  // 값 안의 '=' 는 첫 '=' 에서만 나눠 그대로 둔다. 우리 보상 표는 [A-Za-z0-9._-] 뿐이고 user_id 는 보내지 않아 진짜 콜백에는
  // 값 속 '&' 가 없다 (있으면 custom_data 가 잘려 표 확인에서 떨어진다)
  const f = new Map();
  for (const kv of message.split('&')) {
    const i = kv.indexOf('=');
    const k = i < 0 ? kv : kv.slice(0, i), v = i < 0 ? '' : kv.slice(i + 1);
    if (f.has(k)) return { ok: false, why: 'shape' };
    f.set(k, v);
  }
  return {
    ok: true,
    keyId,
    txn: f.get('transaction_id') || '',
    userId: f.get('user_id') || '',
    customData: f.get('custom_data') || '',
    adUnit: f.get('ad_unit') || '',
    adNetwork: f.get('ad_network') || '',
    rewardItem: f.get('reward_item') || '',
    rewardAmount: +(f.get('reward_amount') || 0),
    timestamp: /^\d{1,16}$/.test(f.get('timestamp') || '') ? +f.get('timestamp') : 0,   // 구글: 밀리초
  };
}

/* ---------- 보상 표(토큰) ----------
   광고를 보여 주기 전에 서버가 발급하고, 앱은 그대로 custom_data 로 넘긴다(ServerSideVerificationOptions).
   구글은 그 값을 서명한 콜백에 담아 돌려주므로, 콜백의 팀·사람은 앱이 적은 말이 아니라 서버가 서명한 표에서 나온다.
   팀·사람·일회용 nonce·만료를 AUTH_SECRET 에서 뽑은 키로 HMAC 한다. 글자는 [A-Za-z0-9._-] 뿐이라 퍼센트 인코딩이 끼지 않는다.
   모양: r1.<종류>.<팀 hex32>.<사람 hex32>.<nonce 16>.<만료 초 36진수>.<mac 22>  */
export const TOKEN_TTL_SEC = 30 * 60;
function tokenKey() {
  const s = process.env.AUTH_SECRET;
  if (!s || s.length < 16) throw new Error('AUTH_SECRET(16자 이상)이 필요합니다');
  // 세션 서명과 같은 비밀을 쓰되 용도를 달리한 키 — 세션 토큰을 보상 표로(또는 반대로) 쓸 수 없게
  return createHmac('sha256', s).update('1414 admob reward token v1').digest();
}
const hex32 = (u) => String(u || '').replace(/-/g, '').toLowerCase();
const uuidOf = (h) => `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
const macOf = (body) => createHmac('sha256', tokenKey()).update(body).digest().subarray(0, 16);
export function rewardToken({ teamId, userId, kind, now = Date.now() }) {
  const th = hex32(teamId), uh = hex32(userId);
  if (!/^[0-9a-f]{32}$/.test(th) || !/^[0-9a-f]{32}$/.test(uh) || !/^[a-z]{1,10}$/.test(kind)) throw new Error('reward token: bad input');
  const nonce = randomBytes(12).toString('base64url');
  const exp = Math.floor(now / 1000) + TOKEN_TTL_SEC;
  const body = ['r1', kind, th, uh, nonce, exp.toString(36)].join('.');
  return { token: body + '.' + macOf(body).toString('base64url'), exp, nonce };
}
// 서명이 맞으면 내용을 돌려준다 (만료는 expired 로 따로 알려 준다). 틀리면 null
export function readRewardToken(tok, now = Date.now()) {
  const p = String(tok || '').split('.');
  if (p.length !== 7 || p[0] !== 'r1') return null;
  const [, kind, th, uh, nonce, exp36, mac] = p;
  if (!/^[a-z]{1,10}$/.test(kind) || !/^[0-9a-f]{32}$/.test(th) || !/^[0-9a-f]{32}$/.test(uh)
      || !/^[A-Za-z0-9_-]{16}$/.test(nonce) || !/^[0-9a-z]{1,10}$/.test(exp36) || !/^[A-Za-z0-9_-]{22}$/.test(mac)) return null;
  const got = Buffer.from(mac, 'base64url'), want = macOf(p.slice(0, 6).join('.'));
  // 22자의 마지막 글자는 아래 4비트가 버려져, 끝 글자만 바꾼 16가지 표가 같은 mac 으로 풀린다. 우리가 쓴 글자 그대로만 받는다
  if (got.toString('base64url') !== mac) return null;
  if (got.length !== want.length || !timingSafeEqual(got, want)) return null;
  const exp = parseInt(exp36, 36);
  return { kind, teamId: uuidOf(th), userId: uuidOf(uh), nonce, exp, expired: exp * 1000 < now };
}
