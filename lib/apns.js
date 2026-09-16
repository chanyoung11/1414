// iOS 푸시 (Apple Push Notification service, HTTP/2 + JWT).
// @capacitor/push-notifications 의 iOS 는 Firebase 를 거치지 않고 APNs 에 직접 등록해
// APNs 토큰을 준다. 그래서 FCM 과 따로 보낸다.
// 필요한 환경변수: APNS_KEY_ID, APNS_TEAM_ID, APNS_PRIVATE_KEY(.p8 내용), APNS_BUNDLE_ID
// APNS_ENV=production 이면 운영 서버, 아니면 개발 서버로 보낸다.
import crypto from 'node:crypto';
import { q } from './db.js';

const KEY_ID = process.env.APNS_KEY_ID || '';
const TEAM_ID = process.env.APNS_TEAM_ID || '';
const KEY = (process.env.APNS_PRIVATE_KEY || '').replace(/\\n/g, '\n');
const BUNDLE = process.env.APNS_BUNDLE_ID || 'com.lets1414.app';
const HOST = process.env.APNS_ENV === 'production' ? 'https://api.push.apple.com' : 'https://api.sandbox.push.apple.com';
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

export async function sendApns(userIds, payload) {
  if (!apnsConfigured()) return 0;
  const ids = [...new Set(userIds)].filter(Boolean);
  if (!ids.length) return 0;
  const rows = await q(`select token from push_tokens where platform='ios' and user_id = any($1::uuid[])`, [ids]);
  if (!rows.length) return 0;
  let jwt;
  try { jwt = authToken(); } catch (e) { console.warn('apns jwt', e.message); return 0; }
  const dead = [];
  let sent = 0;
  const note = {
    aps: { alert: { title: payload.title || '1414', body: payload.body || '' }, sound: 'default',
           'thread-id': payload.tag || 'conti' },
    link: String(payload.link || '#/home'), type: String(payload.type || ''),
  };
  await Promise.all(rows.map(async (r) => {
    try {
      const res = await fetch(`${HOST}/3/device/${encodeURIComponent(r.token)}`, {
        method: 'POST',
        headers: { authorization: 'bearer ' + jwt, 'apns-topic': BUNDLE, 'apns-push-type': 'alert', 'apns-priority': '10' },
        body: JSON.stringify(note),
      });
      if (res.ok) { sent++; return; }
      const t = await res.text().catch(() => '');
      // 지운 앱·바뀐 토큰은 정리한다
      if (res.status === 410 || /BadDeviceToken|Unregistered/.test(t)) dead.push(r.token);
      else console.warn('apns', res.status, t.slice(0, 120));
    } catch (e) { console.warn('apns send', e.message); }
  }));
  if (dead.length) await q('delete from push_tokens where token = any($1::text[])', [dead]);
  return sent;
}
