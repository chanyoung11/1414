// 웹 푸시. VAPID 키가 없으면 조용히 아무것도 안 한다(로컬 개발).
import webpush from 'web-push';
import { q, one } from './db.js';
import { sendFcm, fcmConfigured } from './fcm.js';
import { sendApns, apnsConfigured } from './apns.js';

const PUB = process.env.VAPID_PUBLIC_KEY || '';
const PRIV = process.env.VAPID_PRIVATE_KEY || '';
const SUBJ = process.env.VAPID_SUBJECT || 'mailto:hello@lets1414.com';
export const pushConfigured = () => !!(PUB && PRIV);
export const vapidPublicKey = () => PUB;
if (pushConfigured()) webpush.setVapidDetails(SUBJ, PUB, PRIV);

// 구독 주소(endpoint)는 브라우저가 주지만 서버에는 사용자가 아무 값이나 올릴 수 있다.
// 서버가 발행·크론 중에 그 주소로 직접 요청을 보내므로 https 공개 주소만 받는다 (IP·localhost 로 안쪽을 찌르지 못하게).
// 푸시 서비스 이름으로 거르지는 않는다 — 웨일 같은 크로미엄 계열이 어디를 쓰는지 다 알 수 없어서,
// 모르는 브라우저의 알림을 막느니 아래 시간 제한으로 버틴다
export function pushEndpointOk(ep) {
  let u;
  try { u = new URL(String(ep || '')); } catch (e) { return false; }
  if (u.protocol !== 'https:' || u.username || u.password) return false;
  const h = u.hostname.toLowerCase();
  return !!h && h !== 'localhost' && !h.endsWith('.localhost') && !h.endsWith('.internal')
    && !/^[\d.]+$/.test(h) && !h.startsWith('[');
}
// 한 곳이 답을 안 하면 발행·아침 크론이 통째로 멈춘다 (web-push 는 기본으로 시간 제한이 없다).
// timeout 은 '조용한' 연결만 끊으므로, 조금씩 흘려 보내며 붙잡는 곳까지 전체 시간도 자른다
const SEND_TIMEOUT = 10000;
function withDeadline(p, ms) {
  let t;
  const late = new Promise((_, rej) => { t = setTimeout(() => rej(new Error('푸시 시간 초과')), ms); });
  return Promise.race([p, late]).finally(() => clearTimeout(t));
}

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
  if (fcmConfigured() || apnsConfigured()) {
    const ok = await allowedUsers(ids0, type);
    if (ok.length) {
      const [a, b] = await Promise.all([
        fcmConfigured() ? sendFcm(ok, payload).catch((e) => { console.warn('fcm', e && e.message); return 0; }) : 0,
        apnsConfigured() ? sendApns(ok, payload).catch((e) => { console.warn('apns', e && e.message); return 0; }) : 0,
      ]);
      appSent = a + b;
    }
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
      await withDeadline(webpush.sendNotification(
        { endpoint: r.endpoint, keys: r.keys },
        JSON.stringify(payload),
        { TTL: 12 * 3600, urgency: 'normal', timeout: SEND_TIMEOUT }), SEND_TIMEOUT + 2000);
      sent++;
    } catch (e) {
      const code = e && e.statusCode;
      if (code === 404 || code === 410) dead.push(r.endpoint);   // 구독이 죽었다
    }
  }));
  if (dead.length) await q('delete from push_subs where endpoint = any($1::text[])', [dead]);
  return sent + appSent;
}
