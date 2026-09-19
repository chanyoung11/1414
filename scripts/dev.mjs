// 로컬 개발 서버: app/ 정적 파일 + /api/* → api/[...path].js (Vercel과 같은 핸들러)
// 사용: DATABASE_URL=... AUTH_SECRET=... node scripts/dev.mjs   (PORT 기본 8766)
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// 실수로 운영 DB 를 보고 테스트를 돌리면 운영 데이터가 더러워진다. 로컬이 아니면 막는다
{
  const u = process.env.DATABASE_URL || '';
  const local = /@(localhost|127\.0\.0\.1|\[::1\])[:/]/.test(u) || /host=localhost/.test(u);
  if (u && !local && process.env.ALLOW_PROD_DB !== '1') {
    console.error('\n[막음] DATABASE_URL 이 로컬이 아닙니다. 개발 서버는 운영 DB 를 보지 않습니다.');
    console.error('       테스트는 로컬 DB 로 돌리세요. 정말 필요하면 ALLOW_PROD_DB=1 을 붙이세요.\n');
    process.exit(1);
  }
}

// 저장소도 마찬가지다. 로컬 테스트가 운영 저장소에 올리면 지워지지 않는 쓰레기가 쌓인다
// (2026-09-19: 그렇게 1,700개 756MB 가 쌓여 무료 한도를 넘겼다)
if (!process.env.BLOB_LOCAL_DIR && (process.env.BLOB_READ_WRITE_TOKEN || process.env.R2_ACCESS_KEY_ID) && process.env.ALLOW_PROD_BLOB !== '1') {
  console.error('\n[막음] 개발 서버가 운영 파일 저장소를 보고 있습니다. BLOB_LOCAL_DIR 을 지정하세요.');
  console.error('       (정말 필요하면 ALLOW_PROD_BLOB=1)\n');
  process.exit(1);
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'app');
const { default: api } = await import(path.join(root, 'api', 'index.js'));
const PORT = +(process.env.PORT || 8766);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.css': 'text/css' };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://local');
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return api(req, res);
  // 로컬 파일 저장소 (BLOB_LOCAL_DIR). 운영에는 없는 경로다
  if (url.pathname.startsWith('/localblob/') && process.env.BLOB_LOCAL_DIR) {
    const dir = path.resolve(process.env.BLOB_LOCAL_DIR);
    const f = path.normalize(path.join(dir, decodeURIComponent(url.pathname.slice('/localblob/'.length))));
    if (!f.startsWith(dir)) { res.statusCode = 400; return res.end('bad path'); }
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,PUT,HEAD,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', '*');
    if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }
    if (req.method === 'PUT') {
      fs.mkdirSync(path.dirname(f), { recursive: true });
      const chunks = []; req.on('data', (c) => chunks.push(c));
      return req.on('end', () => {
        fs.writeFileSync(f, Buffer.concat(chunks));
        fs.writeFileSync(f + '.type', String(req.headers['content-type'] || 'application/octet-stream'));
        res.statusCode = 200; res.end('ok');
      });
    }
    if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.statusCode = 404; return res.end('not found'); }
    let type = 'application/octet-stream';
    try { type = fs.readFileSync(f + '.type', 'utf8'); } catch (e) {}
    res.setHeader('Content-Type', type);
    if (req.method === 'HEAD') { res.setHeader('Content-Length', fs.statSync(f).size); return res.end(); }
    return fs.createReadStream(f).pipe(res);
  }
  let p = decodeURIComponent(url.pathname); if (p.endsWith('/')) p += 'index.html';
  const file = path.normalize(path.join(appDir, p));
  if (!file.startsWith(appDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end('not found'); }
  res.setHeader('Content-Type', MIME[path.extname(file)] || 'application/octet-stream');
  res.setHeader('Cache-Control', 'no-cache');
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log(`conti dev: http://localhost:${PORT}/`));
