// 보상형 광고(코드 인식 1곡) 서버 검사 — 로컬 DB 에서만, 밖으로 나가는 호출 없이.
//
// 사용: node tests/test_reward_ssv.mjs
//   (DATABASE_URL 을 주지 않으면 로컬 도커 postgres://postgres:pg@localhost:54329/postgres. 스키마는 이 검사가 먼저 적용한다 — 멱등)
//
// 1) 서명 확인(lib/admob.js)을 구글과 똑같이: 우리 ECDSA P-256 키 한 쌍을 만들고, 로컬 서버가 구글 키 파일 모양
//    (verifier-keys.json)으로 공개키를 내준다. 콜백은 구글처럼 만든다 — 값은 퍼센트 인코딩해 보내고, 서명은
//    '디코딩한' 쿼리(signature 앞까지)에 한다 (tink RewardedAdsVerifier · testShouldVerifyWithEncodedUrl).
//    맞는 것은 통과, 한 글자라도 바꾼 것·날것에 서명한 것·모양이 틀린 것은 거절. 값은 서명한 글자에서 읽어, 남의 광고 단위로
//    받은 진짜 서명 콜백의 '&' 를 %26 으로 감춰 다시 나눈 위조(custom_data·user_id 로 ad_unit·표·transaction_id 끼우기)도 거절.
//    키 캐시(한 번만 받기 · 동시에 와도 한 번 ·
//    모르는 key_id 로 쏟아지지 않기 · 시간 제한 · 받기가 실패하면 남은 키로 · 빈 목록이 캐시를 지우지 않기).
// 2) API 전체를 이 프로세스 안에서: 보상 표 · 광고 단위 목록 · 시각 · 인도자 · 같은 콜백/표 한 번만 · 거절한 콜백도 다시 못 씀 ·
//    하루 3개·한 달 20개를 동시에 보내도 넘지 않음 · 한도 넘긴 코드 인식은 보상 1개를 쓰고 사용량(10)에 안 잡힘 ·
//    같은 곡을 동시에 보내도 보상 없이 통과하지 못함 · 자정 무렵 보상 · 보상 곡 환불(사용량 그대로 · 월 환불 횟수 안 씀 · 한 번만) ·
//    엔진 실패면 보상을 돌려줌 · 꺼져 있으면 아무것도 안 함
// 만든 팀·사용자·기록은 끝에서 지운다.
import http from 'node:http';
import { generateKeyPairSync, sign, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.DATABASE_URL = process.env.DATABASE_URL || 'postgres://postgres:pg@localhost:54329/postgres';
if (!/@(localhost|127\.0\.0\.1)[:/]/.test(process.env.DATABASE_URL)) { console.error('로컬 DB 에서만 돌린다'); process.exit(1); }
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
process.env.ENFORCE_PLAN = '1';
process.env.GEMINI_API_KEY = 'fake';   // 아래에서 fetch 를 가로채 원하는 결과를 준다 (진짜로 부르지 않는다)
delete process.env.GOOGLE_VISION_KEY; delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
process.env.BLOB_LOCAL_DIR = process.env.BLOB_LOCAL_DIR || path.join(root, '.localblob');
const UNIT = '5550001111', UNIT2 = '5550002222';
process.env.ADMOB_REWARD_UNITS = `ca-app-pub-5011605715320185/${UNIT}, ${UNIT2}`;

// 스키마 먼저 (다른 검사처럼 dev-local.sh 를 먼저 켜지 않아도 돌게)
{
  const { default: pg } = await import('pg');
  const c = new pg.Client({ connectionString: process.env.DATABASE_URL });
  await c.connect(); await c.query(fs.readFileSync(path.join(root, 'db', 'schema.sql'), 'utf8')); await c.end();
}

let fails = 0;
const ok = (c, m) => { console.log((c ? 'ok  ' : 'FAIL') + ' ' + m); if (!c) fails++; };

// ---------- 구글 흉내: 키 한 쌍 · 키 파일 서버 ----------
const KEY_ID = '3335741209';
const kp = generateKeyPairSync('ec', { namedCurve: 'P-256' });
const other = generateKeyPairSync('ec', { namedCurve: 'P-256' });
const spki = kp.publicKey.export({ type: 'spki', format: 'der' }).toString('base64');
const pem = kp.publicKey.export({ type: 'spki', format: 'pem' });
const KS = { mode: 'ok', hits: 0 };
const keySrv = http.createServer((req, res) => {
  KS.hits++;
  if (KS.mode === 'hang') return;   // 답하지 않는다 (시간 제한 검사)
  if (KS.mode === '500') { res.statusCode = 500; return res.end('no'); }
  res.setHeader('content-type', 'application/json');
  res.setHeader('cache-control', 'public, max-age=86400');
  res.end(JSON.stringify(KS.mode === 'empty' ? { keys: [] } : { keys: [{ keyId: +KEY_ID, pem, base64: spki }] }));
}).listen(0, '127.0.0.1');
await new Promise((r) => keySrv.once('listening', r));
process.env.ADMOB_KEYS_URL = `http://127.0.0.1:${keySrv.address().port}/admob/reward/verifier-keys.json`;

// 구글처럼: 인자는 이름 순, 값은 퍼센트 인코딩해 보내고, 서명은 디코딩한 쿼리에 (signature·key_id 는 맨 뒤)
const enc = (v) => encodeURIComponent(v).replace(/[!'()*]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase());
function googleCallback(fields, { key = kp.privateKey, keyId = KEY_ID, signRaw = false, encode = enc } = {}) {
  const names = Object.keys(fields).sort();
  const decoded = names.map((k) => `${k}=${fields[k]}`).join('&');
  const raw = names.map((k) => `${k}=${encode(String(fields[k]))}`).join('&');
  const sig = sign('sha256', Buffer.from(signRaw ? raw : decoded, 'utf8'), { key, dsaEncoding: 'der' }).toString('base64url');
  return `${raw}&signature=${sig}&key_id=${keyId}`;
}
const baseFields = (over = {}) => ({ ad_network: '5450213213286189855', ad_unit: UNIT, reward_amount: '1', reward_item: 'song',
  timestamp: String(Date.now()), transaction_id: randomBytes(16).toString('hex'), user_id: 'not-trusted', ...over });

// Gemini 흉내 — 코드 몇 개를 찾을지(GEM.n) · 실패할지(GEM.fail). 키 파일 서버(로컬)는 진짜로 부른다
const GEM = { n: 20, fail: false };
const realFetch = globalThis.fetch;
globalThis.fetch = async (u, o) => {
  if (String(u).includes('generativelanguage')) {
    if (GEM.fail) return { ok: false, status: 503, json: async () => ({ error: { message: 'overloaded', status: 'UNAVAILABLE' } }) };
    const chords = Array.from({ length: GEM.n }, (_, i) => ({ text: ['C', 'G', 'Am', 'F'][i % 4], box: [100 + i * 20, 100, 115 + i * 20, 130] }));
    return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify({ title: '곡', key: 'C', chords }) }] } }], usageMetadata: {} }) };
  }
  if (/^http:\/\/127\.0\.0\.1:/.test(String(u))) return realFetch(u, o);
  throw new Error('밖으로 나가는 호출은 막았다: ' + u);
};

