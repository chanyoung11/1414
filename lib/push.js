// 웹 푸시. VAPID 키가 없으면 조용히 아무것도 안 한다(로컬 개발).
import webpush from 'web-push';
import { q, one } from './db.js';
import { sendFcm, fcmConfigured } from './fcm.js';

const PUB = process.env.VAPID_PUBLIC_KEY || '';
const PRIV = process.env.VAPID_PRIVATE_KEY || '';
const SUBJ = process.env.VAPID_SUBJECT || 'mailto:hello@lets1414.com';
export const pushConfigured = () => !!(PUB && PRIV);
export const vapidPublicKey = () => PUB;
if (pushConfigured()) webpush.setVapidDetails(SUBJ, PUB, PRIV);

// 조용한 시간: 사용자가 정한 시간대(기본 22:00~08:00)에는 폰을 울리지 않는다.
// 알림함에는 그대로 쌓인다 — 아침에 열면 다 있다.
const QUIET_DEF = { on: true, from: 22, to: 8, tz: 9 };   // tz: KST 기준 시차
export function inQuietHours(prefs, now = new Date()) {
  const qh = { ...QUIET_DEF, ...((prefs && prefs.quiet) || {}) };
  if (!qh.on) return false;
  const h = (now.getUTCHours() + (+qh.tz || 0) + 24) % 24;
  const from = +qh.from, to = +qh.to;
  if (from === to) return false;
  return from < to ? (h >= from && h < to) : (h >= from || h < to);
}
// 이 종류의 알림을 이 사람이 받기로 했는지 (앱 안 토글과 같은 키)
function typeOn(prefs, type) {
  const off = (prefs && prefs.notiOff) || {};
  return off[type] !== true;
}

// 종류별 끄기·조용한 시간을 통과한 사람만 남긴다 (웹·앱에 똑같이 적용)
async function allowedUsers(ids, type) {
  if (!ids.length) return [];
  const rows = await q(`select id, coalesce(prefs,'{}'::jsonb) as prefs from users where id = any($1::uuid[])`, [ids]);
  return rows.filter((u) => {
    const prefs = u.prefs || {};
    if (type && !typeOn(prefs, type)) return false;
    if (inQuietHours(prefs)) return false;   // 알림함에는 이미 쌓였다
    return true;
  }).map((u) => u.id);
}

export async function sendPush(userIds, payload, { type = '' } = {}) {
  const ids0 = [...new Set(userIds)].filter(Boolean);
  if (!ids0.length) return 0;
  // 앱(FCM) 으로도 보낸다. 웹푸시와 따로 거르지 않고 같은 규칙을 쓴다
  let appSent = 0;
  if (fcmConfigured()) {
    try { appSent = await sendFcm(await allowedUsers(ids0, type), payload); }
    catch (e) { console.warn('fcm', e && e.message); }
  }
  if (!pushConfigured()) return appSent;
  const ids = ids0;
  const rows = await q(
    `select s.endpoint, s.keys, s.user_id as "userId", coalesce(u.prefs,'{}'::jsonb) as prefs
       from push_subs s join users u on u.id = s.user_id
      where s.user_id = any($1::uuid[])`, [ids]);
  let sent = 0;
  const dead = [];
  await Promise.all(rows.map(async (r) => {
    const prefs = r.prefs || {};
    if (type && !typeOn(prefs, type)) return;          // 종류별로 끈 사람
    if (inQuietHours(prefs)) return;                    // 조용한 시간 — 알림함에는 이미 쌓였다
    try {
      await webpush.sendNotification(
        { endpoint: r.endpoint, keys: r.keys },
        JSON.stringify(payload),
        { TTL: 12 * 3600, urgency: 'normal' });
      sent++;
    } catch (e) {
      const code = e && e.statusCode;
      if (code === 404 || code === 410) dead.push(r.endpoint);   // 구독이 죽었다
    }
  }));
  if (dead.length) await q('delete from push_subs where endpoint = any($1::text[])', [dead]);
  return sent + appSent;
}
