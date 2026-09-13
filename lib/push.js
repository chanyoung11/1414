// 웹 푸시. VAPID 키가 없으면 조용히 아무것도 안 한다(로컬 개발).
import webpush from 'web-push';
import { q, one } from './db.js';

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

export async function sendPush(userIds, payload, { type = '' } = {}) {
  if (!pushConfigured()) return 0;
  const ids = [...new Set(userIds)].filter(Boolean);
  if (!ids.length) return 0;
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
  return sent;
}
