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

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'app');
const { default: api } = await import(path.join(root, 'api', 'index.js'));
const PORT = +(process.env.PORT || 8766);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.css': 'text/css' };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://local');
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return api(req, res);
  let p = decodeURIComponent(url.pathname); if (p.endsWith('/')) p += 'index.html';
  const file = path.normalize(path.join(appDir, p));
  if (!file.startsWith(appDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end('not found'); }
  res.setHeader('Content-Type', MIME[path.extname(file)] || 'application/octet-stream');
  res.setHeader('Cache-Control', 'no-cache');
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log(`conti dev: http://localhost:${PORT}/`));
