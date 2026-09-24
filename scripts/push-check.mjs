// 웹 푸시가 답 없는 구독 주소에 붙잡히지 않는지 확인 (테스트에서 부른다).
// 로컬에 '아무 말 없는 서버'와 '답을 조금씩 흘리는 https 서버'를 세우고, 구독을 로컬 DB 에 넣어 sendPush 를 부른다.
// - 시간을 넘긴 발송의 소켓은 닫힌다 (흘리는 서버 쪽에서 연결이 끊긴 것을 본다)
// - 안쪽 주소로 풀리는 이름·옛 IP 구독으로는 연결조차 안 한다 (세는 서버에 아무것도 안 온다)
// 가짜 이름(*.pushchk.test)은 이 프로세스 안에서만 푼다: dns.lookup 을 바꾸고, 시간 제한을 보는 두 이름은
// tls.connect 에서 로컬 서버로 돌린다 (안쪽 주소 막기는 연결할 때 보므로 그대로 두면 로컬 서버에 못 닿는다)
//   node scripts/push-check.mjs        → 마지막 줄 OK
import net from 'node:net';
import tls from 'node:tls';
import dns from 'node:dns';
import https from 'node:https';
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const DB = process.env.DATABASE_URL || 'postgres://postgres:pg@localhost:54329/postgres';
if (!/@(localhost|127\.0\.0\.1)[:/]/.test(DB)) { console.log('BAD 로컬 DB 가 아니라서 안 돌린다'); process.exit(1); }
process.env.DATABASE_URL = DB;
// dev-local.sh 의 개발용 키
process.env.VAPID_PUBLIC_KEY = 'BBq9nqw8YvL_wusVh4V6jQIXo-nph79oqnhr8VhzTfO67ssHN4FwThabeFwyq7YKeYl3lIOHJRklS6kfO8sbEVo';
process.env.VAPID_PRIVATE_KEY = 'Qy2iS5vLHI40osMnj_7AQwXeTtFRf0aP24RkV21cMY8';
for (const k of ['FCM_PROJECT_ID', 'FCM_USE_METADATA', 'APNS_KEY_ID']) delete process.env[k];
// 흘리는 서버는 스스로 만든 인증서를 쓴다. 이 확인 프로세스에서만 믿는다
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
process.removeAllListeners('warning');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pushchk-'));
execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=127.0.0.1',
  '-keyout', path.join(dir, 'k.pem'), '-out', path.join(dir, 'c.pem')], { stdio: 'ignore' });

// 1) 연결만 받고 아무 말도 안 한다
let silentHits = 0;
const silent = net.createServer((s) => { silentHits++; s.on('error', () => {}); });
// 2) 머리는 바로 주고 몸은 1초에 한 글자씩 끝없이 — 연결이 '조용'하지 않아 소켓 시간 제한에 안 걸린다
let dripped = 0, dripClosedAt = 0;
const drip = https.createServer({ key: fs.readFileSync(path.join(dir, 'k.pem')), cert: fs.readFileSync(path.join(dir, 'c.pem')) }, (req, res) => {
  dripped++; res.writeHead(201); const iv = setInterval(() => res.write('.'), 1000);
  res.on('close', () => { clearInterval(iv); dripClosedAt = Date.now(); });
});
// 3) 오는 연결을 세기만 한다 — 안쪽 주소 막기가 뚫리면 여기로 온다
let insideHits = 0;
const inside = net.createServer((s) => { insideHits++; s.on('error', () => {}); s.destroy(); });
for (const s of [silent, drip, inside]) await new Promise((r) => s.listen(0, '127.0.0.1', r));

// 가짜 이름 풀기: *.pushchk.test 는 모두 127.0.0.1 (안쪽 주소 — 막혀야 한다)
const realLookup = dns.lookup;
dns.lookup = function (host, opts, cb) {
  if (!/\.pushchk\.test$/.test(String(host))) return realLookup.apply(this, arguments);
  if (typeof opts === 'function') { cb = opts; opts = {}; }
  const a = { address: '127.0.0.1', family: 4 };
  process.nextTick(() => (opts && opts.all ? cb(null, [a]) : cb(null, a.address, a.family)));
};
// 시간 제한을 보는 두 이름은 이름 풀기를 건너뛰고 로컬 서버로 곧장 붙인다
const realTls = tls.connect;
tls.connect = function (...args) {
  const o = args[0];
  if (o && typeof o === 'object' && /^(silent|drip)\.pushchk\.test$/.test(o.host || '')) args[0] = { ...o, host: '127.0.0.1', lookup: undefined };
  return realTls.apply(this, args);
};

