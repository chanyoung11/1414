// iOS 푸시 (Apple Push Notification service).
// @capacitor/push-notifications 의 iOS 는 Firebase 를 거치지 않고 APNs 에 직접 등록해
// APNs 토큰을 준다. 그래서 FCM(안드로이드)과 따로 보낸다.
//
// APNs 는 HTTP/2 만 받는다. node 의 fetch(undici)는 HTTP/1.1 이라 연결이 깨지므로
// node:http2 를 직접 쓴다.
//
// 필요한 환경변수: APNS_KEY_ID, APNS_TEAM_ID, APNS_PRIVATE_KEY(.p8 내용), APNS_BUNDLE_ID
// APNS_ENV=production 이면 운영 서버, 아니면 개발(샌드박스) 서버로 보낸다.
import crypto from 'node:crypto';
import http2 from 'node:http2';
import { q } from './db.js';

const KEY_ID = process.env.APNS_KEY_ID || '';
const TEAM_ID = process.env.APNS_TEAM_ID || '';
const KEY = (process.env.APNS_PRIVATE_KEY || '').replace(/\\n/g, '\n');
const BUNDLE = process.env.APNS_BUNDLE_ID || 'com.lets1414.app';
const PROD = 'https://api.push.apple.com';
const SANDBOX = 'https://api.sandbox.push.apple.com';
// 같은 토큰이라도 환경이 다르면 거부된다. Xcode 로 깐 개발 빌드는 sandbox,
// 테스트플라이트·앱스토어 빌드는 production 을 쓴다. 토큰만 봐서는 구분할 수 없으므로
// 기본 환경에서 거부되면 반대쪽으로 한 번 더 보낸다.
const HOST = process.env.APNS_ENV === 'sandbox' ? SANDBOX : PROD;
const OTHER = HOST === PROD ? SANDBOX : PROD;
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

// 한 세션으로 여러 기기에 보낸다. 다 보내면 닫는다
function openSession(host) {
  return new Promise((res, rej) => {
    const s = http2.connect(host, { settings: { enablePush: false } });
    let settled = false;
    // 세션 오류는 연결된 뒤에도 온다 (애플이 연결을 끊거나 GOAWAY 로 닫을 때).
    // 'error' 를 듣는 쪽이 하나도 없으면 node 가 잡히지 않은 예외로 던져 인스턴스가 통째로 죽는다
    // (처리 중이던 다른 요청까지 같이). 보내던 요청은 post() 가 각자 실패로 끝내므로 여기서는 적어 두기만 한다
    s.on('error', (e) => { if (settled) console.warn('apns session', host, e && e.message); });
    const done = (fn, v) => {
      if (settled) return;
      settled = true; clearTimeout(timer); s.off('connect', ok); s.off('error', bad); fn(v);
    };
    const ok = () => done(res, s);
    const bad = (e) => { try { s.destroy(); } catch {} done(rej, e); };
    s.once('connect', ok); s.once('error', bad);
    // 연결될 때까지만 잰다. 연결 뒤에도 돌면 한창 보내는 세션을 8초에 끊어 버린다
    const timer = setTimeout(() => bad(new Error('APNs 연결 시간 초과')), 8000);
    timer.unref?.();
  });
}

function post(session, token, jwt, note) {
  return new Promise((res) => {
    const body = Buffer.from(JSON.stringify(note));
    const req = session.request({
      ':method': 'POST', ':path': `/3/device/${token}`,
      authorization: 'bearer ' + jwt, 'apns-topic': BUNDLE,
      'apns-push-type': 'alert', 'apns-priority': '10',
      'content-type': 'application/json', 'content-length': body.length,
    });
    let status = 0, text = '';
    req.setTimeout(8000, () => { req.close(); res({ status: 0, text: '시간 초과' }); });
    req.on('response', (h) => { status = h[':status'] || 0; });
    req.on('data', (c) => { text += c; });
    req.on('end', () => res({ status, text }));
    req.on('error', (e) => res({ status: 0, text: e.message }));
    // 세션이 통째로 닫히면 end 없이 close 만 오기도 한다. 그래도 끝은 나야 발행이 멈추지 않는다
    req.on('close', () => res({ status, text: text || '연결이 닫혔어요' }));
    req.end(body);
  });
}