const admob = await import(path.join(root, 'lib', 'admob.js'));
const { verifySsv, _cfg, _resetKeys, _keyStats, rewardToken } = admob;
const { default: api } = await import(path.join(root, 'api', 'index.js'));
const { q, one } = await import(path.join(root, 'lib', 'db.js'));

const T = Date.now().toString(36).slice(-6);
const madeUsers = [], madeTeams = [], sentTxns = [];
try {
  /* ================= 1) 서명 확인 (구글과 같은 방식) ================= */
  _resetKeys();
  // 특수 글자가 든 custom_data (':' '/' 공백 '=' '+' '%' '?' 한글 · 따옴표) — 구글은 퍼센트 인코딩해 보낸다
  const tricky = "r1:팀 곡=1/2?%+ok*'()!";
  let cb = googleCallback(baseFields({ custom_data: tricky, user_id: 'real-user-1' }));
  ok(/custom_data=r1%3A%ED%8C%80%20%EA%B3%A1%3D1/.test(cb), '콜백의 custom_data 는 퍼센트 인코딩돼 있다');
  let v = await verifySsv(cb);
  ok(v.ok === true, '구글처럼 디코딩한 쿼리에 서명한 콜백 → 통과');
  ok(v.customData === tricky, "custom_data 를 인자 하나로 그대로 푼다 ('=' 는 첫 것만 나눈다) " + JSON.stringify(v.customData));
  ok(v.userId === 'real-user-1', 'user_id 도 읽는다');
  ok(v.adUnit === UNIT && v.timestamp > 0 && /^[0-9a-f]{32}$/.test(v.txn), '광고 단위·시각·transaction_id 를 읽는다');
  ok(_keyStats().fetches === 1, '키 파일을 한 번 받았다');
  // 값은 서명한 글자(디코딩한 쿼리)에서 읽는다 — custom_data 안의 '&이름=' 은 서명한 글자에서 따로 선 인자라 이름이 겹치면 거절
  v = await verifySsv(googleCallback(baseFields({ custom_data: 'r1:팀 & 곡=1&user_id=evil', user_id: 'real-user-1' })));
  ok(!v.ok && v.why === 'shape', "custom_data 안의 '&user_id=evil' (서명한 글자에서 user_id 가 두 번) → 거절 (" + v.why + ')');
  v = await verifySsv(googleCallback(baseFields({ custom_data: `x&ad_unit=${UNIT2}` })));
  ok(!v.ok && v.why === 'shape', "custom_data 로 ad_unit 을 하나 더 넣으면 → 거절 (" + v.why + ')');

  /* ---- 날것을 다시 나눠 인자를 끼워 넣는 위조 (남의 광고 단위로 받은 진짜 서명 콜백) ----
     구글의 키는 모든 애드몹 퍼블리셔가 같다. 자기 보상형 광고 단위와 SSV 주소를 가진 사람은 custom_data·user_id 를
     마음대로 정한 '진짜로 서명된' 콜백을 받는다. 서명은 디코딩한 글자에만 걸려 있으니, 보낼 때 어느 '&' 를 %26 으로
     감출지를 바꿔도 서명은 그대로다. 날것을 '&' 로 나눠 읽으면: 진짜 ad_unit(남의 것)은 다른 인자 값·쓸모없는 키 안에
     숨고, custom_data·user_id 에 적어 둔 ad_unit=우리 단위 · custom_data=우리 표 · transaction_id=아무거나 가 진짜 인자가 된다 */
  const FOREIGN = '7770009999';
  // 구글이 남의 광고 단위 콜백에 서명한 것 (디코딩한 글자 · 서명). 다시 나눠 보내는 것은 아래에서 손으로 만든다
  const signedFor = (fields) => {
    const names = Object.keys(fields).sort();
    const decoded = names.map((k) => `${k}=${fields[k]}`).join('&');
    return { decoded, sig: sign('sha256', Buffer.from(decoded, 'utf8'), { key: kp.privateKey, dsaEncoding: 'der' }).toString('base64url') };
  };
  const tokLike = rewardToken({ teamId: randomBytes(16).toString('hex'), userId: randomBytes(16).toString('hex'), kind: 'ocr' }).token;
  // (1) custom_data = 'junk&ad_unit=<우리>&custom_data=<표>' · 앞의 '&' 두 개를 %26 으로 감춰 진짜 ad_unit 을 ad_network 값 속에 숨긴다
  const forgeA = (tok) => {
    const s = signedFor(baseFields({ ad_unit: FOREIGN, custom_data: `junk&ad_unit=${UNIT}&custom_data=${tok}` }));
    const P = s.decoded.split('&');   // ad_network · ad_unit=남 · custom_data=junk · ad_unit=우리 · custom_data=표 · reward_amount …
    const raw = ['ad_network=' + enc(P.slice(0, 3).join('&').slice('ad_network='.length)), ...P.slice(3)].join('&');
    if (decodeURIComponent(raw) !== s.decoded) throw new Error('forgeA: 디코딩하면 서명한 글자와 같아야 한다');
    return { url: `${raw}&signature=${s.sig}&key_id=${KEY_ID}`, honest: `${s.decoded.split('&').map((kv) => { const i = kv.indexOf('='); return kv.slice(0, i + 1) + enc(kv.slice(i + 1)); }).join('&')}&signature=${s.sig}&key_id=${KEY_ID}` };
  };
  // (2) user_id = 'u&ad_unit=<우리>&custom_data=<표>&transaction_id=<아무거나>' · 진짜 transaction_id 는 쓸모없는 키
  //     'transaction_id=<진짜>&user_id' 안에 숨기고, 진짜 ad_unit 은 (1)처럼 ad_network 값 속에
  const forgeB = (tok, fakeTx) => {
    const s = signedFor(baseFields({ ad_unit: FOREIGN, custom_data: 'x', user_id: `u&ad_unit=${UNIT}&custom_data=${tok}&transaction_id=${fakeTx}` }));
    const P = s.decoded.split('&');
    const iA = P.findIndex((x) => x.startsWith('reward_amount=')), iT = P.findIndex((x) => x.startsWith('transaction_id='));
    const raw = ['ad_network=' + enc(P.slice(0, iA).join('&').slice('ad_network='.length)), ...P.slice(iA, iT),
      enc(P[iT] + '&user_id') + '=' + P[iT + 1].slice('user_id='.length), ...P.slice(iT + 2)].join('&');
    if (decodeURIComponent(raw) !== s.decoded) throw new Error('forgeB: 디코딩하면 서명한 글자와 같아야 한다');
    return { url: `${raw}&signature=${s.sig}&key_id=${KEY_ID}`, realTx: /transaction_id=([0-9a-f]+)&user_id=/.exec(s.decoded)[1] };
  };
  {
    const fa = forgeA(tokLike);
    v = await verifySsv(fa.url);
    ok(!v.ok, '위조 (1): 남의 ad_unit 을 숨기고 custom_data 로 ad_unit·custom_data 를 끼워 넣은 것 → 거절 ' + JSON.stringify({ ok: v.ok, why: v.why, adUnit: v.adUnit }));
    ok(v.why === 'shape', '위조 (1) 은 서명은 맞아도 인자 이름이 겹쳐 shape (' + v.why + ')');
    v = await verifySsv(fa.honest);
    ok(!v.ok && v.why === 'shape', '위조 (1) 의 정직한 모양(구글이 보낸 그대로)도 거절 (' + v.why + ')');
    const fb = forgeB(tokLike, 'ffff' + randomBytes(8).toString('hex'));
    v = await verifySsv(fb.url);
    ok(!v.ok && v.why === 'shape', '위조 (2): user_id 로 ad_unit·custom_data·transaction_id 를 끼우고 진짜 transaction_id 를 쓸모없는 키에 숨긴 것 → 거절 ' + JSON.stringify({ ok: v.ok, why: v.why, adUnit: v.adUnit, txn: v.txn }));
  }
  v = await verifySsv(googleCallback(baseFields({ custom_data: 'abc' })));
  ok(v.ok && _keyStats().fetches === 1, '두 번째는 캐시로 (다시 안 받는다)');
  // 날것(인코딩된 문자열)에 서명한 것은 구글이 하는 방식이 아니다 → 인코딩된 글자가 있으면 틀린 서명
  v = await verifySsv(googleCallback(baseFields({ custom_data: 'a:b c' }), { signRaw: true }));
  ok(!v.ok && v.why === 'bad_signature', '인코딩된 쿼리 그대로에 서명한 것은 거절 (' + v.why + ')');
  // 가는 길에 인코딩만 달라져도(':' 를 %3A 로 두느냐 마느냐) 디코딩하면 같으니 통과 — 구글 검증기와 같다
  v = await verifySsv(googleCallback(baseFields({ custom_data: 'a:b/c' }), { encode: (s) => s.replace(/ /g, '%20') }));
  ok(v.ok, '인코딩 모양이 달라도 디코딩한 내용이 같으면 통과');
  // 바꾼 것들
  const good = googleCallback(baseFields({ custom_data: 'abc', transaction_id: 'aa11bb22' }));
  v = await verifySsv(good.replace('transaction_id=aa11bb22', 'transaction_id=aa11bb23'));
  ok(!v.ok && v.why === 'bad_signature', 'transaction_id 를 바꾸면 거절');
  v = await verifySsv(good.replace('custom_data=abc', 'custom_data=abd'));
  ok(!v.ok, 'custom_data 를 바꾸면 거절');
  v = await verifySsv(good.replace(`ad_unit=${UNIT}`, `ad_unit=${UNIT2}`));
  ok(!v.ok, '광고 단위를 바꾸면 거절');
  {
    const m = /signature=([^&]+)/.exec(good); const s = Buffer.from(m[1], 'base64url'); s[10] ^= 0x55;
    v = await verifySsv(good.replace(m[1], s.toString('base64url'))); ok(!v.ok && v.why === 'bad_signature', '서명을 한 바이트 바꾸면 거절');
  }
  v = await verifySsv(googleCallback(baseFields({ custom_data: 'abc' }), { key: other.privateKey }));
  ok(!v.ok && v.why === 'bad_signature', '다른 키로 서명한 것은 거절');
  // 모양: signature·key_id 가 맨 뒤 두 인자여야 한다
  v = await verifySsv(good + '&x=1'); ok(!v.ok && v.why === 'shape', 'key_id 뒤에 인자가 더 있으면 거절');
  v = await verifySsv(good.replace(/&key_id=\d+$/, '')); ok(!v.ok, 'key_id 가 없으면 거절');
  v = await verifySsv(good.replace(/&key_id=\d+$/, '&key_id=12x')); ok(!v.ok && v.why === 'shape', 'key_id 가 숫자가 아니면 거절');
  v = await verifySsv('ad_network=1&custom_data=%E0%A4%A&signature=AAAA&key_id=' + KEY_ID); ok(!v.ok, '깨진 퍼센트 인코딩은 거절');
  // 우리 rewrite(vercel.json /api?p=<경로>)가 앞이나 뒤에 붙인 p= 는 떼고 본다
  v = await verifySsv('p=ads%2Fssv&' + good); ok(v.ok, '앞에 붙은 p= 는 떼고 확인');
  v = await verifySsv(good + '&p=ads/ssv'); ok(v.ok, '뒤에 붙은 p= 는 떼고 확인');

  // 키 캐시: 모르는 key_id 로 쏟아도 밖으로 한 번도 안 나간다 (1분에 한 번)
  const f0 = _keyStats().fetches;
  for (let i = 0; i < 5; i++) { v = await verifySsv(googleCallback(baseFields(), { keyId: String(900000 + i) })); }
  ok(!v.ok && v.why === 'unknown_key' && _keyStats().fetches === f0, '모르는 key_id 5번 → 거절 · 키 파일은 다시 안 받음');
  _cfg.unknownGap = 0;   // 간격이 지나면 한 번 새로 받는다 (구글이 키를 돌렸을 때)
  v = await verifySsv(googleCallback(baseFields(), { keyId: '12345' }));
  ok(!v.ok && _keyStats().fetches === f0 + 1, '간격이 지나면 모르는 key_id 로 한 번 새로 받는다');
  _cfg.unknownGap = 60e3;
  // 동시에 와도 한 번만 받는다
  _resetKeys();
  const many = await Promise.all(Array.from({ length: 10 }, () => verifySsv(googleCallback(baseFields()))));
  ok(many.every((x) => x.ok) && _keyStats().fetches === 1, '처음에 10개가 동시에 와도 키 파일은 한 번 (' + _keyStats().fetches + ')');
  // 시간 제한: 키 서버가 답을 안 하면 기다리지 않고 던진다 → 라우트 503 → 구글이 다시 보낸다
  _resetKeys(); KS.mode = 'hang'; _cfg.fetchMs = 300;
  let t0 = Date.now(), threw = false;
  try { await verifySsv(googleCallback(baseFields())); } catch { threw = true; }
  ok(threw && Date.now() - t0 < 3000, '키 서버가 멈추면 시간 제한으로 끝낸다 (' + (Date.now() - t0) + 'ms)');
  // 받기가 실패해도 전에 받은 키로 확인한다 · 실패 뒤 곧바로 또 나가지 않는다 · 빈 목록이 캐시를 지우지 않는다
  _resetKeys(); KS.mode = 'ok'; _cfg.fetchMs = 5000; _cfg.ttlMax = 1;   // 받자마자 오래된 것으로
  v = await verifySsv(googleCallback(baseFields())); ok(v.ok, '키 받음');
  await new Promise((r) => setTimeout(r, 5));
  KS.mode = '500'; const h0 = KS.hits;
  v = await verifySsv(googleCallback(baseFields())); ok(v.ok && KS.hits === h0 + 1, '새로 받기가 실패해도 남은 키로 통과');
  v = await verifySsv(googleCallback(baseFields())); ok(v.ok && KS.hits === h0 + 1, '실패한 뒤 10초 안에는 다시 안 나간다');
  _cfg.failGap = 0; KS.mode = 'empty';
  v = await verifySsv(googleCallback(baseFields())); ok(v.ok, '빈 키 목록이 와도 캐시를 지우지 않는다');
  _cfg.failGap = 10e3; _cfg.ttlMax = 24 * 3600e3; KS.mode = 'ok'; _resetKeys();

  /* ================= 2) API 전체 ================= */
  const call = (method, p, body, headers = {}) => new Promise((resolve) => {
    const h = {};
    const res = { statusCode: 200, setHeader(k, val) { h[k.toLowerCase()] = val; }, getHeader(k) { return h[k.toLowerCase()]; },
      end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ st: this.statusCode, j: j || {}, headers: h }); } };
    api({ method, url: p.startsWith('/api') ? p : '/api' + p, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
  });
  const user = async (n) => {
    const r = await call('POST', '/auth/signup', { username: 'rw' + n + T, password: 'secret12', name: n });
    if (r.st !== 200) throw new Error('가입 ' + JSON.stringify(r.j));
    madeUsers.push(r.j.user.id);
    return { id: r.j.user.id, h: { cookie: String(r.headers['set-cookie']).split(';')[0] } };
  };
  const L = await user('lead'), M = await user('mem'), O = await user('out');
  const tm = await call('POST', '/teams', { name: '보상팀' + T, myName: '인도자' }, L.h);
  const teamId = tm.j.teamId; madeTeams.push(teamId);
  ok(!!teamId, '팀 만들기');
  const jn = await call('POST', `/invite/${tm.j.invite}/join`, { name: '멤버', sessions: ['드럼'] }, M.h);
  ok(jn.st === 200, '멤버 가입');
  const month = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 7);
  for (let i = 0; i < 10; i++) await q('insert into ai_songs(team_id, month, kind, song_key) values($1,$2,$3,$4) on conflict do nothing', [teamId, month, 'ocr', 'used' + i]);
  const img = { b64: fs.readFileSync(path.join(root, 'docs', 'sample_sheet.jpg')).toString('base64'), mime: 'image/jpeg', w: 2120, h: 3163 };
  const ocr = (songKey, who = L) => call('POST', '/ocr', { teamId, songKey, images: [img] }, who.h);
  const status = async () => (await call('GET', '/ads/reward?teamId=' + teamId, null, L.h)).j;
  const start = async (who = L) => call('POST', '/ads/reward/start', { teamId, kind: 'ocr' }, who.h);
  const ssv = async (qs, prefix = '/ads/ssv?') => { const t = /(?:^|&)transaction_id=([^&]+)/.exec(qs); if (t) sentTxns.push(t[1]); return call('GET', prefix + qs); };
  const token = async () => { const r = await start(); if (!r.j.token) throw new Error('표 ' + JSON.stringify(r.j)); return r.j.token; };
  const cbFor = (tok, over = {}) => googleCallback(baseFields({ custom_data: tok, ...over }));

  let r = await ocr('songA'); ok(r.st === 402 && r.j.error === 'ai_limit', '한도를 다 쓰면 402 ai_limit');
  let st = await status();
  ok(st.on === true && st.ready === 0 && st.left === 3 && st.today === 0 && st.perDay === 3 && st.perMonth === 20, '처음: 받은 것 0 · 오늘 3번 ' + JSON.stringify(st));
  r = await call('GET', '/ads/reward?teamId=' + teamId, null, M.h); ok(r.st === 403, '인도자가 아니면 상태를 못 본다');
  r = await call('GET', '/ads/reward?teamId=' + teamId, null, O.h); ok(r.st === 403, '다른 팀 사람은 403');
  r = await call('GET', '/ads/reward?teamId=garbage', null, L.h); ok(r.st === 400, 'uuid 가 아닌 팀은 400 (500 아님)');
  r = await call('GET', '/ads/reward', null, L.h); ok(r.st === 400, '팀이 없으면 400');
  r = await start(M); ok(r.st === 403, '멤버는 보상 표를 못 받는다');
  r = await call('GET', '/usage'.replace('/usage', `/teams/${teamId}/usage`), null, L.h);
  ok(r.j.reward && r.j.reward.on === true && r.j.reward.left === 3, '/usage 가 인도자에게 보상 상태를 준다');
  r = await call('GET', `/teams/${teamId}/usage`, null, M.h); ok(r.st === 200 && !r.j.reward, '멤버의 /usage 에는 보상 상태가 없다');

  // 콘솔 'URL 확인'(서명 없음)
  r = await call('GET', '/ads/ssv'); ok(r.st === 200, '서명 없는 확인 요청은 200');
  r = await call('GET', '/ads/ssv?ad_network=1&ad_unit=2'); ok(r.st === 200, '서명 없는 콘솔 확인(인자만) 200');

  // 진짜 보상 · 같은 콜백 두 번 · 같은 표로 다른 광고
  const tok1 = await token();
  ok(/^r1\.ocr\.[0-9a-f]{32}\.[0-9a-f]{32}\.[A-Za-z0-9_-]{16}\.[0-9a-z]+\.[A-Za-z0-9_-]{22}$/.test(tok1), '보상 표 모양 (퍼센트 인코딩이 필요 없는 글자만)');
  const cb1 = cbFor(tok1, { user_id: O.id });   // user_id 는 믿지 않는다 (표의 사람으로)
  r = await ssv(cb1); ok(r.st === 200 && r.j.ok === true, '맞는 콜백 → 보상 적힘');
  r = await ssv(cb1); ok(r.st === 200 && r.j.ok === true && r.j.dup, '같은 콜백이 다시 와도(구글 재전송) 200 · 한 번만');
  r = await ssv(cbFor(tok1)); ok(r.st === 200 && r.j.ok === false, '같은 표로 다른 광고(다른 transaction_id) → 거절');
  st = await status(); ok(st.ready === 1 && st.today === 1 && st.left === 2, '받은 것 1 · 오늘 1 ' + JSON.stringify(st));
  const g1 = await one('select user_id, ad_unit, day::text as day, expires_at from ad_reward_grants where team_id=$1', [teamId]);
  ok(g1 && g1.user_id === L.id && g1.ad_unit === UNIT, '보상은 표의 사람(인도자)으로 적힌다 · 광고 단위');
  ok(g1 && new Date(g1.expires_at) > new Date(), '쓸 수 있는 기한이 있다');

  // Vercel rewrite 모양의 주소(/api?p=ads/ssv&…)로 와도 된다
  r = await ssv(cbFor(await token()), '/api?p=ads%2Fssv&'); ok(r.j.ok === true, '/api?p=ads/ssv&… 로 와도 확인된다');
  st = await status(); ok(st.ready === 2 && st.today === 2, '받은 것 2');

  // 거절: 남의 광고 단위 · 오래된·앞선 시각 · 위조·만료 표 · 인도자가 아닌 사람의 표 · 날것 서명
  const before = await status();
  const bad1 = cbFor(await token(), { ad_unit: '9999999999' });
  r = await ssv(bad1); ok(r.st === 200 && r.j.ok === false, '목록에 없는 광고 단위 → 거절 (200)');
  r = await ssv(cbFor(await token(), { timestamp: String(Date.now() - 2 * 3600e3) })); ok(r.j.ok === false, '2시간 전 콜백 → 거절');
  r = await ssv(cbFor(await token(), { timestamp: String(Date.now() + 10 * 60e3) })); ok(r.j.ok === false, '10분 앞선 콜백 → 거절');
  // mac 의 첫 글자를 바꾼다 (마지막 글자는 아래 4비트가 버려지는 자리라 바꿔도 같은 mac 일 수 있다 — 그건 아래에서 따로)
  const macAt = tok1.lastIndexOf('.') + 1;
  const forged = tok1.slice(0, macAt) + (tok1[macAt] === 'A' ? 'B' : 'A') + tok1.slice(macAt + 1);
  ok(!admob.readRewardToken(forged), '위조한 표(mac 틀림)는 풀리지 않는다');
  r = await ssv(cbFor(forged)); ok(r.j.ok === false, '위조한 표(mac 틀림) → 거절');
  {
    // 끝 글자를 base64url 값의 맨 아래 비트(버려지는 4비트 중 하나)만 다른 글자로 — 풀면 같은 mac 16바이트
    const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    const lastB = tok1.slice(0, -1) + B64[B64.indexOf(tok1[tok1.length - 1]) ^ 1];
    ok(Buffer.from(lastB.slice(macAt), 'base64url').equals(Buffer.from(tok1.slice(macAt), 'base64url')), '(준비) 끝 글자만 바꾼 mac 이 같은 바이트로 풀린다');
    ok(admob.readRewardToken(tok1) && !admob.readRewardToken(lastB), '끝 글자의 버려지는 비트만 바꾼 표는 받지 않는다 (쓴 글자 그대로만)');
  }
  r = await ssv(cbFor(`${teamId}:ocr`)); ok(r.j.ok === false, "앱이 적은 '팀id:종류' 같은 값 → 거절");
  const oldTok = rewardToken({ teamId, userId: L.id, kind: 'ocr', now: Date.now() - 31 * 60e3 }).token;
  r = await ssv(cbFor(oldTok)); ok(r.j.ok === false, '만료된 표(30분) → 거절');
  const memTok = rewardToken({ teamId, userId: M.id, kind: 'ocr' }).token;
  r = await ssv(cbFor(memTok)); ok(r.j.ok === false, '인도자가 아닌 사람의 표 → 거절');
  // 위조 (1)·(2) 에 우리 서버가 준 진짜 표를 넣어도 — 서명은 구글이 한 진짜지만 광고 단위는 남의 것 → 적히지 않는다
  const nGrants = async () => (await one('select count(*)::int n from ad_reward_grants where team_id=$1', [teamId])).n;
  const g0 = await nGrants();
  const fA = forgeA(await token());
  r = await ssv(fA.url); ok(r.st === 200 && r.j.ok === false, '위조 (1) 을 /ads/ssv 로 → 거절 ' + JSON.stringify(r.j));
  r = await ssv(fA.honest); ok(r.st === 200 && r.j.ok === false, '위조 (1) 의 정직한 모양 → 거절 ' + JSON.stringify(r.j));
  const fB = forgeB(await token(), 'ffff' + randomBytes(8).toString('hex'));
  r = await ssv(fB.url); ok(r.st === 200 && r.j.ok === false, '위조 (2) 을 /ads/ssv 로 → 거절 ' + JSON.stringify(r.j));
  ok(await nGrants() === g0, '위조 콜백으로는 보상이 하나도 안 적혔다 (' + g0 + ' → ' + (await nGrants()) + ')');
  ok(!(await one('select 1 from ad_ssv_seen where txn=$1', [fB.realTx])), '위조 (2) 가 숨긴 진짜 transaction_id 도 적히지 않았다 (모양에서 끝남)');
  st = await status(); ok(st.ready === before.ready && st.today === before.today, '거절한 것들은 하나도 안 적혔다 ' + JSON.stringify(st));
  // 거절한 콜백은 transaction_id 를 적어 두어, 나중에 다시 보내도 못 쓴다 (아직 오늘 자리가 남아 있는데도)
  const seenBad = await one('select result from ad_ssv_seen where txn=$1', [new URLSearchParams(bad1).get('transaction_id')]);
  ok(seenBad && seenBad.result === 'unit', '거절한 콜백도 적어 둔다 (' + (seenBad && seenBad.result) + ')');
  process.env.ADMOB_REWARD_UNITS += ',9999999999';
  r = await ssv(bad1); ok(r.j.ok === false && r.j.dup, '한 번 거절된 콜백은 나중에 다시 보내도(단위를 더한 뒤에도) 거절 ' + JSON.stringify(r.j));
  process.env.ADMOB_REWARD_UNITS = `ca-app-pub-5011605715320185/${UNIT}, ${UNIT2}`;
  st = await status(); ok(st.left === 1, '자리는 그대로 1 남음');
  r = await ssv(googleCallback(baseFields({ custom_data: await token() }), { signRaw: true }));
  ok(r.j.ok === true, '표는 인코딩할 글자가 없어 날것 서명과 디코딩 서명이 같다 (그래서 받음)');
  st = await status(); ok(st.ready === before.ready + 1 && st.today === before.today + 1, '셋째 보상 ' + JSON.stringify(st));

  // 오늘 3/3 → 넷째는 표부터 안 준다 · 콜백이 와도 막힌다
  st = await status(); ok(st.today === 3 && st.left === 0 && st.why === 'day', '오늘 3/3 · 까닭 day ' + JSON.stringify(st));
  r = await start(); ok(r.st === 200 && r.j.ok === false && r.j.capped && !r.j.token, '한도면 표를 안 준다 (광고를 헛보지 않게)');
  const tokX = rewardToken({ teamId, userId: L.id, kind: 'ocr' }).token;
  r = await ssv(cbFor(tokX)); ok(r.j.ok === false && r.j.capped, '넷째 콜백은 막힘');

  /* ---- 코드 인식이 보상을 쓴다 ---- */
  r = await ocr('songA'); ok(r.st === 200 && r.j.quota && r.j.quota.reward === true, '보상으로 인식 ' + r.st + ' ' + JSON.stringify(r.j.quota || r.j));
  ok(r.j.quota && r.j.quota.used === 10 && r.j.quota.cap === 10, '응답의 사용량은 그대로 10/10');
  st = await status(); ok(st.ready === 2, '보상 하나를 썼다 (3 → 2)');
  r = await call('GET', `/teams/${teamId}/usage`, null, L.h); ok(r.j.ocr.used === 10, '/usage 의 한도 사용량도 10 (보상 곡은 안 셈)');
  r = await ocr('songA'); ok(r.st === 200 && !r.j.quota.reward, '같은 곡 다시 인식은 또 안 뺀다');
  st = await status(); ok(st.ready === 2, '그대로 2');
  // 남은 보상 두 개를 치워 두고 (다음 검사를 위해)
  await q(`update ad_reward_grants set used_at=now(), used_key='x' where team_id=$1 and used_at is null`, [teamId]);
  r = await ocr('songB'); ok(r.st === 402, '보상이 없으면 다른 곡은 402');

  // 같은 곡을 동시에 4번 — 보상이 없으면 하나도 통과하지 못한다 (예전엔 곡을 먼저 적었다 지우는 틈에 공짜로 통과)
  let rs = await Promise.all([1, 2, 3, 4].map(() => ocr('songC')));
  ok(rs.every((x) => x.st === 402), '보상 없이 같은 곡 동시 4번 → 모두 402 (' + rs.map((x) => x.st).join(',') + ')');
  ok(!(await one("select 1 from ai_songs where team_id=$1 and song_key='songC'", [teamId])), '곡 기록도 안 남는다');

  // 보상 1개 · 같은 곡 동시 4번 — 보상은 한 번만 쓰인다
  await q(`insert into ad_reward_grants(txn, team_id, user_id, kind, day, expires_at) values($1,$2,$3,'ocr',current_date, now() + interval '1 hour')`, ['t-' + T + '-d', teamId, L.id]);
  rs = await Promise.all([1, 2, 3, 4].map(() => ocr('songD')));
  const used = await one(`select count(*)::int n from ad_reward_grants where team_id=$1 and used_key='songD'`, [teamId]);
  const rows = await one(`select count(*)::int n from ai_songs where team_id=$1 and song_key='songD' and source='reward'`, [teamId]);
  ok(used.n === 1 && rows.n === 1 && rs.some((x) => x.st === 200) && rs.every((x) => x.st === 200 || x.st === 402),
    '보상 1개로 같은 곡 동시 4번 → 보상은 한 번만 (' + rs.map((x) => x.st).join(',') + ')');

  /* ---- 하루·한 달 한도를 동시에 보내도 넘지 않는다 ---- */
  // 하루를 어제로 돌려 오늘은 0부터 (한 달 5개)
  await q(`update ad_reward_counts set day = day - 1, n_month = 5 where team_id=$1`, [teamId]);
  const toks = [];
  for (let i = 0; i < 8; i++) toks.push(rewardToken({ teamId, userId: L.id, kind: 'ocr' }).token);
  rs = await Promise.all(toks.map((t) => ssv(cbFor(t))));
  st = await status();
  ok(rs.filter((x) => x.j.ok).length === 3 && st.today === 3 && st.month === 8, '콜백 8개 동시 → 딱 3개만 (오늘 ' + st.today + ' · 달 ' + st.month + ')');
  // 한 달 19개 → 동시 4개 중 1개만, 까닭은 month
  await q(`update ad_reward_counts set day = day - 1, n_month = 19 where team_id=$1`, [teamId]);
  rs = await Promise.all([1, 2, 3, 4].map(() => ssv(cbFor(rewardToken({ teamId, userId: L.id, kind: 'ocr' }).token))));
  st = await status();
  ok(rs.filter((x) => x.j.ok).length === 1 && st.month === 20 && st.left === 0 && st.why === 'month', '한 달 19 → 동시 4개 중 1개만 · 까닭 month ' + JSON.stringify(st));
  r = await start(); ok(r.j.capped && r.j.why === 'month', '한 달 한도면 표를 안 주고 까닭을 month 로');
  await q(`update ad_reward_grants set used_at=now(), used_key='x' where team_id=$1 and used_at is null`, [teamId]);

  /* ---- 자정 무렵: 날짜가 넘어가도 기한 안이면 쓴다 · 기한이 지나면 못 쓴다 ---- */
  await q(`insert into ad_reward_grants(txn, team_id, user_id, kind, day, expires_at) values($1,$2,$3,'ocr',current_date - 1, now() - interval '1 minute')`, ['t-' + T + '-old', teamId, L.id]);
  r = await ocr('songE'); ok(r.st === 402, '기한이 지난 보상은 못 쓴다');
  await q(`insert into ad_reward_grants(txn, team_id, user_id, kind, day, expires_at) values($1,$2,$3,'ocr',current_date - 1, now() + interval '10 minutes')`, ['t-' + T + '-mid', teamId, L.id]);
  st = await status(); ok(st.ready === 1 && st.readyUntil, '어제 받았어도 기한(자정+30분) 안이면 준비된 것으로 센다');
  r = await ocr('songE'); ok(r.st === 200 && r.j.quota.reward, '어제 23:59 에 받은 보상을 00:05 에 쓴다');
  {
    // 기한 계산: 23:59:50 에 받으면 자정이 아니라 30분 뒤까지
    const kst = (y, m, d, hh, mm, ss) => Date.UTC(y, m - 1, d, hh - 9, mm, ss);
    const mid = (ms) => { const d = new Date(ms + 9 * 3600e3); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1) - 9 * 3600e3; };
    const at = kst(2026, 9, 25, 23, 59, 50);
    ok(Math.max(mid(at), at + 30 * 60e3) === at + 30 * 60e3 && mid(kst(2026, 9, 25, 10, 0, 0)) === kst(2026, 9, 26, 0, 0, 0), '기한: 낮에 받으면 그날 자정 · 자정 직전이면 30분 뒤');
  }

  /* ---- 보상 곡 환불: 사용량 그대로 · 월 환불 횟수 안 씀 · 보상 하나에 한 번 ---- */
  await q(`insert into ad_reward_grants(txn, team_id, user_id, kind, day, expires_at) values($1,$2,$3,'ocr',current_date, now() + interval '1 hour')`, ['t-' + T + '-rf', teamId, L.id]);
  GEM.n = 2;   // 코드를 거의 못 찾음 → 환불
  r = await ocr('songF');
  ok(r.st === 200 && r.j.quota.refunded === true && r.j.quota.used === 10, '보상 곡 환불 → 응답 사용량은 10 그대로 (9 아님) ' + JSON.stringify(r.j.quota));
  st = await status(); ok(st.ready === 1, '보상을 돌려받아 다시 쓸 수 있다');
  const cr = await one('select count(*)::int n from credit_refunds where team_id=$1', [teamId]);
  ok(cr.n === 0, '요금제 월 환불 횟수는 쓰지 않았다');
  ok(!(await one("select 1 from ai_songs where team_id=$1 and song_key='songF'", [teamId])), '환불한 곡 기록은 지워졌다');
  r = await ocr('songG');
  ok(r.st === 200 && r.j.quota.refunded === false, '같은 보상으로 또 적게 나오면 두 번째는 안 돌려준다 (광고 한 번으로 끝없이 못 쓰게)');
  st = await status(); ok(st.ready === 0, '보상은 songG 에 쓴 것으로 남는다');
  GEM.n = 20;

  /* ---- 엔진이 실패하면 보상을 그대로 돌려준다 ---- */
  await q(`insert into ad_reward_grants(txn, team_id, user_id, kind, day, expires_at) values($1,$2,$3,'ocr',current_date, now() + interval '1 hour')`, ['t-' + T + '-fail', teamId, L.id]);
  GEM.fail = true;
  r = await ocr('songH'); ok(r.st === 502, '엔진 실패 502');
  GEM.fail = false;
  st = await status(); ok(st.ready === 1, '엔진이 실패하면 보상을 돌려준다');
  ok(!(await one("select 1 from ai_songs where team_id=$1 and song_key='songH'", [teamId])), '실패한 곡 기록은 안 남는다');

  /* ---- 꺼져 있으면 아무것도 안 한다 ---- */
  process.env.ADMOB_REWARD_UNITS = '';
  const f1 = _keyStats().fetches;
  r = await start(); ok(r.st === 409 && r.j.error === 'reward_off', '광고 단위가 설정되지 않으면 표를 안 준다 (409)');
  r = await ssv(cbFor(tokX)); ok(r.st === 200 && r.j.ok === false && _keyStats().fetches === f1, '꺼져 있으면 콜백은 서명도 안 보고(키를 받으러 안 나감) 거절');
  r = await call('GET', `/teams/${teamId}/usage`, null, L.h); ok(!r.j.reward, '꺼져 있으면 /usage 에 보상 상태가 없다');
} catch (e) { console.error(e); fails++; }
finally {
  // 뒷정리 — 팀을 지우면 보상·자리·곡 기록은 따라 지워진다 (on delete cascade). SSV 기록은 팀 id 로 지운다
  try {
    for (const t of madeTeams) { await q('delete from ad_ssv_seen where team_id=$1', [t]); await q('delete from teams where id=$1', [t]); }
    if (sentTxns.length) await q('delete from ad_ssv_seen where txn = any($1::text[])', [sentTxns]);   // 팀을 모르는 거절(위조 표 등)
    if (madeUsers.length) await q('delete from users where id = any($1::uuid[])', [madeUsers]);
  } catch (e) { console.error('뒷정리', e.message); fails++; }
  keySrv.close();
}
console.log(fails ? `\n${fails}개 실패` : '\n모두 통과');
process.exit(fails ? 1 : 0);