const { sendPush, pushEndpointOk } = await import(process.env.PUSH_MODULE || '../lib/push.js');
const { q, one } = await import('../lib/db.js');
const tag = Date.now().toString(36);
// 조용한 시간이면 보내지도 않으니 꺼 둔다
const u = await one(`insert into users(username, password_hash, display_name, prefs) values($1,'','푸시 확인','{"quiet":{"on":false}}') returning id`, ['pushchk-' + tag]);
const KEYS = JSON.stringify({ p256dh: 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM', auth: 'tBHItJI5svbpez7KI4CCXg' });
const bad = [];
// 구독 주소 거르기 (API 가 받기 전에 부른다)
const NO = ['http://fcm.googleapis.com/x', 'https://127.0.0.1/x', 'https://localhost/x', 'https://localhost./x', 'https://a.localhost./x',
  'https://metadata.google.internal/x', 'https://metadata.google.internal./x', 'https://metadata/x', 'https://metadata./x',
  'https://printer.local/x', 'https://1.0.0.127.in-addr.arpa/x', 'https://[::1]/x', 'https://2130706433/x', 'https://0x7f.1/x',
  'https://u:p@fcm.googleapis.com/x', 'javascript:alert(1)', ''];
const YES = ['https://fcm.googleapis.com/fcm/send/abc', 'https://updates.push.services.mozilla.com/wpush/v2/abc',
  'https://web.push.apple.com/abc', 'https://wns2-par02p.notify.windows.com/w/?token=abc', 'https://FCM.googleapis.com./fcm/send/abc'];
for (const ep of NO) if (pushEndpointOk(ep)) bad.push('받으면 안 되는 주소를 받음: ' + ep);
for (const ep of YES) if (!pushEndpointOk(ep)) bad.push('정상 주소를 거절: ' + ep);
try {
  const P = (s) => s.address().port;
  const eps = {
    silent: `https://silent.pushchk.test:${P(silent)}/push/${tag}`,
    drip: `https://drip.pushchk.test:${P(drip)}/push/${tag}`,
    // 이름은 공개처럼 보여도 안쪽 주소로 풀린다 (*.nip.io 같은 것, 구독 뒤에 DNS 를 바꾼 것)
    rebind: `https://inside.pushchk.test:${P(inside)}/push/${tag}`,
    // 거르기 전에 DB 에 들어온 옛 구독
    ip: `https://127.0.0.1:${P(inside)}/push/${tag}`,
    dot: `https://localhost.:${P(inside)}/push/${tag}`,
  };
  for (const ep of Object.values(eps)) await q('insert into push_subs(endpoint, user_id, keys) values($1,$2,$3)', [ep, u.id, KEYS]);
  const t0 = Date.now();
  const r = await Promise.race([sendPush([u.id], { title: '확인', body: '시간 제한', link: '#/home' }), new Promise((ok) => setTimeout(() => ok('hang'), 30000))]);
  const ms = Date.now() - t0;
  console.log('sendPush →', r, `(${ms}ms)`);
  if (r === 'hang') bad.push('답 없는 구독에 30초 넘게 붙잡힘');
  else if (ms > 16000) bad.push(`너무 오래 걸림 ${ms}ms`);
  if (r !== 'hang' && r !== 0) bad.push('보낸 수가 0 이 아님: ' + r);
  if (dripped !== 1 || !silentHits) bad.push('답 없는·흘리는 서버까지 요청이 안 감 (확인이 헛돎)');
  // 시간을 넘긴 발송의 연결은 닫혀야 한다. 기다리기만 그만두면 흘리는 서버가 소켓을 끝없이 붙잡는다
  if (r !== 'hang') {
    for (let i = 0; i < 30 && !dripClosedAt; i++) await new Promise((ok) => setTimeout(ok, 100));
    console.log('흘리는 연결', dripClosedAt ? `닫힘 (+${dripClosedAt - t0 - ms}ms)` : '안 닫힘');
    if (!dripClosedAt) bad.push('시간을 넘긴 뒤에도 흘리는 연결이 열려 있음');
  }
  if (insideHits) bad.push(`안쪽 주소로 연결함 ${insideHits}번 (이름이 127.0.0.1 로 풀리는 구독 · 옛 IP 구독)`);
  // 죽었다고 확인된 게 아니니 구독은 남아 있어야 한다 (404/410 만 지운다)
  const left = (await q('select count(*)::int as n from push_subs where user_id=$1', [u.id]))[0].n;
  if (left !== Object.keys(eps).length) bad.push('구독이 지워짐: ' + left);
} finally {
  await q('delete from users where id=$1', [u.id]);
  silent.close(); drip.closeAllConnections?.(); drip.close(); inside.close();
  fs.rmSync(dir, { recursive: true, force: true });
}
console.log(bad.length ? 'BAD ' + bad.join(' / ') : 'OK');
process.exit(bad.length ? 1 : 0);
