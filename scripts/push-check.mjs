// 웹 푸시가 답 없는 구독 주소에 붙잡히지 않는지 확인 (테스트에서 부른다).
// 로컬에 '아무 말 없는 서버'와 '답을 조금씩 흘리는 https 서버'를 세우고, 구독을 로컬 DB 에 넣어 sendPush 를 부른다.
//   node scripts/push-check.mjs        → 마지막 줄 OK
import net from 'node:net';
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
const silent = net.createServer((s) => { s.on('error', () => {}); });
// 2) 머리는 바로 주고 몸은 1초에 한 글자씩 끝없이 — 연결이 '조용'하지 않아 소켓 시간 제한에 안 걸린다
let dripped = 0;
const drip = https.createServer({ key: fs.readFileSync(path.join(dir, 'k.pem')), cert: fs.readFileSync(path.join(dir, 'c.pem')) }, (req, res) => {
  dripped++; res.writeHead(201); const iv = setInterval(() => res.write('.'), 1000); res.on('close', () => clearInterval(iv));
});
for (const s of [silent, drip]) await new Promise((r) => s.listen(0, '127.0.0.1', r));

const { sendPush } = await import(process.env.PUSH_MODULE || '../lib/push.js');
const { q, one } = await import('../lib/db.js');
const tag = Date.now().toString(36);
// 조용한 시간이면 보내지도 않으니 꺼 둔다
const u = await one(`insert into users(username, password_hash, display_name, prefs) values($1,'','푸시 확인','{"quiet":{"on":false}}') returning id`, ['pushchk-' + tag]);
const KEYS = JSON.stringify({ p256dh: 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM', auth: 'tBHItJI5svbpez7KI4CCXg' });
const bad = [];
try {
  for (const s of [silent, drip]) {
    await q('insert into push_subs(endpoint, user_id, keys) values($1,$2,$3)', [`https://127.0.0.1:${s.address().port}/push/${tag}`, u.id, KEYS]);
  }
  const t0 = Date.now();
  const r = await Promise.race([sendPush([u.id], { title: '확인', body: '시간 제한', link: '#/home' }), new Promise((ok) => setTimeout(() => ok('hang'), 30000))]);
  const ms = Date.now() - t0;
  console.log('sendPush →', r, `(${ms}ms)`);
  if (r === 'hang') bad.push('답 없는 구독에 30초 넘게 붙잡힘');
  else if (ms > 16000) bad.push(`너무 오래 걸림 ${ms}ms`);
  if (r !== 'hang' && r !== 0) bad.push('보낸 수가 0 이 아님: ' + r);
  if (dripped !== 1) bad.push('흘리는 서버까지 요청이 안 감 (확인이 헛돎)');
  // 죽었다고 확인된 게 아니니 구독은 남아 있어야 한다 (404/410 만 지운다)
  const left = (await q('select count(*)::int as n from push_subs where user_id=$1', [u.id]))[0].n;
  if (left !== 2) bad.push('구독이 지워짐: ' + left);
} finally {
  await q('delete from users where id=$1', [u.id]);
  silent.close(); drip.closeAllConnections?.(); drip.close();
  fs.rmSync(dir, { recursive: true, force: true });
}
console.log(bad.length ? 'BAD ' + bad.join(' / ') : 'OK');
process.exit(bad.length ? 1 : 0);
