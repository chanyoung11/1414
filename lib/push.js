// 웹 푸시. VAPID 키가 없으면 조용히 아무것도 안 한다(로컬 개발).
import webpush from 'web-push';
import https from 'node:https';
import net from 'node:net';
import dns from 'node:dns';
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
// 모르는 브라우저의 알림을 막느니 아래 시간 제한으로 버틴다.
// 이름 끝의 점은 떼고 본다 (localhost. · metadata.google.internal. 이 그대로 통과했다). 점 없는 한 단어 이름
// (metadata 처럼 안쪽 DNS 가 푸는 것)도 안 받는다 — 공개 푸시 서비스는 모두 도메인이다.
// 이름이 멀쩡해도 안쪽 IP 로 풀리는 것(*.nip.io 같은)은 여기서 못 거른다 → 보낼 때 푼 주소를 다시 본다 (insideLookup)
export function pushEndpointOk(ep) {
  let u;
  try { u = new URL(String(ep || '')); } catch (e) { return false; }
  if (u.protocol !== 'https:' || u.username || u.password) return false;
  const h = u.hostname.toLowerCase().replace(/\.+$/, '');
  return !!h && h.includes('.') && !/(^|\.)(localhost|internal|local|arpa)$/.test(h)
    && !/^[\d.]+$/.test(h) && !h.startsWith('[');
}
// 안쪽 주소: 루프백·사설망·링크 로컬(클라우드 메타데이터 169.254.169.254)·CGNAT·멀티캐스트 등.
// ::ffff:10.0.0.1 처럼 IPv6 에 담긴 IPv4 도 IPv4 규칙으로 걸린다 (BlockList 가 그렇게 본다)
const INSIDE = new net.BlockList();
for (const [a, n] of [['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8], ['169.254.0.0', 16], ['172.16.0.0', 12],
  ['192.0.0.0', 24], ['192.168.0.0', 16], ['198.18.0.0', 15], ['224.0.0.0', 3]]) INSIDE.addSubnet(a, n, 'ipv4');
for (const [a, n] of [['::', 127], ['fc00::', 7], ['fe80::', 10], ['ff00::', 8]]) INSIDE.addSubnet(a, n, 'ipv6');
export const insideIp = (ip) => { const f = net.isIP(ip); return !f || INSIDE.check(ip, f === 6 ? 'ipv6' : 'ipv4'); };
// 푸시를 보낼 때 이름을 푸는 함수. 안쪽 주소로 풀리면 연결하지 않는다 — 구독할 때 공개였던 이름도
// 나중에 DNS 를 바꿔 안쪽을 가리키게 할 수 있어서, 이름을 볼 때가 아니라 연결할 때 본다
function insideLookup(host, opts, cb) {
  if (typeof opts === 'function') { cb = opts; opts = {}; }
  if (typeof opts === 'number') opts = { family: opts };
  opts = opts || {};
  dns.lookup(host, { ...opts, all: true }, (err, list) => {
    if (err) return cb(err);
    const out = (list || []).filter((a) => !insideIp(a.address));
    if (!out.length) return cb(Object.assign(new Error('안쪽 주소로는 푸시를 보내지 않아요: ' + host), { code: 'EINSIDE' }));
    if (opts.all) cb(null, out); else cb(null, out[0].address, out[0].family);
  });
}
// 한 곳이 답을 안 하면 발행·아침 크론이 통째로 멈춘다 (web-push 는 기본으로 시간 제한이 없다).
// timeout 은 '조용한' 연결만 끊으므로, 조금씩 흘려 보내며 붙잡는 곳까지 전체 시간도 자른다
const SEND_TIMEOUT = 10000;
function withDeadline(p, ms) {
  let t;
  const late = new Promise((_, rej) => { t = setTimeout(() => rej(new Error('푸시 시간 초과')), ms); });
  return Promise.race([p, late]).finally(() => clearTimeout(t));
}
// 구독 하나로 보낸다. 연결은 이 발송만의 에이전트로 맺고 끝나면(시간을 넘겨도) 통째로 부순다 —
// 시간 제한은 기다리기만 그만둘 뿐이라, 조금씩 흘려 보내는 곳은 소켓이 끝없이 열려 있었다
function sendOne(sub, body) {
  const agent = new https.Agent({ lookup: insideLookup });
  return withDeadline(webpush.sendNotification(sub, body, { TTL: 12 * 3600, urgency: 'normal', timeout: SEND_TIMEOUT, agent }), SEND_TIMEOUT + 2000)
    .finally(() => agent.destroy());
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
async function allowedUsers(ids, type, force) {
  if (!ids.length) return [];
  if (force) return ids;
  const rows = await q(`select id, coalesce(prefs,'{}'::jsonb) as prefs from users where id = any($1::uuid[])`, [ids]);
  return rows.filter((u) => {
    const prefs = u.prefs || {};
    if (type && !typeOn(prefs, type)) return false;
    if (inQuietHours(prefs)) return false;   // 알림함에는 이미 쌓였다
    return true;
  }).map((u) => u.id);
}

// force: 본인이 방금 누른 시험 발송처럼 조용한 시간·종류 끄기를 건너뛰고 보낸다.
// 걸러 내면 밤(기본 22~08시)에는 알림이 켜져 있어도 보낸 수가 0 이라 '보낼 기기가 없어요'로 보였다
export async function sendPush(userIds, payload, { type = '', force = false } = {}) {
  const ids0 = [...new Set(userIds)].filter(Boolean);
  if (!ids0.length) return 0;
  // 앱(FCM) 으로도 보낸다. 웹푸시와 따로 거르지 않고 같은 규칙을 쓴다
  let appSent = 0;
  if (fcmConfigured() || apnsConfigured()) {
    const ok = await allowedUsers(ids0, type, force);
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
    if (!force && type && !typeOn(prefs, type)) return;   // 종류별로 끈 사람
    if (!force && inQuietHours(prefs)) return;             // 조용한 시간 — 알림함에는 이미 쌓였다
    // 거르기 전에 들어온 옛 구독(IP·localhost 주소)은 보내지 않는다. 죽었다고 확인된 건 아니라 지우지는 않는다
    if (!pushEndpointOk(r.endpoint)) return;
    try {
      await sendOne({ endpoint: r.endpoint, keys: r.keys }, JSON.stringify(payload));
      sent++;
    } catch (e) {
      const code = e && e.statusCode;
      if (code === 404 || code === 410) dead.push(r.endpoint);   // 구독이 죽었다
    }
  }));
  if (dead.length) await q('delete from push_subs where endpoint = any($1::text[])', [dead]);
  return sent + appSent;
}