export async function sendApns(userIds, payload) {
  if (!apnsConfigured()) return 0;
  const ids = [...new Set(userIds)].filter(Boolean);
  if (!ids.length) return 0;
  const rows = await q(`select token from push_tokens where platform='ios' and user_id = any($1::uuid[])`, [ids]);
  if (!rows.length) return 0;

  let jwt;
  try { jwt = authToken(); } catch (e) { console.warn('apns jwt', e.message); return 0; }

  const note = {
    aps: {
      alert: { title: payload.title || '1414', body: payload.body || '' },
      sound: 'default', 'thread-id': payload.tag || 'conti',
    },
    // teamId: 여러 팀에 있는 사람이 누르면 앱이 그 팀으로 바꾼 뒤 링크를 연다 (링크는 팀 안 주소)
    link: String(payload.link || '#/home'), type: String(payload.type || ''), teamId: String(payload.teamId || ''),
  };
  const dead = [];
  let sent = 0;

  // 한 환경으로 보낸다. 그 환경이 '모르는 토큰'(BadDeviceToken)이라 답한 것과
  // '서명 키가 이 환경용이 아니다'(BadEnvironmentKeyInToken)라 답한 것을 돌려준다.
  // 연결조차 안 되면 null — 답을 못 들은 것이지 토큰이 죽은 게 아니다
  async function round(host, tokens) {
    let session;
    try { session = await openSession(host); }
    catch (e) { console.warn('apns connect', host, e.message); return null; }
    const unknown = [], wrongKey = [];
    try {
      const out = await Promise.all(tokens.map((t) => post(session, t, jwt, note)));
      out.forEach((o, i) => {
        if (o.status === 200) { sent++; return; }
        // 환경이 달라 거부된 것뿐일 수 있으니 여기서 지우지 않는다
        if (/BadDeviceToken/.test(o.text)) { unknown.push(tokens[i]); return; }
        if (/BadEnvironmentKeyInToken/.test(o.text)) { wrongKey.push(tokens[i]); return; }
        if (o.status === 410 || /Unregistered/.test(o.text)) { dead.push(tokens[i]); return; }
        console.warn('apns', o.status, String(o.text).slice(0, 120));
      });
    } finally { try { session.close(); } catch {} }
    return { unknown, wrongKey };
  }

  const all = rows.map((r) => r.token);
  const first = await round(HOST, all);
  // 기본 환경이 거부한 토큰만 반대 환경으로 한 번 더 보낸다. 기본 환경에 아예 연결이 안 됐으면 전부 보낸다 —
  // 반대 환경 토큰(Xcode 개발 빌드는 샌드박스)은 거기서 받는다. 멈추면 기본 환경이 앓는 동안 그쪽 폰도 못 받았다.
  // 두 환경이 모두 '모르는 토큰'이라고 실제로 답해야 죽은 토큰이다. 한쪽에 연결이 안 됐거나
  // 키가 그 환경용이 아니라 판단을 못 한 것은 지우지 않는다
  // (애플 운영 서버가 잠깐 안 닿는 사이 샌드박스의 BadDeviceToken 만 보고 아이폰 토큰을 전부 지우던 것)
  const retry = first ? [...first.unknown, ...first.wrongKey] : all;
  if (retry.length) {
    const second = await round(OTHER, retry);
    const was = new Set(first ? first.unknown : []);
    if (second) dead.push(...second.unknown.filter((t) => was.has(t)));
  }

  if (dead.length) await q('delete from push_tokens where token = any($1::text[])', [dead]);
  return sent;
}
