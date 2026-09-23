// iOS 푸시 (Apple Push Notification service).
// @capacitor/push-notifications 의 iOS 는 Firebase 를 거치지 않고 APNs 에 직접 등록해
// APNs 토큰을 준다. 그래서 FCM(안드로이드)과 따로 보낸다.
//
// APNs 는 HTTP/2 만 받는다. node 의 fetch(undici)는 HTTP/1.1 이라 연결이 깨지므로
// node:http2 를 직접 쓴다.
//
// 필요한 환경변수: APNS_KEY_ID, APNS_TEAM_ID, APNS_PRIVATE_KEY(.p8 내용), APNS_BUNDLE_ID
// APNS_ENV=production 이면 운영 서버, 아니면 개발(샌드박스) 서버로 보낸다.
import crypto from 'node:crypto';
import http2 from 'node:http2';
import { q } from './db.js';

const KEY_ID = process.env.APNS_KEY_ID || '';
const TEAM_ID = process.env.APNS_TEAM_ID || '';
const KEY = (process.env.APNS_PRIVATE_KEY || '').replace(/\\n/g, '\n');
const BUNDLE = process.env.APNS_BUNDLE_ID || 'com.lets1414.app';
const PROD = 'https://api.push.apple.com';
const SANDBOX = 'https://api.sandbox.push.apple.com';
// 같은 토큰이라도 환경이 다르면 거부된다. Xcode 로 깐 개발 빌드는 sandbox,
// 테스트플라이트·앱스토어 빌드는 production 을 쓴다. 토큰만 봐서는 구분할 수 없으므로
// 기본 환경에서 거부되면 반대쪽으로 한 번 더 보낸다.
const HOST = process.env.APNS_ENV === 'sandbox' ? SANDBOX : PROD;
const OTHER = HOST === PROD ? SANDBOX : PROD;
export const apnsConfigured = () => !!(KEY_ID && TEAM_ID && KEY);

let tok = null, tokAt = 0;
// APNs 는 ES256 으로 서명한 JWT 를 쓴다. 한 시간까지 재사용할 수 있다
function authToken() {
  if (tok && Date.now() - tokAt < 45 * 60 * 1000) return tok;
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const head = b64({ alg: 'ES256', kid: KEY_ID });
  const body = b64({ iss: TEAM_ID, iat: Math.floor(Date.now() / 1000) });
  const sig = crypto.createSign('SHA256').update(`${head}.${body}`)
    .sign({ key: KEY, dsaEncoding: 'ieee-p1363' }).toString('base64url');
  tok = `${head}.${body}.${sig}`; tokAt = Date.now();
  return tok;
}

// 한 세션으로 여러 기기에 보낸다. 다 보내면 닫는다
function openSession(host) {
  return new Promise((res, rej) => {
    const s = http2.connect(host, { settings: { enablePush: false } });
    const done = (fn, v) => { s.off('connect', ok); s.off('error', bad); fn(v); };
    const ok = () => done(res, s);
    const bad = (e) => { try { s.destroy(); } catch {} done(rej, e); };
    s.once('connect', ok); s.once('error', bad);
    setTimeout(() => bad(new Error('APNs 연결 시간 초과')), 8000).unref?.();
  });
}

function post(session, token, jwt, note) {
  return new Promise((res) => {
    const body = Buffer.from(JSON.stringify(note));
    const req = session.request({
      ':method': 'POST', ':path': `/3/device/${token}`,
      authorization: 'bearer ' + jwt, 'apns-topic': BUNDLE,
      'apns-push-type': 'alert', 'apns-priority': '10',
      'content-type': 'application/json', 'content-length': body.length,
    });
    let status = 0, text = '';
    req.setTimeout(8000, () => { req.close(); res({ status: 0, text: '시간 초과' }); });
    req.on('response', (h) => { status = h[':status'] || 0; });
    req.on('data', (c) => { text += c; });
    req.on('end', () => res({ status, text }));
    req.on('error', (e) => res({ status: 0, text: e.message }));
    req.end(body);
  });
}

export async function sendApns(userIds, payload) {
  if (!apnsConfigured()) return 0;
  const ids = [...new Set(userIds)].filter(Boolean);
  if (!ids.length) return 0;
  const rows = await q(`select token from push_tokens where platform='ios' and user_id = any($1::uuid[])`, [ids]);
  if (!rows.length) return 0;

  let jwt;
  try { jwt = authToken(); } catch (e) { console.warn('apns jwt', e.message); return 0; }

  const note = {
    aps: {
      alert: { title: payload.title || '1414', body: payload.body || '' },
      sound: 'default', 'thread-id': payload.tag || 'conti',
    },
    // teamId: 여러 팀에 있는 사람이 누르면 앱이 그 팀으로 바꾼 뒤 링크를 연다 (링크는 팀 안 주소)
    link: String(payload.link || '#/home'), type: String(payload.type || ''), teamId: String(payload.teamId || ''),
  };
  const dead = [];
  let sent = 0;

  // 한 환경으로 보내고, 환경이 안 맞아 거부된 토큰만 돌려준다
  async function round(host, tokens) {
    let session;
    try { session = await openSession(host); }
    catch (e) { console.warn('apns connect', host, e.message); return tokens; }
    const retry = [];
    try {
      const out = await Promise.all(tokens.map((t) => post(session, t, jwt, note)));
      out.forEach((o, i) => {
        if (o.status === 200) { sent++; return; }
        // 환경이 달라 거부된 것뿐일 수 있으니 여기서 지우지 않는다
        if (/BadDeviceToken|BadEnvironmentKeyInToken/.test(o.text)) { retry.push(tokens[i]); return; }
        if (o.status === 410 || /Unregistered/.test(o.text)) { dead.push(tokens[i]); return; }
        console.warn('apns', o.status, String(o.text).slice(0, 120));
      });
    } finally { try { session.close(); } catch {} }
    return retry;
  }

  const left = await round(HOST, rows.map((r) => r.token));
  // 반대 환경에서도 거부되면 진짜 죽은 토큰이다
  if (left.length) dead.push(...await round(OTHER, left));

  if (dead.length) await q('delete from push_tokens where token = any($1::text[])', [dead]);
  return sent;
}
