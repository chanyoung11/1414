// 네이티브 앱 푸시 (Firebase Cloud Messaging HTTP v1).
// 안드로이드 전용이다. iOS 는 @capacitor/push-notifications 가 Firebase 를 거치지 않고
// APNs 에 직접 등록하므로 lib/apns.js 가 따로 보낸다.
// 필요한 환경변수: FCM_PROJECT_ID, FCM_CLIENT_EMAIL, FCM_PRIVATE_KEY (서비스 계정)
import crypto from 'node:crypto';
import { q } from './db.js';

const PROJECT = process.env.FCM_PROJECT_ID || '';
const EMAIL = process.env.FCM_CLIENT_EMAIL || '';
const KEY = (process.env.FCM_PRIVATE_KEY || '').replace(/\\n/g, '\n');
export const fcmConfigured = () => !!(PROJECT && EMAIL && KEY);

let cachedToken = null, cachedExp = 0;
// 서비스 계정 → OAuth 액세스 토큰 (라이브러리 없이 JWT 를 직접 서명한다)
async function accessToken() {
  if (cachedToken && Date.now() < cachedExp - 60000) return cachedToken;
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const head = b64({ alg: 'RS256', typ: 'JWT' });
  const body = b64({ iss: EMAIL, scope: 'https://www.googleapis.com/auth/firebase.messaging',
    aud: 'https://oauth2.googleapis.com/token', iat: now, exp: now + 3600 });
  const sig = crypto.createSign('RSA-SHA256').update(`${head}.${body}`).sign(KEY).toString('base64url');
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${head}.${body}.${sig}` }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new Error((j.error_description || j.error || 'FCM 인증 실패'));
  cachedToken = j.access_token; cachedExp = Date.now() + (j.expires_in || 3600) * 1000;
  return cachedToken;
}

// userIds 의 모든 기기에 보낸다. 죽은 토큰은 지운다. 보낸 수를 돌려준다
export async function sendFcm(userIds, payload) {
  if (!fcmConfigured()) return 0;
  const ids = [...new Set(userIds)].filter(Boolean);
  if (!ids.length) return 0;
  const rows = await q(`select token, platform from push_tokens where platform='android' and user_id = any($1::uuid[])`, [ids]);
  if (!rows.length) return 0;
  let tok;
  try { tok = await accessToken(); } catch (e) { console.warn('fcm auth', e.message); return 0; }
  const url = `https://fcm.googleapis.com/v1/projects/${encodeURIComponent(PROJECT)}/messages:send`;
  const dead = [];
  let sent = 0;
  await Promise.all(rows.map(async (r) => {
    const msg = {
      message: {
        token: r.token,
        notification: { title: payload.title || '1414', body: payload.body || '' },
        data: { link: String(payload.link || '#/home'), type: String(payload.type || '') },
        android: { priority: 'HIGH', notification: { channel_id: 'conti', tag: payload.tag || 'conti' } },
        apns: { payload: { aps: { sound: 'default', 'thread-id': payload.tag || 'conti' } } },
      },
    };
    try {
      const res = await fetch(url, { method: 'POST', headers: { authorization: 'Bearer ' + tok, 'content-type': 'application/json' }, body: JSON.stringify(msg) });
      if (res.ok) { sent++; return; }
      const j = await res.json().catch(() => ({}));
      const code = (j.error && j.error.status) || '';
      // 지워진 앱·바뀐 토큰은 정리한다
      if (res.status === 404 || code === 'NOT_FOUND' || code === 'UNREGISTERED' || code === 'INVALID_ARGUMENT') dead.push(r.token);
      else console.warn('fcm', res.status, code);
    } catch (e) { console.warn('fcm send', e.message); }
  }));
  if (dead.length) await q('delete from push_tokens where token = any($1::text[])', [dead]);
  return sent;
}
