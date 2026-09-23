// iOS 푸시(lib/apns.js) 확인 (테스트에서 부른다).
// 애플 대신 로컬 HTTP/2 서버를 세워 두고 http2.connect 를 그쪽으로 돌린다. 진짜 애플에는 안 간다.
// 토큰은 로컬 DB(push_tokens)에 넣었다가 끝나면 지운다.
//   DATABASE_URL=postgres://postgres:pg@localhost:54329/postgres node scripts/apns-check.mjs
import http2 from 'node:http2';
import crypto from 'node:crypto';

const DB = process.env.DATABASE_URL || 'postgres://postgres:pg@localhost:54329/postgres';
if (!/@(localhost|127\.0\.0\.1)[:/]/.test(DB)) { console.log('BAD 로컬 DB 가 아니라서 안 돌린다'); process.exit(1); }
process.env.DATABASE_URL = DB;
const { privateKey } = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
process.env.APNS_KEY_ID = 'KEYCHECK01'; process.env.APNS_TEAM_ID = 'TEAMCHECK1';
process.env.APNS_PRIVATE_KEY = privateKey.export({ type: 'pkcs8', format: 'pem' });
delete process.env.APNS_ENV;   // 기본 = 운영 서버 먼저, 거부되면 샌드박스

// 가짜 애플 서버들. 이름 → 스트림을 받았을 때 하는 일
const ACT = {
  ok: (st) => { st.respond({ ':status': 200 }); st.end(); },
  bad: (st) => { st.respond({ ':status': 400, 'content-type': 'application/json' }); st.end('{"reason":"BadDeviceToken"}'); },
  wrongkey: (st) => { st.respond({ ':status': 403, 'content-type': 'application/json' }); st.end('{"reason":"BadEnvironmentKeyInToken"}'); },
  gone: (st) => { st.respond({ ':status': 410, 'content-type': 'application/json' }); st.end('{"reason":"Unregistered"}'); },
  // 보내는 중에 애플이 연결을 끊는다 (ECONNRESET)
  reset: (st) => { setTimeout(() => st.session.socket.resetAndDestroy(), 100); },
  // 보내는 중에 애플이 GOAWAY(INTERNAL_ERROR)로 닫는다
  goaway: (st) => { setTimeout(() => st.session.goaway(http2.constants.NGHTTP2_INTERNAL_ERROR), 100); },
};
const PORT = {};
const servers = [];
for (const name of Object.keys(ACT)) {
  const s = http2.createServer();
  s.on('stream', (st) => { st.on('error', () => {}); ACT[name](st); });
  s.on('sessionError', () => {});
  await new Promise((r) => s.listen(0, '127.0.0.1', r));
  PORT[name] = s.address().port; servers.push(s);
}
const route = { prod: 'ok', sandbox: 'ok' };
const orig = http2.connect;
http2.connect = (host, opts) => {
  const which = host === 'https://api.push.apple.com' ? route.prod : host === 'https://api.sandbox.push.apple.com' ? route.sandbox : null;
  if (!which) throw new Error('모르는 주소 ' + host);
  return orig(which === 'down' ? 'http://127.0.0.1:1' : `http://127.0.0.1:${PORT[which]}`, opts);
};

const { sendApns } = await import(process.env.APNS_MODULE || '../lib/apns.js');
const { q, one } = await import('../lib/db.js');

const tag = Date.now().toString(36);
const u = await one(`insert into users(username, password_hash, display_name) values($1,'','apns 확인') returning id`, ['apnschk-' + tag]);
const TOKENS = ['a', 'b'].map((x) => `chk${tag}${x}`);
const bad = [];
async function run(name, prod, sandbox, want) {
  await q('delete from push_tokens where user_id=$1', [u.id]);
  for (const t of TOKENS) await q(`insert into push_tokens(token, user_id, platform) values($1,$2,'ios')`, [t, u.id]);
  route.prod = prod; route.sandbox = sandbox;
  const t0 = Date.now();
  const sent = await Promise.race([
    sendApns([u.id], { title: '확인', body: name }),
    new Promise((r) => setTimeout(() => r('hang'), 25000)),
  ]);
  const left = (await q('select token from push_tokens where user_id=$1', [u.id])).length;
  const got = `sent=${sent} left=${left}`;
  const ok = got === `sent=${want.sent} left=${want.left}`;
  console.log(ok ? 'ok ' : 'BAD', name, got, `(${Date.now() - t0}ms)`);
  if (!ok) bad.push(`${name}: ${got}, want sent=${want.sent} left=${want.left}`);
}
const only = process.argv[2];
const CASES = [
  // F103: 운영 서버가 안 닿는데 샌드박스가 BadDeviceToken → 지우면 안 된다
  ['운영 안 닿음 + 샌드박스 BadDeviceToken', 'down', 'bad', { sent: 0, left: 2 }],
  ['운영 BadDeviceToken + 샌드박스 안 닿음', 'bad', 'down', { sent: 0, left: 2 }],
  ['운영 BadDeviceToken + 샌드박스 키 환경 다름', 'bad', 'wrongkey', { sent: 0, left: 2 }],
  // 정리는 여전히 된다
  ['운영·샌드박스 둘 다 BadDeviceToken', 'bad', 'bad', { sent: 0, left: 0 }],
  ['운영 410 Unregistered', 'gone', 'ok', { sent: 0, left: 0 }],
  ['운영 BadDeviceToken → 샌드박스로 감', 'bad', 'ok', { sent: 2, left: 2 }],
  ['정상', 'ok', 'ok', { sent: 2, left: 2 }],
  // F34: 연결된 뒤 세션 오류가 나도 프로세스가 죽지 않고, 토큰도 안 지운다
  ['보내는 중 연결 끊김(ECONNRESET)', 'reset', 'ok', { sent: 0, left: 2 }],
  ['보내는 중 GOAWAY(INTERNAL_ERROR)', 'goaway', 'ok', { sent: 0, left: 2 }],
];
try {
  for (const c of CASES) if (!only || c[0].includes(only)) await run(...c);
} finally {
  await q('delete from users where id=$1', [u.id]);
  servers.forEach((s) => s.close());
}
console.log(bad.length ? 'BAD ' + bad.join(' / ') : 'OK');
process.exit(bad.length ? 1 : 0);
