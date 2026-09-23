// 운영 서버 (Google Cloud Run): app/ 정적 파일 + /api/* → api/index.js
//
// api/index.js 는 원래 Node 의 (req, res) 방식이라 감쌀 것 없이 그대로 넘긴다.
// vercel.json 이 하던 일(헤더·rewrite)을 여기서 한다. 크론은 Cloud Scheduler 가 /api/cron/* 를 부른다.
// 로컬 개발은 scripts/dev.mjs 를 쓴다 (운영 DB·저장소를 막는 안전장치가 거기 있다).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import api from './api/index.js';

const appDir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'app');
const PORT = +(process.env.PORT || 8080);
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.txt': 'text/plain; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
};
// 딥링크 파일은 확장자가 없다. 애플은 application/json 이 아니면 무시한다
const AASA = '/.well-known/apple-app-site-association';

// 정적 파일은 몇 MB 뿐이라 켤 때 전부 메모리에 올리고 gzip 도 미리 해 둔다 (Cloud Run 은 압축을 안 해 준다)
const files = new Map();
(function load(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    // 숨김 파일(.DS_Store, 도구 폴더)은 내보내지 않는다. 딥링크 폴더만 예외
    if (e.name.startsWith('.') && e.name !== '.well-known') continue;
    const f = path.join(dir, e.name);
    if (e.isDirectory()) { load(f); continue; }
    const rel = '/' + path.relative(appDir, f).split(path.sep).join('/');
    const body = fs.readFileSync(f);
    const type = rel === AASA ? 'application/json' : (MIME[path.extname(f)] || 'application/octet-stream');
    const text = /^(text\/|application\/(json|manifest))|svg/.test(type);
    const gz = text && body.length > 1024 ? zlib.gzipSync(body, { level: 9 }) : null;
    const etag = '"' + crypto.createHash('sha1').update(body).digest('base64url').slice(0, 20) + '"';
    files.set(rel, { body, gz, type, etag });
  }
})(appDir);

function cacheControl(p) {
  if (p === AASA) return 'public, max-age=3600';
  // 앱은 배포마다 바뀌는 파일 이름을 쓰지 않는다 → 늘 다시 확인하게 하고 ETag 로 304 를 준다
  return 'no-cache';
}

function serveStatic(req, res, url) {
  let p;
  try { p = decodeURIComponent(url.pathname); } catch (e) { res.statusCode = 400; return res.end('bad path'); }
  if (p.endsWith('/')) p += 'index.html';
  let f = files.get(p);
  // 해시 라우팅이라 없는 주소는 거의 오지 않지만, 확장자 없는 주소는 첫 화면으로 보낸다
  if (!f && !/\.[a-z0-9]+$/i.test(p) && p !== AASA) f = files.get('/index.html');
  if (!f) { res.statusCode = 404; res.setHeader('Content-Type', 'text/plain; charset=utf-8'); return res.end('not found'); }
  res.setHeader('Content-Type', f.type);
  res.setHeader('Cache-Control', cacheControl(p));
  res.setHeader('ETag', f.etag);
  if (f.gz) res.setHeader('Vary', 'Accept-Encoding');
  if (req.headers['if-none-match'] === f.etag) { res.statusCode = 304; return res.end(); }
  const gz = f.gz && /\bgzip\b/.test(req.headers['accept-encoding'] || '');
  const body = gz ? f.gz : f.body;
  if (gz) res.setHeader('Content-Encoding', 'gzip');
  res.setHeader('Content-Length', body.length);
  res.end(req.method === 'HEAD' ? undefined : body);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://local');
  if (url.pathname === '/api' || url.pathname.startsWith('/api/')) {
    res.setHeader('Cache-Control', 'no-store');
    return api(req, res);
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') { res.statusCode = 405; return res.end(); }
  serveStatic(req, res, url);
});
// Cloud Run 앞단(GFE)이 연결을 오래 붙잡는다. Node 기본 5초보다 길게 둬야 가끔 나는 502 가 없다
server.keepAliveTimeout = 620 * 1000;
server.headersTimeout = 630 * 1000;
server.listen(PORT, () => console.log(`1414 on :${PORT} (static ${files.size} files)`));

// 새 버전으로 넘어갈 때 Cloud Run 이 SIGTERM 을 보낸다. 처리 중인 요청은 끝내고 내린다
// 요청 하나의 실수로 인스턴스 전체가 죽지 않게 (Vercel 은 요청마다 격리돼 있어 몰랐던 부분)
process.on('unhandledRejection', (e) => console.error('unhandledRejection', e));
process.on('SIGTERM', () => server.close(() => process.exit(0)));
