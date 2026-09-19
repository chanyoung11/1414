// Cloudflare Workers 진입점.
//
// api/index.js 는 Node 방식(req, res)으로 쓰여 있다. 그 2,700줄을 다시 쓰는 대신
// 여기서 Workers 의 Request 를 Node 스타일 req 로, 응답을 모으는 가짜 res 로 감싸 넘긴다.
// 덕분에 라우트 114개와 그 아래 코드는 손대지 않는다.
//
// 정적 파일(app/)은 Workers Assets(env.ASSETS)이 맡는다.
import handler from '../api/index.js';

// api 코드가 process.env 를 읽는다. Workers 는 요청마다 env 를 주므로 첫 요청에 옮겨 담는다.
function fillEnv(env) {
  if (typeof process === 'undefined' || !process.env) return;
  for (const k in env) {
    const v = env[k];
    if (typeof v === 'string' && process.env[k] === undefined) process.env[k] = v;
  }
}

// Node 의 http.ServerResponse 흉내. 우리 api 는 statusCode·setHeader·end 만 쓴다.
function fakeRes() {
  const chunks = [];
  const res = {
    statusCode: 200,
    _headers: {},
    _done: null,
    setHeader(k, v) { this._headers[k] = v; },
    getHeader(k) { return this._headers[k]; },
    removeHeader(k) { delete this._headers[k]; },
    write(c) { if (c != null) chunks.push(c); return true; },
    end(c) { if (c != null) chunks.push(c); this._done(this); },
  };
  res.promise = new Promise((r) => { res._done = r; });
  res._body = () => (chunks.length ? chunks.join('') : null);
  return res;
}

async function nodeReq(request) {
  const headers = {};
  for (const [k, v] of request.headers) headers[k.toLowerCase()] = v;
  const req = { method: request.method, url: new URL(request.url).pathname + new URL(request.url).search, headers };
  // api 의 readBody/readRaw 는 req.body 가 이미 있으면 스트림을 읽지 않는다.
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const buf = await request.arrayBuffer();
    const type = headers['content-type'] || '';
    // 파일 자체가 본문인 경로는 Buffer 로, 나머지는 문자열(JSON)로 넘긴다
    req.body = /json|text|urlencoded/.test(type) || buf.byteLength === 0
      ? new TextDecoder().decode(buf)
      : Buffer.from(buf);
  }
  return req;
}

async function api(request, env) {
  fillEnv(env);
  const req = await nodeReq(request);
  const res = fakeRes();
  await handler(req, res);
  await res.promise;
  const h = new Headers();
  for (const k in res._headers) h.set(k, String(res._headers[k]));
  return new Response(res._body(), { status: res.statusCode, headers: h });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api' || url.pathname.startsWith('/api/')) return api(request, env);
    // 그 밖의 주소는 정적 파일. 앱은 해시 라우팅이라 없는 경로는 index.html 로 보낸다
    let res = await env.ASSETS.fetch(request);
    // 딥링크 파일은 확장자가 없어 타입이 안 붙는다. 애플은 application/json 이 아니면 무시한다
    // (vercel.json 의 headers 로 하던 일)
    if (url.pathname === '/.well-known/apple-app-site-association' && res.status === 200) {
      res = new Response(res.body, res);
      res.headers.set('Content-Type', 'application/json');
      res.headers.set('Cache-Control', 'public, max-age=3600');
    }
    if (res.status === 404 && request.method === 'GET' && !/\.[a-z0-9]+$/i.test(url.pathname)) {
      return env.ASSETS.fetch(new Request(new URL('/index.html', url), request));
    }
    return res;
  },

  // Vercel 의 크론 두 개를 그대로 옮긴 것 (wrangler 설정의 시간표를 보고 갈라 부른다)
  async scheduled(event, env, ctx) {
    fillEnv(env);
    const path = event.cron === '0 18 * * *' ? '/api/cron/dates' : '/api/cron/remind';
    const r = await api(new Request('https://lets1414.com' + path, {
      method: 'GET', headers: { 'authorization': 'Bearer ' + (env.CRON_SECRET || '') },
    }), env);
    console.log('cron', event.cron, path, r.status);
  },
};
